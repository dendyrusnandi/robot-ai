from __future__ import annotations

import sounddevice as sd


if __name__ == "__main__":
    print(sd.query_devices())
    print("Default input/output:", sd.default.device)
    sd.check_input_settings(samplerate=16000, channels=1, dtype="int16")
    sd.check_output_settings(samplerate=24000, channels=1, dtype="int16")
    print("Audio input 16 kHz: OK")
    print("Audio output 24 kHz: OK")
