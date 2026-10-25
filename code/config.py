"""Configuration management for Ghost Data Still Exists Deletion-Audit Agent."""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root if it exists
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


@dataclass
class Config:
    repo_root: Path = REPO_ROOT
    dataset_dir: Path = REPO_ROOT / "dataset"
    evidence_dir: Path = REPO_ROOT / "dataset" / "evidence"
    
    # SQLite storage
    db_path: Path = REPO_ROOT / os.getenv("DB_PATH", "data_store.db")
    faiss_index_path: Path = REPO_ROOT / os.getenv("FAISS_INDEX_PATH", "faiss_identity.index")
    
    # Embeddings
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    embedding_dim: int = 384
    
    # LLM via Groq / OpenAI compatible API
    # Prioritize GROQ_API_KEY, fallback to OPENAI_API_KEY
    groq_api_key: str = os.getenv("GROQ_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    groq_base_url: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    # Default to llama-3.3-70b-versatile or custom model name specified in .env
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    # Execution options
    temperature: float = 0.0
    max_tokens: int = 1024
    
    # Submission paths
    output_csv_path: Path = REPO_ROOT / "output.csv"
    sample_output_csv_path: Path = REPO_ROOT / "dataset" / "sample_output.csv"


config = Config()
