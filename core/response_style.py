from __future__ import annotations

from typing import Any


STYLE_INSTRUCTIONS = {
    "kasual": (
        "Gunakan gaya kasual, santai, ramah, dan natural. Hindari bahasa yang terlalu "
        "kaku, tetapi tetap sopan dan mudah dipahami."
    ),
    "formal": (
        "Gunakan gaya formal, sopan, terstruktur, dan gunakan tata bahasa yang baik. "
        "Hindari slang atau sapaan yang terlalu santai."
    ),
    "profesional": (
        "Gunakan gaya profesional, percaya diri, objektif, dan berorientasi solusi. "
        "Sampaikan informasi secara terstruktur tanpa basa-basi berlebihan."
    ),
    "ramah": (
        "Gunakan gaya hangat, sabar, suportif, dan bersahabat. Tunjukkan empati secara "
        "wajar tanpa terdengar dibuat-buat."
    ),
    "ringkas": (
        "Jawab sangat ringkas dan langsung ke inti. Gunakan satu sampai tiga kalimat "
        "kecuali pengguna meminta penjelasan lebih lengkap."
    ),
    "humoris": (
        "Gunakan gaya ringan dan sesekali humor yang sopan. Tetap utamakan jawaban yang "
        "benar, jelas, dan jangan bercanda pada situasi serius atau sensitif."
    ),
}


def response_style_instruction(config: dict[str, Any]) -> str:
    style = str(config.get("app", {}).get("response_style", "kasual")).lower()
    instruction = STYLE_INSTRUCTIONS.get(style, STYLE_INSTRUCTIONS["kasual"])
    return f"\nGaya jawaban aktif: {style}. {instruction}"
