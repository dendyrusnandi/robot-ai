#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BUILD_PYTHON="$SCRIPT_DIR/.venv/bin/python"
BUILD_TOOLS="$SCRIPT_DIR/.build-tools"
OUTPUT_ROOT="$SCRIPT_DIR/dist"
APP_DIR="$OUTPUT_ROOT/rn-ai-bot"
ARCHIVE="$OUTPUT_ROOT/rn-ai-bot-linux-x86_64.tar.gz"

if [[ ! -x "$BUILD_PYTHON" ]]; then
    echo "Error: .venv tidak ditemukan. Jalankan python3 -m venv .venv terlebih dahulu." >&2
    exit 1
fi

cd -- "$SCRIPT_DIR"

if ! PYTHONPATH="$BUILD_TOOLS${PYTHONPATH:+:$PYTHONPATH}" \
    "$BUILD_PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
    echo "PyInstaller belum tersedia. Memasang dependency build..."
    "$BUILD_PYTHON" -m pip install --target "$BUILD_TOOLS" "pyinstaller>=6.10,<7"
fi

echo "Membangun RN AI Bot portable..."
PYTHONPATH="$BUILD_TOOLS${PYTHONPATH:+:$PYTHONPATH}" "$BUILD_PYTHON" -m PyInstaller \
    --noconfirm \
    --clean \
    --onedir \
    --name rn-ai-bot \
    --contents-directory runtime \
    --collect-all PySide6 \
    --collect-submodules google.genai \
    --collect-submodules docx \
    --collect-submodules pypdf \
    --hidden-import sounddevice \
    --hidden-import cv2 \
    --hidden-import qasync \
    main.py

install -m 0755 start.sh "$APP_DIR/start.sh"
install -m 0644 config.yaml "$APP_DIR/config.yaml"
install -m 0644 README.md "$APP_DIR/README.md"
install -m 0644 KNOWLEDGE_SETUP.md "$APP_DIR/KNOWLEDGE_SETUP.md"
mkdir -p "$APP_DIR/face" "$APP_DIR/knowledge" "$APP_DIR/logs"
cp -a face/qml "$APP_DIR/face/"

if [[ -d knowledge ]]; then
    cp -a knowledge/. "$APP_DIR/knowledge/"
fi

if [[ -f .env.example ]]; then
    install -m 0600 .env.example "$APP_DIR/.env.example"
else
    install -m 0600 /dev/null "$APP_DIR/.env.example"
fi

if [[ "${INCLUDE_ENV:-0}" == "1" && -f .env ]]; then
    echo "Peringatan: INCLUDE_ENV=1, API key akan dimasukkan ke bundle." >&2
    install -m 0600 .env "$APP_DIR/.env"
fi

find "$APP_DIR" -type d -exec chmod 0755 {} +
tar -C "$OUTPUT_ROOT" -czf "$ARCHIVE" rn-ai-bot

echo
echo "Build selesai:"
echo "  Folder : $APP_DIR"
echo "  Arsip  : $ARCHIVE"
echo
echo "Di komputer tujuan: ekstrak arsip, isi .env, lalu jalankan ./start.sh"
