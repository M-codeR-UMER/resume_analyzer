from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from uuid import UUID

from typing import Any

from src.core.config import settings


Collection = Any


class ChromaVectorStore:
    _model: Any = None

    def __init__(self) -> None:
        self._persist_dir = Path(settings.chroma_persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._fallback_path = self._persist_dir / "vectors.json"
        self._fallback_store: dict[str, dict[str, Any]] = self._load_fallback_store()
        self._collection: Collection | None = None
        self._client: Any = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(settings.embedding_model)
            except Exception:
                self._model = None
        return self._model

    def _ensure_collection(self) -> None:
        if self._collection is not None:
            return
        try:
            chromadb_module = import_module("chromadb")
            self._client = chromadb_module.PersistentClient(path=settings.chroma_persist_dir)
            self._collection = self._client.get_or_create_collection(name=settings.chroma_collection_name)
        except Exception:  # pragma: no cover - optional dependency fallback
            self._client = None

    def _load_fallback_store(self) -> dict[str, dict[str, Any]]:
        if not self._fallback_path.exists():
            return {}
        try:
            return json.loads(self._fallback_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_fallback_store(self) -> None:
        self._fallback_path.write_text(json.dumps(self._fallback_store, ensure_ascii=True), encoding="utf-8")

    def save_embedding(self, candidate_id: UUID, text: str) -> None:
        """Generate embedding from text and upsert into ChromaDB (or fallback store)."""
        self._ensure_collection()
        model = self._get_model()

        if model is not None and self._collection is not None:
            embeddings = model.encode([text], batch_size=16, normalize_embeddings=True)
            vector = embeddings[0].tolist()
            self._collection.upsert(
                ids=[str(candidate_id)],
                embeddings=[vector],
                documents=[text],
                metadatas=[{"candidate_id": str(candidate_id)}],
            )
            return

        # Fallback: simple hash-based embedding
        vector = [0.0] * 384
        for index, character in enumerate(text.lower()):
            vector[index % 384] += (ord(character) % 31) / 31.0

        self._fallback_store[str(candidate_id)] = {
            "candidate_id": str(candidate_id),
            "embedding": vector,
            "document": text,
        }
        self._save_fallback_store()

    def upsert(self, candidate_id: UUID, vector: list[float], document: str | None = None) -> None:
        self._ensure_collection()
        if self._collection is not None:
            self._collection.upsert(
                ids=[str(candidate_id)],
                embeddings=[vector],
                documents=[document or ""],
                metadatas=[{"candidate_id": str(candidate_id)}],
            )
            return

        self._fallback_store[str(candidate_id)] = {
            "candidate_id": str(candidate_id),
            "embedding": vector,
            "document": document or "",
        }
        self._save_fallback_store()

    def get(self, candidate_id: UUID) -> dict | None:
        self._ensure_collection()
        if self._collection is not None:
            result = self._collection.get(ids=[str(candidate_id)], include=["embeddings", "documents", "metadatas"])
            if not result.get("ids"):
                return None
            return result

        return self._fallback_store.get(str(candidate_id))

    def reset_collection(self) -> None:
        self._ensure_collection()
        if self._collection is not None:
            try:
                self._client.delete_collection(name=settings.chroma_collection_name)
                self._collection = self._client.get_or_create_collection(name=settings.chroma_collection_name)
            except Exception:
                pass
        self._fallback_store = {}
        self._save_fallback_store()