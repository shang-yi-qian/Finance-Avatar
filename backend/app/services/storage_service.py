from pathlib import Path
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_GENERATED_DIR = REPO_ROOT / "frontend" / "public" / "generated"


def ensure_generated_dir(kind: str) -> Path:
    directory = PUBLIC_GENERATED_DIR / kind
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def public_url(kind: str, filename: str) -> str:
    return f"/generated/{kind}/{filename}"


def unique_filename(prefix: str, suffix: str) -> str:
    safe_prefix = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in prefix)
    return f"{safe_prefix}-{uuid4().hex[:10]}{suffix}"

