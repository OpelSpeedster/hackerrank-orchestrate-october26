"""FAISS Index with MiniLM embeddings for profile similarity matching."""

import json
import pickle
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from config import config
from data_loader import data_loader


class IdentityIndex:
    def __init__(
        self,
        index_path: Optional[Path] = None,
        model_name: Optional[str] = None,
    ):
        self.index_path = index_path or config.faiss_index_path
        self.meta_path = self.index_path.with_suffix(".pkl")
        self.model_name = model_name or config.embedding_model_name
        self.model: Optional[SentenceTransformer] = None
        self.index: Optional[faiss.Index] = None
        self.id_map: List[Dict[str, Any]] = []

    def _load_model(self) -> SentenceTransformer:
        if self.model is None:
            self.model = SentenceTransformer(self.model_name)
        return self.model

    def build_index(self, force_rebuild: bool = False) -> None:
        """Build and persist FAISS index from user identities and audit log."""
        if (
            not force_rebuild
            and self.index_path.exists()
            and self.meta_path.exists()
        ):
            self.load_index()
            return

        model = self._load_model()
        users_df = data_loader.get_user_identities_df()

        # Connect to SQLite to get audit log history for each user
        with data_loader.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, field_name, old_value FROM user_audit_log WHERE field_name IN ('email', 'phone', 'name')"
            )
            audit_records = cursor.fetchall()

        user_historical: Dict[str, List[str]] = {}
        for r in audit_records:
            uid = r["user_id"]
            if uid not in user_historical:
                user_historical[uid] = []
            user_historical[uid].append(f"{r['field_name']}: {r['old_value']}")

        texts: List[str] = []
        self.id_map = []

        for _, row in users_df.iterrows():
            uid = str(row["user_id"])
            name = str(row.get("name", ""))
            email = str(row.get("email", ""))
            phone = str(row.get("phone", ""))
            email_hash = str(row.get("email_hash", ""))
            history = user_historical.get(uid, [])
            hist_str = " | ".join(history) if history else "none"

            text = f"User: {uid} | Name: {name} | Email: {email} | Phone: {phone} | Hash: {email_hash} | Historical: {hist_str}"
            texts.append(text)
            self.id_map.append({
                "user_id": uid,
                "name": name,
                "email": email,
                "phone": phone,
                "email_hash": email_hash,
                "history": history,
            })

        # Generate embeddings
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)

        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)

        # Save to disk
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        with open(self.meta_path, "wb") as f:
            pickle.dump(self.id_map, f)

    def load_index(self) -> None:
        """Load FAISS index and metadata from disk."""
        if not self.index_path.exists() or not self.meta_path.exists():
            self.build_index()
            return
        self.index = faiss.read_index(str(self.index_path))
        with open(self.meta_path, "rb") as f:
            self.id_map = pickle.load(f)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """Search similar user profiles given a query string."""
        if self.index is None:
            self.load_index()

        model = self._load_model()
        query_emb = model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_emb)

        scores, indices = self.index.search(query_emb, top_k)
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx != -1 and idx < len(self.id_map):
                results.append((self.id_map[idx], float(score)))
        return results


identity_index = IdentityIndex()
