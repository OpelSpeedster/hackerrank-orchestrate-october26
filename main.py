"""Entry point for running Ghost Data Still Exists Deletion-Audit Agent from repo root."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
CODE_DIR = REPO_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from main import main

if __name__ == "__main__":
    main()
