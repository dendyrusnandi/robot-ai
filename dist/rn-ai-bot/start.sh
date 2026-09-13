#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
BUNDLE_BINARY="$SCRIPT_DIR/rn-ai-bot"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ ! -x "$BUNDLE_BINARY" && ! -x "$VENV_PYTHON" ]]; then
    echo "Error: binary bundle dan virtual environment tidak ditemukan." >&2
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Peringatan: $ENV_FILE belum ada. API key mungkin belum dikonfigurasi." >&2
fi

cd -- "$SCRIPT_DIR"
export PYTHONUNBUFFERED=1

CURRENT_UID="$(id -u)"
CURRENT_RUNTIME_DIR="/run/user/$CURRENT_UID"

# A login shell created with `su - mac` does not inherit the graphical session
# variables. Recover the user's Wayland session first (Ubuntu 22 default), or
# fall back to the local X display.
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    if [[ -S "$CURRENT_RUNTIME_DIR/wayland-0" ]]; then
        export XDG_RUNTIME_DIR="$CURRENT_RUNTIME_DIR"
        export WAYLAND_DISPLAY="wayland-0"
        export QT_QPA_PLATFORM="wayland"
        export DBUS_SESSION_BUS_ADDRESS="unix:path=$CURRENT_RUNTIME_DIR/bus"
        echo "Display desktop: Wayland ($WAYLAND_DISPLAY)"
    elif [[ -S /tmp/.X11-unix/X0 ]]; then
        export DISPLAY=":0"
        echo "Display desktop: X11 ($DISPLAY)"
    elif [[ -S /tmp/.X11-unix/X1 ]]; then
        export DISPLAY=":1"
        echo "Display desktop: X11 ($DISPLAY)"
    fi
fi

# When launched from a root terminal, ALSA/PortAudio can silently select its
# null device because the real PulseAudio/PipeWire server belongs to the
# logged-in desktop user. Reuse that session so microphone and speaker carry
# real samples instead of permanent zeroes.
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    for runtime_dir in /run/user/[0-9]*; do
        if [[ -S "$runtime_dir/pulse/native" ]]; then
            export XDG_RUNTIME_DIR="$runtime_dir"
            export PULSE_SERVER="unix:$runtime_dir/pulse/native"
            echo "Audio desktop: $PULSE_SERVER"
            break
        fi
    done
fi

# Normal desktop-user launch: explicitly bind audio to the same user session.
if [[ -z "${PULSE_SERVER:-}" && -S "$CURRENT_RUNTIME_DIR/pulse/native" ]]; then
    export XDG_RUNTIME_DIR="$CURRENT_RUNTIME_DIR"
    export PULSE_SERVER="unix:$CURRENT_RUNTIME_DIR/pulse/native"
    echo "Audio desktop: $PULSE_SERVER"
fi

# Use PulseAudio's WebRTC acoustic echo canceller so the built-in microphone
# does not feed the robot's own speaker voice back into barge-in detection.
if command -v pactl >/dev/null 2>&1 && [[ -n "${PULSE_SERVER:-}" ]]; then
    if ! pactl list short sources 2>/dev/null | rg -q $'\trn_ai_echo_cancel\t'; then
        if ! pactl load-module module-echo-cancel \
            aec_method=webrtc \
            source_name=rn_ai_echo_cancel \
            sink_name=rn_ai_echo_cancel_sink \
            source_master=alsa_input.pci-0000_00_1b.0.analog-stereo \
            sink_master=alsa_output.pci-0000_00_1b.0.analog-stereo >/dev/null 2>&1; then
            echo "Peringatan: echo cancellation tidak dapat diaktifkan." >&2
        fi
    fi
    if pactl list short sources 2>/dev/null | rg -q $'\trn_ai_echo_cancel\t'; then
        export PULSE_SOURCE="rn_ai_echo_cancel"
        export PULSE_SINK="rn_ai_echo_cancel_sink"
        echo "Echo cancellation: WebRTC aktif"
    fi
fi

echo "Menjalankan RN AI Bot..."
echo "Folder: $SCRIPT_DIR"
if [[ -x "$BUNDLE_BINARY" ]]; then
    exec "$BUNDLE_BINARY" "$@"
fi
exec "$VENV_PYTHON" -u main.py "$@"
