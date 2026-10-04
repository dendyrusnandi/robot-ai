from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from collections.abc import Iterator
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
RESPONSES_URL = "https://api.openai.com/v1/responses"

INSTRUCTIONS = """Kamu adalah RN, robot AI dari Robotika Nusantara yang ramah.
Jawab selalu dalam Bahasa Indonesia yang natural, jelas, dan ringkas.
Dalam konteks percakapan ini, RN merujuk pada Robotika Nusantara, bukan
Registered Nurse. Semua jawaban harus didasarkan pada hasil file_search dari
dokumen knowledge. Utamakan definisi, nama, dan istilah yang tertulis dalam
dokumen daripada arti umum dari pengetahuan model. Jika informasi tidak
ditemukan dalam dokumen, katakan dengan jujur bahwa informasinya tidak
ditemukan. Jangan mengarang atau mengganti arti singkatan.
"""


def load_dotenv_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def config_value(section: str, key: str, default: str) -> str:
    current_section = ""
    for raw_line in (ROOT / "config.yaml").read_text(encoding="utf-8").splitlines():
        if raw_line and not raw_line.startswith((" ", "\t")) and raw_line.rstrip().endswith(":"):
            current_section = raw_line.strip()[:-1]
            continue
        if current_section == section:
            stripped = raw_line.strip()
            if stripped.startswith(f"{key}:"):
                return stripped.split(":", 1)[1].strip().strip('"').strip("'")
    return default


def extract_output_text(response: dict[str, Any]) -> str:
    texts: list[str] = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                texts.append(str(content["text"]))
    return "\n".join(texts).strip()


class KnowledgeCLI:
    def __init__(self) -> None:
        self.vector_store_id = config_value("knowledge", "vector_store_id", "")
        # text_model is nested under providers.openai. Its key is unique in this config.
        self.model = config_value("providers", "text_model", "") or _find_key(
            "text_model", "gpt-5-mini"
        )
        self.max_results = max(1, min(50, int(config_value("knowledge", "max_results", "4"))))
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.previous_response_id: str | None = None

        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY belum diisi di file .env")
        if not self.vector_store_id.startswith("vs_"):
            raise RuntimeError("knowledge.vector_store_id tidak valid di config.yaml")

    def ask(self, question: str) -> str:
        return "".join(self.ask_stream(question))

    def ask_stream(self, question: str) -> Iterator[str]:
        payload: dict[str, Any] = {
            "model": self.model,
            "instructions": INSTRUCTIONS,
            "input": question,
            "tools": [{
                "type": "file_search",
                "vector_store_ids": [self.vector_store_id],
                "max_num_results": self.max_results,
            }],
            "tool_choice": "required",
            "stream": True,
        }
        if self.previous_response_id:
            payload["previous_response_id"] = self.previous_response_id

        request = Request(
            RESPONSES_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=90) as response:
                received_text = False
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data:"):
                        continue
                    encoded_event = line[5:].strip()
                    if not encoded_event or encoded_event == "[DONE]":
                        continue
                    event = json.loads(encoded_event)
                    event_type = event.get("type")
                    if event_type == "response.created":
                        self.previous_response_id = event.get("response", {}).get("id")
                    elif event_type == "response.output_text.delta":
                        delta = str(event.get("delta", ""))
                        if delta:
                            received_text = True
                            yield delta
                    elif event_type == "response.completed":
                        response_data = event.get("response", {})
                        self.previous_response_id = (
                            response_data.get("id") or self.previous_response_id
                        )
                    elif event_type in {"error", "response.failed"}:
                        error = event.get("error") or event.get("response", {}).get("error") or {}
                        detail = error.get("message") if isinstance(error, dict) else str(error)
                        raise RuntimeError(detail or "Streaming response OpenAI gagal")
                if not received_text:
                    raise RuntimeError("OpenAI tidak mengembalikan output teks")
        except HTTPError as exc:
            try:
                error_data = json.loads(exc.read().decode("utf-8"))
                detail = error_data.get("error", {}).get("message", str(exc))
            except (ValueError, UnicodeDecodeError):
                detail = str(exc)
            raise RuntimeError(f"OpenAI API {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Tidak dapat terhubung ke OpenAI: {exc.reason}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tes jawaban teks RN dari OpenAI Vector Store"
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Pertanyaan satu kali; kosongkan untuk mode percakapan interaktif",
    )
    return parser.parse_args()


def _find_key(key: str, default: str) -> str:
    for raw_line in (ROOT / "config.yaml").read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith(f"{key}:"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
    return default


def main() -> int:
    args = parse_args()
    try:
        load_dotenv_file(ROOT / ".env")
        bot = KnowledgeCLI()
        if args.question:
            for delta in bot.ask_stream(" ".join(args.question)):
                print(delta, end="", flush=True)
            print()
            return 0

        print(
            f"RN Knowledge CLI — model={bot.model}, vector_store={bot.vector_store_id}\n"
            "Ketik pertanyaan. Gunakan 'exit', 'quit', atau Ctrl+C untuk keluar."
        )
        while True:
            try:
                question = input("\nAnda > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSelesai.")
                return 0
            if question.casefold() in {"exit", "quit", "keluar"}:
                print("Selesai.")
                return 0
            if not question:
                continue
            try:
                print("RN   > ", end="", flush=True)
                for delta in bot.ask_stream(question):
                    print(delta, end="", flush=True)
                print()
            except RuntimeError as exc:
                print()
                print(f"Error: {exc}", file=sys.stderr)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
