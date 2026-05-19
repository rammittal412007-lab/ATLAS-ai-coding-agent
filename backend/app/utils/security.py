"""
Sandbox Security Helpers
Validates commands and file operations before passing them
to the Docker executor, preventing accidental or malicious damage.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

logger = structlog.get_logger(__name__)

# ─── Dangerous command patterns ───────────────────────────────────────────────

# These patterns in a command string are always blocked.
BLOCKED_COMMAND_PATTERNS: List[re.Pattern] = [
    re.compile(r"\brm\s+-rf\s+/"),             # rm -rf /
    re.compile(r"\bformat\b.*\b(c:|d:)\b", re.IGNORECASE),  # Windows format
    re.compile(r"\b(shutdown|reboot|halt|poweroff)\b"),
    re.compile(r"\bdd\s+if="),                  # disk destroy
    re.compile(r"\bmkfs\b"),                    # filesystem format
    re.compile(r">\s*/dev/sda"),               # write to raw disk
    re.compile(r"\bchmod\s+777\s+/"),           # world-write root
    re.compile(r"\bchown\s+.*\s+/"),            # chown root
    re.compile(r"\bcurl.*\|\s*(?:bash|sh|python)"), # curl-pipe-exec
    re.compile(r"\bwget.*\|\s*(?:bash|sh|python)"),
    re.compile(r"(?:;|&&|\|\|)\s*rm\s+-rf"),    # rm -rf chained after another command
    re.compile(r"\b(eval|exec)\s+\$\("),        # eval $(...)
    re.compile(r"/etc/shadow"),                 # sensitive file
    re.compile(r"/etc/passwd"),
    re.compile(r"\bkill\s+-9\s+1\b"),           # kill init
    re.compile(r"\bnsenter\b"),                 # namespace escape
    re.compile(r"\bdocker\s+.*--privileged"),   # privileged Docker-in-Docker
]

# Commands that are suspicious but allowed with a warning
SUSPICIOUS_PATTERNS: List[re.Pattern] = [
    re.compile(r"\brm\s+-rf\b"),
    re.compile(r"\bsudo\b"),
    re.compile(r"\bcurl\b.*\bhttp"),
    re.compile(r"\bwget\b.*\bhttp"),
    re.compile(r"\bpip\s+install\b"),
    re.compile(r"\bnpm\s+install\b"),
    re.compile(r"\bapt-get\s+install\b"),
    re.compile(r"\bapt\s+install\b"),
]

# Allowed file extensions for write operations by agents
ALLOWED_WRITE_EXTENSIONS: Set[str] = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
    ".cpp", ".c", ".h", ".cs", ".rb", ".php", ".swift", ".kt",
    ".md", ".txt", ".rst", ".yaml", ".yml", ".json", ".toml",
    ".tf", ".sql", ".sh", ".dockerfile", ".env.example",
    ".gitignore", ".dockerignore", ".editorconfig",
    ".css", ".scss", ".sass", ".html", ".svg",
    ".cfg", ".ini", ".conf",
}

# Paths that agents must never write to
PROTECTED_PATHS: Set[str] = {
    "/etc/", "/usr/", "/bin/", "/sbin/", "/boot/",
    "/dev/", "/proc/", "/sys/", "/var/log/",
    "~/.ssh/", "~/.gnupg/",
}


# ─── Command validation ───────────────────────────────────────────────────────

class CommandValidationResult:
    def __init__(
        self,
        safe: bool,
        blocked_reason: Optional[str] = None,
        warnings: Optional[List[str]] = None,
    ):
        self.safe           = safe
        self.blocked_reason = blocked_reason
        self.warnings       = warnings or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "safe":           self.safe,
            "blocked_reason": self.blocked_reason,
            "warnings":       self.warnings,
        }


def validate_command(command: str) -> CommandValidationResult:
    """
    Check a shell command for dangerous patterns.

    Returns a CommandValidationResult indicating whether the command
    is safe to execute, blocked, or suspicious.
    """
    if not command or not command.strip():
        return CommandValidationResult(safe=False, blocked_reason="Empty command")

    # Hard blocks
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if pattern.search(command):
            reason = f"Blocked pattern detected: {pattern.pattern}"
            logger.warning("Command blocked", command=command[:100], reason=reason)
            return CommandValidationResult(safe=False, blocked_reason=reason)

    # Warnings
    warnings: List[str] = []
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern.search(command):
            warnings.append(f"Suspicious pattern: {pattern.pattern}")

    if warnings:
        logger.info("Command has warnings", command=command[:100], warnings=warnings)

    return CommandValidationResult(safe=True, warnings=warnings)


def sanitize_command(command: str) -> str:
    """
    Light sanitisation: strip leading/trailing whitespace,
    collapse multiple semicolons.
    Does NOT strip content — that would break legitimate commands.
    """
    return command.strip()


def validate_file_path(
    file_path: str,
    repo_root: str,
    allow_dotfiles: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a file path is safe to write:
    - stays within repo_root
    - has an allowed extension
    - is not a protected system path
    - optionally allows dot-files

    Returns (is_safe, reason_if_not_safe).
    """
    from pathlib import Path

    # Must not be absolute pointing outside repo
    p = Path(file_path)

    # Extension check
    ext = p.suffix.lower()
    if ext and ext not in ALLOWED_WRITE_EXTENSIONS and ext != "":
        return False, f"Extension '{ext}' is not in the allowed write list"

    # Protected path check
    abs_path = str((Path(repo_root) / file_path).resolve())
    for protected in PROTECTED_PATHS:
        if abs_path.startswith(protected):
            return False, f"Path is in protected location: {protected}"

    # Dotfile check
    if not allow_dotfiles:
        parts = p.parts
        for part in parts:
            if part.startswith(".") and part not in {
                ".env.example", ".gitignore", ".dockerignore", ".editorconfig"
            }:
                return False, f"Dotfile writes are restricted: {part}"

    return True, None


def validate_environment_vars(env: Dict[str, str]) -> Tuple[bool, List[str]]:
    """
    Check environment variables passed to the sandbox for dangerous values.
    Returns (safe, list_of_issues).
    """
    issues: List[str] = []
    SENSITIVE_KEYS = {
        "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "DATABASE_URL",
        "REDIS_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "SECRET_KEY", "JWT_SECRET",
    }

    for key in env:
        if key.upper() in SENSITIVE_KEYS:
            issues.append(f"Sensitive key '{key}' should not be passed to sandbox")

    return len(issues) == 0, issues


# ─── Path traversal detection ────────────────────────────────────────────────

def detect_path_traversal(path: str) -> bool:
    """
    Return True if the path contains traversal sequences.
    """
    suspicious = [
        "..",
        "%2e%2e",   # URL encoded
        "%252e",    # double encoded
        "..%2f",
        "..%5c",
    ]
    lower = path.lower()
    return any(s in lower for s in suspicious)


# ─── Content scanning ─────────────────────────────────────────────────────────

MALICIOUS_CODE_PATTERNS: List[re.Pattern] = [
    re.compile(r"import\s+os\s*;\s*os\.system\s*\("),   # obvious shell injection
    re.compile(r"__import__\('os'\)"),
    re.compile(r"subprocess\.call\(\[.*rm.*-rf"),
    re.compile(r"eval\(base64\.b64decode"),              # encoded eval
]


def scan_code_for_malicious_patterns(code: str) -> List[str]:
    """
    Scan generated code for obviously malicious patterns.
    Returns a list of warnings (empty = clean).
    """
    warnings: List[str] = []
    for pattern in MALICIOUS_CODE_PATTERNS:
        if pattern.search(code):
            warnings.append(f"Potentially dangerous pattern: {pattern.pattern}")
    return warnings
