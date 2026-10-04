from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from docx import Document
from pypdf import PdfReader


class KnowledgeStore:
    SUPPORTED = {".pdf", ".docx", ".md", ".txt"}

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self.root = root
        self.config = config.get("knowledge", {})
        self.folder = root / str(self.config.get("folder", "knowledge"))
        self.cache_path = self.folder / ".vector_store.json"
        self.model = str(self.config.get("embedding_model", "text-embedding-3-small"))
        self.chunks: list[dict[str, Any]] = []
        self.matrix: np.ndarray | None = None
        self.enabled = False
        self.logger = logging.getLogger("KNOWLEDGE")

    async def initialize(self) -> bool:
        self.folder.mkdir(parents=True, exist_ok=True)
        if not bool(self.config.get("enabled", True)):
            self.logger.info("knowledge disabled by configuration")
            return False
        files = sorted(
            path for path in self.folder.rglob("*")
            if path.is_file() and path.suffix.casefold() in self.SUPPORTED
        )
        if not files:
            self.logger.info("knowledge disabled: folder has no supported documents")
            return False

        fingerprint = self._fingerprint(files)
        if self._load_cache(fingerprint):
            self.enabled = True
            self.logger.info("knowledge ready from cache documents=%s chunks=%s", len(files), len(self.chunks))
            return True

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            self.logger.warning("knowledge disabled: OPENAI_API_KEY is not set")
            return False

        chunks = await asyncio.to_thread(self._extract_chunks, files)
        if not chunks:
            self.logger.warning("knowledge disabled: documents contain no readable text")
            return False
        texts = [chunk["text"] for chunk in chunks]
        embeddings = await self._embed(texts, api_key)
        self.chunks = chunks
        self.matrix = self._normalize(np.asarray(embeddings, dtype=np.float32))
        self.enabled = True
        self._save_cache(fingerprint)
        self.logger.info("knowledge indexed documents=%s chunks=%s", len(files), len(chunks))
        return True

    async def search(self, query: str) -> list[dict[str, Any]]:
        if not self.enabled or self.matrix is None or not query.strip():
            return []
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return []
        vector = np.asarray((await self._embed([query], api_key))[0], dtype=np.float32)
        vector /= max(float(np.linalg.norm(vector)), 1e-12)
        scores = self.matrix @ vector
        limit = max(1, min(8, int(self.config.get("max_results", 4))))
        minimum = float(self.config.get("minimum_score", 0.20))
        ranked = np.argsort(scores)[::-1][:limit]
        return [
            {
                "source": self.chunks[int(index)]["source"],
                "text": self.chunks[int(index)]["text"],
                "score": round(float(scores[int(index)]), 4),
            }
            for index in ranked if float(scores[int(index)]) >= minimum
        ]

    async def _embed(self, texts: list[str], api_key: str) -> list[list[float]]:
        output: list[list[float]] = []
        timeout = httpx.Timeout(60.0, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for offset in range(0, len(texts), 64):
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": self.model, "input": texts[offset:offset + 64]},
                )
                response.raise_for_status()
                data = sorted(response.json()["data"], key=lambda item: item["index"])
                output.extend(item["embedding"] for item in data)
        return output

    def _extract_chunks(self, files: list[Path]) -> list[dict[str, str]]:
        chunks: list[dict[str, str]] = []
        size = max(400, int(self.config.get("chunk_characters", 1400)))
        overlap = max(0, min(size // 2, int(self.config.get("chunk_overlap", 220))))
        for path in files:
            try:
                text = self._read(path)
            except Exception:
                self.logger.exception("failed reading knowledge file=%s", path.name)
                continue
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            start = 0
            while start < len(text):
                end = min(len(text), start + size)
                if end < len(text):
                    boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
                    if boundary > start + size // 2:
                        end = boundary + 1
                content = text[start:end].strip()
                if len(content) >= 40:
                    chunks.append({"source": str(path.relative_to(self.folder)), "text": content})
                if end >= len(text):
                    break
                start = max(start + 1, end - overlap)
        return chunks

    @staticmethod
    def _read(path: Path) -> str:
        suffix = path.suffix.casefold()
        if suffix in {".md", ".txt"}:
            return path.read_text(encoding="utf-8", errors="replace")
        if suffix == ".pdf":
            return "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        if suffix == ".docx":
            return "\n".join(paragraph.text for paragraph in Document(path).paragraphs)
        return ""

    def _fingerprint(self, files: list[Path]) -> str:
        digest = hashlib.sha256(self.model.encode())
        for path in files:
            stat = path.stat()
            digest.update(str(path.relative_to(self.folder)).encode())
            digest.update(str(stat.st_size).encode())
            digest.update(str(stat.st_mtime_ns).encode())
        return digest.hexdigest()

    def _load_cache(self, fingerprint: str) -> bool:
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if payload.get("fingerprint") != fingerprint or payload.get("model") != self.model:
                return False
            self.chunks = payload["chunks"]
            self.matrix = self._normalize(np.asarray(payload["embeddings"], dtype=np.float32))
            return bool(self.chunks) and len(self.chunks) == len(self.matrix)
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def _save_cache(self, fingerprint: str) -> None:
        assert self.matrix is not None
        temporary = self.cache_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({
            "fingerprint": fingerprint,
            "model": self.model,
            "chunks": self.chunks,
            "embeddings": self.matrix.tolist(),
        }, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.cache_path)

    @staticmethod
    def _normalize(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.maximum(norms, 1e-12)
