# RN AI BOT

Phase 1 foundation and animated HDMI face for the modular RN AI Bot stack.

## Install

```bash
cd rn-ai-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Development controls: `1` idle, `2` listening, `3` thinking, `4` speaking,
`5` vision, `H` happy, `C` curious, `N` neutral, and `Esc` exit.

Set `display.fullscreen: true` in `config.yaml` for HDMI fullscreen mode.

## Basic checks

```bash
python -m compileall -q core providers face main.py scripts tests
pytest -q
```

The active provider is configured in `config.yaml`; it now defaults to Gemini.
Vision and motion remain disabled until their dedicated phases are tested.

## Gemini Live voice

Create `.env` with `GEMINI_API_KEY=...`. The default config now streams mono
16-bit PCM microphone audio at 16 kHz to Gemini Live and plays its 24 kHz PCM
response through the default speaker. Set `audio.input_device` or
`audio.output_device` in `config.yaml` when the system defaults are incorrect.
