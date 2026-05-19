"""
GitHub Integration Tools
Provides repository operations: branch creation, commits,
PR preparation, and diff handling via PyGithub and GitPython.
"""
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class GitHubTools:
    """
    Wraps git CLI and PyGithub for repository operations
    needed by the coding agent pipeline.
    """

    def __init__(self, repo_path: str, github_token: Optional[str] = None):
        self.repo_path    = Path(repo_path)
        self.github_token = github_token or settings.GITHUB_TOKEN
        self._gh          = None  # lazy PyGithub client

    # ── Git CLI helpers ───────────────────────────────────────────────────────

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in repo_path."""
        cmd = ["git", "-C", str(self.repo_path)] + list(args)
        logger.debug("git command", cmd=" ".join(cmd))
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
        )

    # ── Status ────────────────────────────────────────────────────────────────

    def get_current_branch(self) -> str:
        result = self._git("rev-parse", "--abbrev-ref", "HEAD", check=False)
        return result.stdout.strip() or "main"

    def get_repo_status(self) -> Dict[str, Any]:
        """Return git status summary."""
        branch = self.get_current_branch()
        status = self._git("status", "--porcelain", check=False)
        diff   = self._git("diff", "--stat", check=False)
        return {
            "branch":          branch,
            "dirty":           bool(status.stdout.strip()),
            "changed_files":   [
                line[3:].strip()
                for line in status.stdout.strip().split("\n")
                if line.strip()
            ],
            "diff_stat":       diff.stdout.strip(),
        }

    def get_remote_url(self) -> Optional[str]:
        result = self._git("remote", "get-url", "origin", check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    # ── Branch operations ─────────────────────────────────────────────────────

    def create_branch(self, branch_name: str, from_branch: str = "main") -> bool:
        """Create and switch to a new branch."""
        try:
            self._git("checkout", "-b", branch_name, from_branch)
            logger.info("Branch created", branch=branch_name)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Branch creation failed", error=e.stderr)
            return False

    def switch_branch(self, branch_name: str) -> bool:
        try:
            self._git("checkout", branch_name)
            return True
        except subprocess.CalledProcessError:
            return False

    def list_branches(self) -> List[str]:
        result = self._git("branch", "--list", check=False)
        return [
            line.strip().lstrip("* ")
            for line in result.stdout.strip().split("\n")
            if line.strip()
        ]

    # ── Staging and committing ────────────────────────────────────────────────

    def stage_files(self, file_paths: Optional[List[str]] = None) -> bool:
        """Stage specific files or all changes."""
        try:
            if file_paths:
                for fp in file_paths:
                    self._git("add", fp)
            else:
                self._git("add", "-A")
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Staging failed", error=e.stderr)
            return False

    def commit(
        self,
        message: str,
        author_name: str = "AgentForge",
        author_email: str = "agent@agentforge.dev",
    ) -> Optional[str]:
        """Commit staged changes and return the commit hash."""
        try:
            env = os.environ.copy()
            env["GIT_AUTHOR_NAME"]     = author_name
            env["GIT_AUTHOR_EMAIL"]    = author_email
            env["GIT_COMMITTER_NAME"]  = author_name
            env["GIT_COMMITTER_EMAIL"] = author_email

            result = subprocess.run(
                ["git", "-C", str(self.repo_path), "commit", "-m", message],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            # Extract commit hash from output
            hash_result = self._git("rev-parse", "HEAD", check=False)
            commit_hash = hash_result.stdout.strip()[:8]
            logger.info("Committed", hash=commit_hash, message=message[:60])
            return commit_hash
        except subprocess.CalledProcessError as e:
            logger.error("Commit failed", error=e.stderr)
            return None

    def stage_and_commit(
        self,
        message: str,
        file_paths: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Convenience: stage files then commit."""
        if self.stage_files(file_paths):
            return self.commit(message)
        return None

    # ── Diff generation ───────────────────────────────────────────────────────

    def get_diff(
        self,
        from_ref: str = "HEAD",
        to_ref: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> str:
        """Generate a unified diff."""
        cmd = ["diff", from_ref]
        if to_ref:
            cmd.append(to_ref)
        if file_path:
            cmd += ["--", file_path]
        result = self._git(*cmd, check=False)
        return result.stdout

    def get_staged_diff(self) -> str:
        result = self._git("diff", "--cached", check=False)
        return result.stdout

    def get_file_diff_against_head(self, file_path: str) -> str:
        result = self._git("diff", "HEAD", "--", file_path, check=False)
        return result.stdout

    # ── Patch application ─────────────────────────────────────────────────────

    def apply_patch(self, patch_content: str) -> Dict[str, Any]:
        """Apply a unified diff patch to the working tree."""
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".patch",
            delete=False,
        ) as f:
            f.write(patch_content)
            patch_path = f.name

        try:
            result = subprocess.run(
                ["git", "-C", str(self.repo_path),
                 "apply", "--check", patch_path],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return {
                    "success": False,
                    "error":   result.stderr,
                    "stage":   "check",
                }

            result = subprocess.run(
                ["git", "-C", str(self.repo_path), "apply", patch_path],
                capture_output=True,
                text=True,
            )
            success = result.returncode == 0
            return {
                "success": success,
                "stdout":  result.stdout,
                "error":   result.stderr if not success else "",
                "stage":   "apply",
            }
        finally:
            os.unlink(patch_path)

    # ── Push and PR preparation ───────────────────────────────────────────────

    def push_branch(self, branch_name: Optional[str] = None) -> bool:
        """Push current or specified branch to origin."""
        branch = branch_name or self.get_current_branch()
        try:
            if self.github_token:
                remote_url = self.get_remote_url()
                if remote_url and "github.com" in remote_url:
                    authed_url = remote_url.replace(
                        "https://",
                        f"https://{self.github_token}@",
                    )
                    self._git("remote", "set-url", "origin", authed_url)

            self._git("push", "origin", branch)
            logger.info("Branch pushed", branch=branch)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Push failed", error=e.stderr)
            return False

    def prepare_pr_data(
        self,
        task_title: str,
        task_description: str,
        implementation_summary: str,
        files_changed: List[str],
        test_results: str,
        review_score: int,
    ) -> Dict[str, Any]:
        """Build a structured PR description dict."""
        body = f"""## Summary
{implementation_summary}

## Task
{task_description}

## Changes
{chr(10).join(f'- `{f}`' for f in files_changed)}

## Test Results
