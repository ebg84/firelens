"""Path resolution for the prep pipeline.

The heavy data root lives OUTSIDE the repo (sibling dir, outside iCloud) and is
addressed only through $FIRELENS_DATA — never a hardcoded absolute path. The
value is loaded from the repo-root .env (resolved relative to this file, so it
works regardless of the caller's cwd) and may also come from the shell.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")


def data_root() -> Path:
    v = os.environ.get("FIRELENS_DATA")
    if not v:
        raise RuntimeError(
            "FIRELENS_DATA is unset. Set it in the repo-root .env or the shell."
        )
    return Path(v).expanduser()


DATA_ROOT = data_root()
RAW_GEFF = DATA_ROOT / "raw" / "geff"
INTERIM = DATA_ROOT / "interim"
