"""
Async Filesystem Utilities
Safe async file operations, encoding detection, directory scanning.
"""
import hashlib
import os
import re
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

import aiofiles
import structlog

logger = structlog.get_logger(__name__)

# Extensions considered as binary — skipped during text operations
BINARY_EXTENSIONS: Set[str] = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv",
    ".woff", ".woff2", ".ttf", ".eot",
    ".db", ".sqlite", ".sqlite3",
    ".lock",  # handled separately
}

MAX_TEXT_SIZE = 2_000_000  # 2 MB


# ─── Read helpers ─────────────────────────────────────────────────────────────

async def read_text_file(
    path: str | Path,
    encoding: str = "utf-8",
    max_bytes: int = MAX_TEXT_SIZE,
) -> Optional[str]:
    """
    Async read a text file safely.
    Returns None if the file does not exist, is binary, or exceeds max_bytes.
    """
    p = Path(path)

    if not p.exists() or not p.is_file():
        return None

    if p.suffix.lower() in BINARY_EXTENSIONS:
        return None

    try:
        size = p.stat().st_size
        if size > max_bytes:
            logger.warning("File too large to read", path=str(p), size=size)
            return None
    except OSError:
        return None

    try:
        async with aiofiles.open(p, "r", encoding=encoding, errors="replace") as fh:
            return await fh.read()
    except Exception as e:
        logger.error("read_text_file error", path=str(p), error=str(e))
        return None


async def read_file_lines(
    path: str | Path,
    encoding: str = "utf-8",
) -> Optional[List[str]]:
    """Read a file and return its lines."""
    content = await read_text_file(path, encoding=encoding)
    return content.splitlines() if content is not None else None


async def write_text_file(
    path: str | Path,
    content: str,
    encoding: str = "utf-8",
    create_parents: bool = True,
) -> bool:
    """
    Async write content to a file.
    Returns True on success.
    """
    p = Path(path)
    try:
        if create_parents:
            p.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(p, "w", encoding=encoding) as fh:
            await fh.write(content)
        return True
    except Exception as e:
        logger.error("write_text_file error", path=str(p), error=str(e))
        return False


async def append_text_file(
    path: str | Path,
    content: str,
    encoding: str = "utf-8",
) -> bool:
    """Append text to a file."""
    try:
        async with aiofiles.open(path, "a", encoding=encoding) as fh:
            await fh.write(content)
        return True
    except Exception as e:
        logger.error("append_text_file error", path=str(path), error=str(e))
        return False


# ─── Directory scanning ───────────────────────────────────────────────────────

SKIP_DIRS: Set[str] = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "coverage", "target", "vendor",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
}


def scan_directory(
    root: str | Path,
    extensions: Optional[List[str]] = None,
    skip_dirs: Optional[Set[str]] = None,
    max_size_bytes: int = 500_000,
) -> List[Tuple[str, str]]:
    """
    Walk a directory tree and return (relative_path, extension) for each file.
    Filters by extension whitelist and size limit.
    Skips SKIP_DIRS and hidden directories/files.
    """
    base        = Path(root).resolve()
    skip        = skip_dirs or SKIP_DIRS
    results: List[Tuple[str, str]] = []

    for dirpath, dirs, files in os.walk(base):
        # Prune unwanted directories in-place
        dirs[:] = [
            d for d in dirs
            if d not in skip and not d.startswith(".")
        ]

        for fname in files:
            if fname.startswith("."):
                continue
            fpath = Path(dirpath) / fname
            ext   = fpath.suffix.lower()

            if extensions and ext not in extensions:
                continue
            if ext in BINARY_EXTENSIONS:
                continue

            try:
                size = fpath.stat().st_size
                if size > max_size_bytes or size == 0:
                    continue
                rel = str(fpath.relative_to(base))
                results.append((rel, ext))
            except OSError:
                continue

    return results


async def iter_text_files(
    root: str | Path,
    extensions: Optional[List[str]] = None,
    max_size_bytes: int = 500_000,
) -> AsyncGenerator[Tuple[str, str], None]:
    """
    Async generator that yields (relative_path, content) for each text file.
    """
    file_list = scan_directory(root, extensions=extensions, max_size_bytes=max_size_bytes)
    base = Path(root)

    for rel_path, _ in file_list:
        full = base / rel_path
        content = await read_text_file(full)
        if content is not None:
            yield rel_path, content


# ─── Path safety ─────────────────────────────────────────────────────────────

def safe_join(base: str | Path, *parts: str) -> Optional[Path]:
    """
    Join base with parts and verify the result stays within base.
    Returns None if the joined path would escape base (path traversal).
    """
    base_resolved = Path(base).resolve()
    try:
        joined = base_resolved.joinpath(*parts).resolve()
        if str(joined).startswith(str(base_resolved)):
            return joined
        return None
    except Exception:
        return None


def is_text_file(path: str | Path) -> bool:
    """Heuristic check: True if the file is likely text-readable."""
    p = Path(path)
    if p.suffix.lower() in BINARY_EXTENSIONS:
        return False
    try:
        with open(p, "rb") as f:
            chunk = f.read(512)
        # If more than 30% of bytes are non-printable, treat as binary
        non_printable = sum(
            1 for b in chunk if b < 9 or (13 < b < 32) or b == 127
        )
        return (non_printable / max(len(chunk), 1)) < 0.30
    except OSError:
        return False


# ─── File stats ───────────────────────────────────────────────────────────────

def file_line_count(path: str | Path) -> int:
    """Count lines in a file efficiently."""
    try:
        count = 0
        with open(path, "rb") as f:
            for _ in f:
                count += 1
        return count
    except OSError:
        return 0


def file_checksum(path: str | Path, algorithm: str = "md5") -> Optional[str]:
    """Compute a hash of the file contents."""
    h = hashlib.new(algorithm)
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


async def ensure_directory(path: str | Path) -> bool:
    """Create a directory (and parents) if it does not exist."""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error("ensure_directory failed", path=str(path), error=str(e))
        return False


def find_files_by_pattern(
    root: str | Path,
    pattern: str,
    skip_dirs: Optional[Set[str]] = None,
) -> List[str]:
    """
    Find files matching a glob-like pattern under root.
    Returns list of relative paths.
    """
    skip   = skip_dirs or SKIP_DIRS
    base   = Path(root)
    found: List[str] = []

    for dirpath, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
        for fname in files:
            fpath = Path(dirpath) / fname
            if re.search(pattern, fname) or re.search(pattern, str(fpath)):
                found.append(str(fpath.relative_to(base)))
    return found
