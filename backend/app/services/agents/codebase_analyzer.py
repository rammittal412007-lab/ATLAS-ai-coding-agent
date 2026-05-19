"""
Codebase Analyser
Detects frameworks, entry points, dependency graphs, and architecture patterns.
Used by the Analyst agent to enrich its understanding of a repository.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import structlog

logger = structlog.get_logger(__name__)

# ─── Framework detection signatures ──────────────────────────────────────────

FRAMEWORK_SIGNATURES: Dict[str, Dict[str, List[str]]] = {
    # Python
    "fastapi":       {"files": ["main.py"],               "patterns": ["from fastapi", "FastAPI()"]},
    "django":        {"files": ["manage.py"],              "patterns": ["django.setup()", "DJANGO_SETTINGS"]},
    "flask":         {"files": ["app.py", "wsgi.py"],      "patterns": ["from flask import", "Flask(__name__)"]},
    "celery":        {"files": ["celery_app.py"],          "patterns": ["from celery import", "Celery("]},
    "sqlalchemy":    {"files": [],                         "patterns": ["from sqlalchemy", "DeclarativeBase"]},
    "pydantic":      {"files": [],                         "patterns": ["from pydantic", "BaseModel"]},
    "langgraph":     {"files": [],                         "patterns": ["from langgraph", "StateGraph"]},
    # JavaScript / TypeScript
    "nextjs":        {"files": ["next.config.js","next.config.ts"], "patterns": ["from 'next'","NextConfig"]},
    "react":         {"files": [],                         "patterns": ["from 'react'","import React"]},
    "express":       {"files": ["server.js","app.js"],     "patterns": ["require('express')","express()"]},
    "nestjs":        {"files": [],                         "patterns": ["@Module(","@Controller("]},
    "vite":          {"files": ["vite.config.ts"],         "patterns": ["from 'vite'"]},
    # Go
    "gin":           {"files": [],                         "patterns": ["gin.Default()","gin.New()"]},
    "echo":          {"files": [],                         "patterns": ["echo.New()"]},
    # Infra
    "docker":        {"files": ["Dockerfile","docker-compose.yml"], "patterns": []},
    "kubernetes":    {"files": [],                         "patterns": ["apiVersion:", "kind: Deployment"]},
    "terraform":     {"files": [],                         "patterns": ["provider \"", "resource \""]},
}

ENTRY_POINT_CANDIDATES = [
    "main.py", "app.py", "server.py", "wsgi.py", "asgi.py",
    "manage.py", "run.py", "index.py",
    "main.go", "cmd/main.go",
    "src/main.ts", "src/index.ts", "src/app.ts",
    "index.js", "server.js", "app.js",
    "main.rs", "src/main.rs",
    "Main.java", "Application.java",
]


class CodebaseAnalyzer:
    """
    Statically analyses a repository to understand its architecture
    without running any code.
    """

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()

    # ── Framework Detection ───────────────────────────────────────────────────

    def detect_frameworks(self) -> Dict[str, bool]:
        """
        Check for known framework signatures in files and content.
        Returns a dict of framework_name → detected (bool).
        """
        detected: Dict[str, bool] = {}

        for name, sig in FRAMEWORK_SIGNATURES.items():
            found = False

            # Check by file existence
            for f in sig.get("files", []):
                if (self.repo_path / f).exists():
                    found = True
                    break

            # Check by content pattern (sample a few files)
            if not found:
                for pattern in sig.get("patterns", []):
                    if self._pattern_exists_in_repo(pattern):
                        found = True
                        break

            if found:
                detected[name] = True

        return detected

    def _pattern_exists_in_repo(self, pattern: str, max_files: int = 30) -> bool:
        """Check if a text pattern appears in any source file."""
        checked = 0
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [
                d for d in dirs
                if d not in {
                    "node_modules", ".git", "__pycache__",
                    "venv", ".venv", "dist", "build",
                }
            ]
            for fname in files:
                if checked >= max_files:
                    return False
                fpath = Path(root) / fname
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        if pattern in f.read(4096):
                            return True
                    checked += 1
                except (OSError, UnicodeDecodeError):
                    continue
        return False

    # ── Entry Points ──────────────────────────────────────────────────────────

    def find_entry_points(self) -> List[str]:
        """Return a list of likely application entry point files."""
        found = []
        for candidate in ENTRY_POINT_CANDIDATES:
            if (self.repo_path / candidate).exists():
                found.append(candidate)
        return found

    # ── Dependencies ─────────────────────────────────────────────────────────

    def extract_dependencies(self) -> Dict[str, Any]:
        """
        Parse package manifests to extract declared dependencies.
        Supports: requirements.txt, pyproject.toml, package.json, go.mod.
        """
        deps: Dict[str, Any] = {}

        # Python: requirements.txt
        req = self.repo_path / "requirements.txt"
        if req.exists():
            try:
                lines = req.read_text(encoding="utf-8").strip().split("\n")
                deps["python"] = [
                    l.strip() for l in lines
                    if l.strip() and not l.startswith("#")
                ]
            except OSError:
                pass

        # Python: pyproject.toml
        ppt = self.repo_path / "pyproject.toml"
        if ppt.exists():
            try:
                import tomllib  # Python 3.11+
                data = tomllib.loads(ppt.read_text())
                poetry_deps = (
                    data.get("tool", {})
                    .get("poetry", {})
                    .get("dependencies", {})
                )
                if poetry_deps:
                    deps["python_poetry"] = list(poetry_deps.keys())
            except Exception:
                pass

        # Node: package.json
        pkg = self.repo_path / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                deps["node"] = list(data.get("dependencies", {}).keys())
                deps["node_dev"] = list(data.get("devDependencies", {}).keys())
            except Exception:
                pass

        # Go: go.mod
        gomod = self.repo_path / "go.mod"
        if gomod.exists():
            try:
                lines = gomod.read_text(encoding="utf-8").split("\n")
                go_deps = []
                in_require = False
                for line in lines:
                    stripped = line.strip()
                    if stripped == "require (":
                        in_require = True
                        continue
                    if in_require:
                        if stripped == ")":
                            in_require = False
                        else:
                            parts = stripped.split()
                            if parts:
                                go_deps.append(parts[0])
                    elif stripped.startswith("require "):
                        go_deps.append(stripped.split()[1])
                deps["go"] = go_deps
            except OSError:
                pass

        return deps

    # ── Directory Structure ───────────────────────────────────────────────────

    def get_top_level_structure(self) -> Dict[str, str]:
        """
        Return a dict of top-level directory/file → inferred role.
        """
        roles: Dict[str, str] = {}
        ROLE_MAP = {
            "tests":          "test suite",
            "test":           "test suite",
            "__tests__":      "test suite",
            "src":            "source code",
            "app":            "application code",
            "lib":            "shared library code",
            "api":            "API layer",
            "models":         "data models",
            "routes":         "route handlers",
            "services":       "business logic services",
            "utils":          "utility functions",
            "helpers":        "helper functions",
            "middleware":     "HTTP middleware",
            "migrations":     "database migrations",
            "alembic":        "database migrations (Alembic)",
            "schemas":        "data schemas / validation",
            "workers":        "background task workers",
            "tasks":          "task definitions",
            "config":         "configuration files",
            "core":           "core framework setup",
            "docs":           "documentation",
            "scripts":        "utility scripts",
            "infra":          "infrastructure / deployment",
            "frontend":       "frontend application",
            "backend":        "backend application",
            "public":         "static assets",
            "static":         "static assets",
            "components":     "UI components",
            "hooks":          "React hooks",
            "store":          "state management",
            "pages":          "Next.js pages",
        }

        try:
            for item in sorted(self.repo_path.iterdir()):
                if item.name.startswith("."):
                    continue
                name = item.name.lower()
                role = ROLE_MAP.get(name, "directory" if item.is_dir() else "file")
                roles[item.name] = role
        except PermissionError:
            pass

        return roles

    # ── Service Map ───────────────────────────────────────────────────────────

    def build_service_map(self) -> Dict[str, List[str]]:
        """
        Build a lightweight service map: module → list of imported modules.
        Scans Python and JS/TS import statements.
        """
        service_map: Dict[str, List[str]] = {}
        SKIP_DIRS = {
            "node_modules", ".git", "__pycache__",
            "venv", ".venv", "dist", "build",
        }

        import re
        py_import  = re.compile(r"^(?:from|import)\s+([\w.]+)")
        js_import  = re.compile(r"""(?:from|require)\s+['"]([^'"]+)['"]""")

        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in files:
                fpath = Path(root) / fname
                rel   = str(fpath.relative_to(self.repo_path))

                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(8192)
                except OSError:
                    continue

                imports: List[str] = []
                if fname.endswith(".py"):
                    imports = py_import.findall(content)
                elif fname.endswith((".js", ".ts", ".tsx", ".jsx")):
                    imports = js_import.findall(content)

                if imports:
                    # Filter to project-local imports only
                    local = [
                        i for i in imports
                        if i.startswith(".") or i.startswith("app.")
                    ]
                    if local:
                        service_map[rel] = local

        return service_map

    # ── Full analysis ─────────────────────────────────────────────────────────

    def analyse(self) -> Dict[str, Any]:
        """
        Run all analyses and return a comprehensive architecture report.
        """
        frameworks   = self.detect_frameworks()
        entry_points = self.find_entry_points()
        dependencies = self.extract_dependencies()
        structure    = self.get_top_level_structure()
        service_map  = self.build_service_map()

        return {
            "frameworks":    frameworks,
            "entry_points":  entry_points,
            "dependencies":  dependencies,
            "structure":     structure,
            "service_map":   service_map,
            "detected_stack": list(frameworks.keys()),
        }
