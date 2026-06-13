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
    """The external heavy-data root (raw GEFF, interim products) for the harvest/ingest
    pipeline, from $FIRELENS_DATA. Falls back to the sibling ``firelens-data/`` by
    convention when unset, so the self-contained serving-DB build (build_duckdb over the
    committed repo-root data/) works without the env var — e.g. in the deploy container,
    which carries only the committed data/ and never touches the external root. Pipeline
    scripts that need raw inputs set FIRELENS_DATA in .env/shell, so this never triggers there.
    """
    v = os.environ.get("FIRELENS_DATA")
    if v:
        return Path(v).expanduser()
    return REPO_ROOT.parent / "firelens-data"


DATA_ROOT = data_root()
RAW_GEFF = DATA_ROOT / "raw" / "geff"
INTERIM = DATA_ROOT / "interim"
