"""
Repository Indexing Pipeline
- Clones GitHub repositories via git
- Scans files and detects languages
- Chunks code semantically by function/class boundaries
- Generates vector embeddings
- Stores chunks in Qdrant for semantic search
- Extracts repository statistics and metadata
"""
import asyncio
import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import aiofiles
import structlog
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

INDEXABLE_EXTENSIONS: set = {
    ".py",   ".js",  ".ts",  ".tsx", ".jsx",
    ".go",   ".rs",  ".java",".cpp", ".c",
    ".h",    ".cs",  ".rb",  ".php", ".swift",
    ".kt",   ".md",  ".yaml",".yml", ".json",
    ".toml", ".tf",  ".sql", ".sh",  ".dockerfile",
}

SKIP_DIRS: set = {
    "node_modules", ".git",        "__pycache__",
    ".venv",        "venv",        "env",
    "dist",         "build",       ".next",
    "coverage",     ".pytest_cache","target",
    "vendor",       ".idea",       ".vscode",
    "out",          ".turbo",      ".parcel-cache",
    "storybook-static", ".cache",  "tmp",
}

SKIP_FILES: set = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock",       "Gemfile.lock",
}

EXT_TO_LANGUAGE: Dict[str, str] = {
    ".py":  "python",      ".js":  "javascript",
    ".ts":  "typescript",  ".tsx": "typescript",
    ".jsx": "javascript",  ".go":  "go",
    ".rs":  "rust",        ".java":"java",
    ".cpp": "cpp",         ".c":   "c",
    ".h":   "c",           ".cs":  "csharp",
    ".rb":  "ruby",        ".php": "php",
    ".swift":"swift",      ".kt":  "kotlin",
    ".md":  "markdown",    ".yaml":"yaml",
    ".yml": "yaml",        ".json":"json",
    ".toml":"toml",        ".tf":  "terraform",
    ".sql": "sql",         ".sh":  "shell",
}

ARCH_HINT_FILES: set = {
    "README.md",       "package.json",    "pyproject.toml",
    "go.mod",          "Cargo.toml",      "pom.xml",
    "build.gradle",    "Gemfile",         "composer.json",
    "requirements.txt","setup.py",        "setup.cfg",
    "tsconfig.json",   "webpack.config.js","vite.config.ts",
    "docker-compose.yml","Makefile",       ".env.example",
}


# ─── Code Chunk ───────────────────────────────────────────────────────────────

class CodeChunk:
    """A semantic chunk of source code with metadata."""

    __slots__ = (
        "content", "file_path", "start_line", "end_line",
        "language", "chunk_type", "name",
    )

    def __init__(
        self,
        content: str,
        file_path: str,
        start_line: int,
        end_line: int,
        language: str,
        chunk_type: str = "code",
        name: Optional[str] = None,
    ):
        self.content    = content
        self.file_path  = file_path
        self.start_line = start_line
        self.end_line   = end_line
        self.language   = language
        self.chunk_type = chunk_type  # code | function | class | config | docs
        self.name       = name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content":    self.content,
            "file_path":  self.file_path,
            "start_line": self.start_line,
            "end_line":   self.end_line,
            "language":   self.language,
            "chunk_type": self.chunk_type,
            "name":       self.name,
        }

    def __repr__(self) -> str:
        return (
            f"CodeChunk(file={self.file_path!r}, "
            f"lines={self.start_line}-{self.end_line}, "
            f"type={self.chunk_type!r}, name={self.name!r})"
        )


# ─── Embedding Service ────────────────────────────────────────────────────────

class EmbeddingService:
    """
    Singleton wrapper around sentence-transformers.
    Generates 384-dim embeddings using all-MiniLM-L6-v2.
    """

    _instance: Optional["EmbeddingService"] = None
    _model: Optional[SentenceTransformer] = None

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load(self):
        if self._model is None:
            logger.info("Loading embedding model", model=settings.EMBEDDING_MODEL)
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info("Embedding model loaded")

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Batch encode texts and return list of embedding vectors."""
        self._load()
        vecs = self._model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return vecs.tolist()

    def embed_single(self, text: str) -> List[float]:
        return self.embed([text])[0]


# ─── Code Chunker ─────────────────────────────────────────────────────────────

class CodeChunker:
    """
    Splits source files into semantically meaningful chunks.
    Uses regex-based boundary detection for Python and JS/TS.
    Falls back to sliding-window for other languages.
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
    ):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE      # characters
        self.overlap    = overlap    or settings.CHUNK_OVERLAP

    # ── Public ────────────────────────────────────────────────────────────────

    def chunk_file(
        self,
        content: str,
        file_path: str,
        language: str,
    ) -> List[CodeChunk]:
        if not content.strip():
            return []
        if language == "python":
            return self._chunk_python(content, file_path)
        if language in ("javascript", "typescript"):
            return self._chunk_js_ts(content, file_path, language)
        if language in ("markdown",):
            return self._chunk_markdown(content, file_path)
        return self._chunk_generic(content, file_path, language)

    # ── Python ────────────────────────────────────────────────────────────────

    def _chunk_python(self, content: str, file_path: str) -> List[CodeChunk]:
        chunks: List[CodeChunk] = []
        lines = content.split("\n")

        class_pat = re.compile(r"^class\s+(\w+)")
        func_pat  = re.compile(r"^(?:async\s+)?def\s+(\w+)")

        current: List[str] = []
        current_start = 1
        current_type  = "code"
        current_name: Optional[str] = None

        for i, line in enumerate(lines, start=1):
            cm = class_pat.match(line)
            fm = func_pat.match(line)

            boundary = (cm or fm) and len(current) > 5

            if boundary:
                if current:
                    chunks.append(CodeChunk(
                        content    = "\n".join(current),
                        file_path  = file_path,
                        start_line = current_start,
                        end_line   = i - 1,
                        language   = "python",
                        chunk_type = current_type,
                        name       = current_name,
                    ))
                current       = []
                current_start = i
                current_type  = "class" if cm else "function"
                current_name  = (cm or fm).group(1)

            current.append(line)

            if len("\n".join(current)) > self.chunk_size:
                chunks.append(CodeChunk(
                    content    = "\n".join(current),
                    file_path  = file_path,
                    start_line = current_start,
                    end_line   = i,
                    language   = "python",
                    chunk_type = current_type,
                    name       = current_name,
                ))
                overlap_n     = max(1, self.overlap // 60)
                current       = current[-overlap_n:]
                current_start = i - len(current) + 1
                current_type  = "code"
                current_name  = None

        if current:
            chunks.append(CodeChunk(
                content    = "\n".join(current),
                file_path  = file_path,
                start_line = current_start,
                end_line   = len(lines),
                language   = "python",
                chunk_type = current_type,
                name       = current_name,
            ))

        return chunks

    # ── JavaScript / TypeScript ───────────────────────────────────────────────

    def _chunk_js_ts(
        self,
        content: str,
        file_path: str,
        language: str,
    ) -> List[CodeChunk]:
        chunks: List[CodeChunk] = []
        lines = content.split("\n")

        func_pat   = re.compile(
            r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?"
            r"(?:\([^)]*\)|[^=]+)\s*=>|class\s+(\w+))"
        )
        export_pat = re.compile(
            r"^export\s+(?:default\s+)?(?:function|class|const|async|interface|type)"
        )

        current: List[str] = []
        current_start = 1
        current_name: Optional[str] = None
        current_type  = "code"

        for i, line in enumerate(lines, start=1):
            fm     = func_pat.search(line)
            is_exp = bool(export_pat.match(line.strip()))

            if (fm or is_exp) and len(current) > 10:
                if current:
                    chunks.append(CodeChunk(
                        content    = "\n".join(current),
                        file_path  = file_path,
                        start_line = current_start,
                        end_line   = i - 1,
                        language   = language,
                        chunk_type = current_type,
                        name       = current_name,
                    ))
                current       = []
                current_start = i
                current_type  = "function"
                if fm:
                    current_name = fm.group(1) or fm.group(2) or fm.group(3)

            current.append(line)

            if len("\n".join(current)) > self.chunk_size:
                chunks.append(CodeChunk(
                    content    = "\n".join(current),
                    file_path  = file_path,
                    start_line = current_start,
                    end_line   = i,
                    language   = language,
                    chunk_type = current_type,
                    name       = current_name,
                ))
                overlap_n     = max(1, self.overlap // 60)
                current       = current[-overlap_n:]
                current_start = i - len(current) + 1
                current_type  = "code"
                current_name  = None

        if current:
            chunks.append(CodeChunk(
                content    = "\n".join(current),
                file_path  = file_path,
                start_line = current_start,
                end_line   = len(lines),
                language   = language,
                chunk_type = current_type,
                name       = current_name,
            ))

        return chunks

    # ── Markdown ─────────────────────────────────────────────────────────────

    def _chunk_markdown(self, content: str, file_path: str) -> List[CodeChunk]:
        chunks: List[CodeChunk] = []
        sections = re.split(r"(?=^#{1,3}\s)", content, flags=re.MULTILINE)
        line_cursor = 1

        for section in sections:
            if not section.strip():
                line_cursor += section.count("\n")
                continue
            line_count = section.count("\n") + 1
            name_match = re.match(r"#{1,3}\s+(.+)", section)
            name = name_match.group(1).strip() if name_match else None
            chunks.append(CodeChunk(
                content    = section,
                file_path  = file_path,
                start_line = line_cursor,
                end_line   = line_cursor + line_count - 1,
                language   = "markdown",
                chunk_type = "docs",
                name       = name,
            ))
            line_cursor += line_count

        return chunks

    # ── Generic sliding window ────────────────────────────────────────────────

    def _chunk_generic(
        self,
        content: str,
        file_path: str,
        language: str,
    ) -> List[CodeChunk]:
        chunks: List[CodeChunk] = []
        lines = content.split("\n")
        lines_per_chunk = max(10, self.chunk_size // 60)
        overlap_lines   = max(2, self.overlap // 60)

        i = 0
        while i < len(lines):
            end = min(i + lines_per_chunk, len(lines))
            body = "\n".join(lines[i:end])
            if body.strip():
                chunks.append(CodeChunk(
                    content    = body,
                    file_path  = file_path,
                    start_line = i + 1,
                    end_line   = end,
                    language   = language,
                    chunk_type = "code",
                ))
            if end >= len(lines):
                break
            i = end - overlap_lines

        return chunks


# ─── Repository Indexer ───────────────────────────────────────────────────────

class RepositoryIndexer:
    """
    Full pipeline: clone (optional) → discover files → chunk → embed → store.
    """

    def __init__(self):
        self.chunker           = CodeChunker()
        self.embedding_service = EmbeddingService.get_instance()

    # ── Git Clone ─────────────────────────────────────────────────────────────

    async def clone_repository(
        self,
        github_url: str,
        repo_id: str,
        github_token: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> str:
        """
        Clone a GitHub repository into the local repo storage directory.
        Returns the local path to the cloned repository.
        """
        repo_path = Path(settings.REPO_STORAGE_PATH) / repo_id

        if repo_path.exists():
            shutil.rmtree(repo_path, ignore_errors=True)

        repo_path.mkdir(parents=True, exist_ok=True)

        clone_url = github_url.rstrip("/")
        if github_token:
            # Inject token for private repositories
            clone_url = clone_url.replace(
                "https://",
                f"https://{github_token}@",
            )

        cmd = ["git", "clone", "--depth=1"]
        if branch:
            cmd += ["--branch", branch]
        cmd += [clone_url, str(repo_path)]

        logger.info("Cloning repository", url=github_url, path=str(repo_path))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

        if proc.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")[:500]
            logger.error("Git clone failed", error=error_msg)
            raise RuntimeError(f"git clone failed: {error_msg}")

        logger.info("Repository cloned successfully", path=str(repo_path))
        return str(repo_path)

    # ── File Discovery ────────────────────────────────────────────────────────

    def discover_files(self, repo_path: str) -> List[Tuple[str, str]]:
        """
        Walk the repository and return (relative_path, language) for every
        indexable file, skipping generated / dependency directories.
        """
        files: List[Tuple[str, str]] = []
        base = Path(repo_path)

        for root, dirs, filenames in os.walk(base):
            # Prune skip directories in-place (os.walk respects mutations)
            dirs[:] = [
                d for d in dirs
                if d not in SKIP_DIRS and not d.startswith(".")
            ]

            for filename in filenames:
                if filename in SKIP_FILES:
                    continue

                full_path = Path(root) / filename
                ext       = full_path.suffix.lower()

                if ext not in INDEXABLE_EXTENSIONS:
                    continue

                try:
                    size = full_path.stat().st_size
                    if size > 500_000:   # Skip files larger than 500 KB
                        continue
                    if size == 0:
                        continue

                    rel_path = str(full_path.relative_to(base))
                    language = EXT_TO_LANGUAGE.get(ext, "text")
                    files.append((rel_path, language))

                except OSError:
                    continue

        return files

    # ── Repository Statistics ─────────────────────────────────────────────────

    def collect_stats(self, repo_path: str, files: List[Tuple[str, str]]) -> Dict[str, Any]:
        """Compute basic statistics about the repository."""
        lang_counts: Dict[str, int] = {}
        total_size  = 0
        base        = Path(repo_path)

        for rel_path, language in files:
            lang_counts[language] = lang_counts.get(language, 0) + 1
            try:
                total_size += (base / rel_path).stat().st_size
            except OSError:
                pass

        dominant_lang = max(lang_counts, key=lang_counts.get) if lang_counts else "unknown"

        return {
            "file_count":     len(files),
            "language_counts":lang_counts,
            "dominant_language": dominant_lang,
            "total_size_bytes":  total_size,
            "size_mb":        round(total_size / (1024 * 1024), 2),
        }

    # ── Main Indexing Pipeline ────────────────────────────────────────────────

    async def index_repository(
        self,
        repo_path: str,
        repository_id: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Full indexing pipeline:
          1. Clear previous vectors for this repository.
          2. Discover all indexable files.
          3. For each file: read → chunk → embed → store in Qdrant.
          4. Generate architecture summary using LLM.

        Returns a summary dict with total_files, total_chunks, errors,
        architecture_summary, and stats.
        """
        from app.services.indexing.vector_store import VectorStore

        vs = VectorStore()
        await vs.delete_repository(repository_id)

        files = self.discover_files(repo_path)
        stats = self.collect_stats(repo_path, files)

        logger.info(
            "Indexing started",
            repository_id=repository_id,
            file_count=len(files),
            dominant_language=stats["dominant_language"],
        )

        total_chunks = 0
        total_files  = 0
        errors: List[Dict[str, str]] = []
        arch_hints: List[str] = []

        for idx, (file_path, language) in enumerate(files):
            try:
                full_path = Path(repo_path) / file_path

                async with aiofiles.open(
                    full_path, "r", encoding="utf-8", errors="replace"
                ) as fh:
                    content = await fh.read()

                if not content.strip():
                    continue

                # Collect key files for architecture summarisation
                filename = Path(file_path).name
                if filename in ARCH_HINT_FILES:
                    arch_hints.append(f"=== {file_path} ===\n{content[:2000]}")

                # Chunk
                chunks = self.chunker.chunk_file(content, file_path, language)
                if not chunks:
                    continue

                # Embed in batch
                texts      = [c.content for c in chunks]
                embeddings = await asyncio.get_event_loop().run_in_executor(
                    None, self.embedding_service.embed, texts
                )

                # Store
                await vs.upsert_chunks(
                    repository_id=repository_id,
                    chunks=[c.to_dict() for c in chunks],
                    embeddings=embeddings,
                )

                total_chunks += len(chunks)
                total_files  += 1

                # Progress callback every 10 files
                if progress_callback and idx % 10 == 0:
                    await progress_callback({
                        "processed":    idx + 1,
                        "total":        len(files),
                        "current_file": file_path,
                        "chunks":       total_chunks,
                        "pct":          round((idx + 1) / len(files) * 100, 1),
                    })

            except Exception as e:
                logger.warning(
                    "Failed to index file",
                    file=file_path,
                    error=str(e),
                )
                errors.append({"file": file_path, "error": str(e)})

        architecture_summary = await self._summarize_architecture(
            hints=arch_hints,
            file_count=total_files,
            chunk_count=total_chunks,
            stats=stats,
        )

        logger.info(
            "Indexing complete",
            repository_id=repository_id,
            total_files=total_files,
            total_chunks=total_chunks,
            errors=len(errors),
        )

        return {
            "total_files":          total_files,
            "total_chunks":         total_chunks,
            "errors":               errors,
            "architecture_summary": architecture_summary,
            "stats":                stats,
            "dominant_language":    stats["dominant_language"],
            "size_mb":              stats["size_mb"],
        }

    # ── Architecture Summary ──────────────────────────────────────────────────

    async def _summarize_architecture(
        self,
        hints: List[str],
        file_count: int,
        chunk_count: int,
        stats: Dict[str, Any],
    ) -> str:
        """Use Claude to generate a 2-3 paragraph architecture summary."""
        if not hints:
            dominant = stats.get("dominant_language", "unknown")
            return (
                f"Repository with {file_count} source files primarily written in "
                f"{dominant}, indexed into {chunk_count} semantic chunks."
            )

        context = "\n\n".join(hints[:6])

        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = ChatAnthropic(
                model=settings.FAST_MODEL,
                api_key=settings.ANTHROPIC_API_KEY,
                max_tokens=800,
                temperature=0.1,
            )

            response = await llm.ainvoke([
                SystemMessage(content=(
                    "You are a software architect. "
                    "Summarize the repository architecture concisely in 2-3 short paragraphs. "
                    "Cover: primary purpose, tech stack, key directories and modules."
                )),
                HumanMessage(content=(
                    f"Repository has {file_count} files "
                    f"({stats.get('dominant_language','unknown')} primary).\n\n"
                    f"Key files:\n{context}"
                )),
            ])
            return response.content

        except Exception as e:
            logger.warning("Architecture summary failed", error=str(e))
            dominant = stats.get("dominant_language", "unknown")
            return (
                f"Repository with {file_count} source files primarily written in "
                f"{dominant}, indexed into {chunk_count} semantic chunks."
            )
