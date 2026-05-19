"""
Sandbox Execution Templates
Provides default Docker commands for building and testing various languages.
Used as fallback when the implementation plan does not specify test commands.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


# ─── Command templates ────────────────────────────────────────────────────────

PYTHON_COMMANDS = {
    "install":     "pip install -r requirements.txt -q 2>&1 || true",
    "install_dev": "pip install -r requirements-dev.txt -q 2>&1 || true",
    "test":        "pytest --tb=short -q 2>&1",
    "test_cov":    "pytest --tb=short -q --cov=. --cov-report=term-missing 2>&1",
    "lint":        "ruff check . 2>&1 || flake8 . 2>&1 || true",
    "type_check":  "mypy . --ignore-missing-imports 2>&1 || true",
    "format_check":"black --check . 2>&1 || true",
}

NODE_COMMANDS = {
    "install":     "npm ci --silent 2>&1 || npm install --silent 2>&1",
    "build":       "npm run build 2>&1",
    "test":        "npm test -- --passWithNoTests 2>&1",
    "test_jest":   "npx jest --passWithNoTests --forceExit 2>&1",
    "test_vitest": "npx vitest run 2>&1",
    "lint":        "npm run lint 2>&1 || true",
    "type_check":  "npx tsc --noEmit 2>&1 || true",
}

GO_COMMANDS = {
    "build": "go build ./... 2>&1",
    "test":  "go test ./... 2>&1",
    "vet":   "go vet ./... 2>&1",
    "lint":  "golangci-lint run 2>&1 || true",
}

RUST_COMMANDS = {
    "build": "cargo build 2>&1",
    "test":  "cargo test 2>&1",
    "lint":  "cargo clippy 2>&1 || true",
    "fmt":   "cargo fmt --check 2>&1 || true",
}

JAVA_COMMANDS = {
    "build": "mvn compile -q 2>&1 || gradle build -q 2>&1",
    "test":  "mvn test -q 2>&1 || gradle test 2>&1",
}

# ─── Sandbox presets ─────────────────────────────────────────────────────────

SANDBOX_PRESETS: Dict[str, Dict[str, Any]] = {
    "python_basic": {
        "description":  "Python project with pytest",
        "setup":        [PYTHON_COMMANDS["install"]],
        "test":         [PYTHON_COMMANDS["test"]],
        "docker_image": "python:3.12-slim",
    },
    "python_full": {
        "description":  "Python project with pytest, lint, and type check",
        "setup":        [
            PYTHON_COMMANDS["install"],
            PYTHON_COMMANDS["install_dev"],
        ],
        "test":         [
            PYTHON_COMMANDS["test_cov"],
            PYTHON_COMMANDS["type_check"],
        ],
        "docker_image": "python:3.12-slim",
    },
    "node_basic": {
        "description":  "Node.js project with npm test",
        "setup":        [NODE_COMMANDS["install"]],
        "test":         [NODE_COMMANDS["test"]],
        "docker_image": "node:20-slim",
    },
    "node_full": {
        "description":  "Node.js with build, lint, and tests",
        "setup":        [NODE_COMMANDS["install"]],
        "test":         [
            NODE_COMMANDS["build"],
            NODE_COMMANDS["lint"],
            NODE_COMMANDS["test"],
        ],
        "docker_image": "node:20-slim",
    },
    "go_basic": {
        "description":  "Go project",
        "setup":        [],
        "test":         [GO_COMMANDS["vet"], GO_COMMANDS["test"]],
        "docker_image": "golang:1.22-alpine",
    },
    "rust_basic": {
        "description":  "Rust project",
        "setup":        [],
        "test":         [RUST_COMMANDS["build"], RUST_COMMANDS["test"]],
        "docker_image": "rust:1.75-slim",
    },
}


# ─── Auto-detect functions ────────────────────────────────────────────────────

async def get_test_commands(repo_path: str) -> List[str]:
    """
    Auto-detect the appropriate test commands for a repository.
    Returns a list of shell commands to run in order.
    """
    base = Path(repo_path)
    commands: List[str] = []

    # ── Python ────────────────────────────────────────────────────────────────
    if _has_file(base, "requirements.txt"):
        commands.append(PYTHON_COMMANDS["install"])
    if _has_file(base, "requirements-dev.txt"):
        commands.append(PYTHON_COMMANDS["install_dev"])
    if _has_file(base, "pyproject.toml") or _has_file(base, "pytest.ini"):
        commands.append(PYTHON_COMMANDS["test"])
        return commands
    if list(base.rglob("test_*.py")) or list(base.rglob("*_test.py")):
        commands.append(PYTHON_COMMANDS["test"])
        return commands

    # ── Node / TypeScript ─────────────────────────────────────────────────────
    if _has_file(base, "package.json"):
        commands.append(NODE_COMMANDS["install"])
        # Check scripts
        pkg = _read_json(base / "package.json")
        scripts = pkg.get("scripts", {})
        if "test" in scripts:
            test_cmd = scripts["test"]
            if "jest" in test_cmd:
                commands.append(NODE_COMMANDS["test_jest"])
            elif "vitest" in test_cmd:
                commands.append(NODE_COMMANDS["test_vitest"])
            else:
                commands.append(NODE_COMMANDS["test"])
        else:
            commands.append(
                "echo '[AgentForge] No test script found in package.json'"
            )
        return commands

    # ── Go ────────────────────────────────────────────────────────────────────
    if _has_file(base, "go.mod"):
        commands.append(GO_COMMANDS["vet"])
        commands.append(GO_COMMANDS["test"])
        return commands

    # ── Rust ─────────────────────────────────────────────────────────────────
    if _has_file(base, "Cargo.toml"):
        commands.append(RUST_COMMANDS["build"])
        commands.append(RUST_COMMANDS["test"])
        return commands

    # ── Fallback ──────────────────────────────────────────────────────────────
    commands.append(
        "echo '[AgentForge] No recognised test framework found in repository'"
    )
    return commands


async def get_build_commands(repo_path: str) -> List[str]:
    """
    Auto-detect build commands.
    """
    base     = Path(repo_path)
    commands: List[str] = []

    if _has_file(base, "package.json"):
        commands.append(NODE_COMMANDS["install"])
        pkg     = _read_json(base / "package.json")
        scripts = pkg.get("scripts", {})
        if "build" in scripts:
            commands.append(NODE_COMMANDS["build"])

    elif _has_file(base, "go.mod"):
        commands.append(GO_COMMANDS["build"])

    elif _has_file(base, "Cargo.toml"):
        commands.append(RUST_COMMANDS["build"])

    return commands


def get_preset(name: str) -> Optional[Dict[str, Any]]:
    """Return a named sandbox preset."""
    return SANDBOX_PRESETS.get(name)


def list_presets() -> List[str]:
    return list(SANDBOX_PRESETS.keys())


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _has_file(base: Path, name: str) -> bool:
    return (base / name).exists()


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
