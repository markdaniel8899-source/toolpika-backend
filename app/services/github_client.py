"""GitHub REST API client used by the Studio apply step.

The backend never writes to a local checkout for publishing. It creates a
branch, commits the generated files through the Contents API and opens a pull
request so Vercel can build and deploy the preview. All secrets come from
``app.config.settings``; the token is only ever sent in an Authorization header.
"""

from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from app.config import settings

log = structlog.get_logger(__name__)

API_BASE = "https://api.github.com"


class GitHubClientError(RuntimeError):
    """Base error for GitHub API failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body[:1000]


class GitHubAuthenticationError(GitHubClientError):
    """Raised for 401/403 responses (bad token or missing scopes)."""


class GitHubBranchExistsError(GitHubClientError):
    """Raised when the target branch already exists."""

    def __init__(self, branch: str) -> None:
        super().__init__(f"Branch already exists: {branch}")
        self.branch = branch


class GitHubClient:
    """Small, typed GitHub REST wrapper for the frontend repository.

    Authentication uses a fine-grained Personal Access Token with
    ``Contents: read/write``, ``Pull requests: read/write`` and
    ``Metadata: read`` on the target repository.
    """

    def __init__(
        self,
        pat: str | None = None,
        owner: str | None = None,
        repo: str | None = None,
        base_branch: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.pat = (pat if pat is not None else settings.github_pat).strip()
        self.owner = (owner if owner is not None else settings.github_repo_owner).strip()
        self.repo = (repo if repo is not None else settings.github_repo_name).strip()
        self.base_branch = (
            base_branch if base_branch is not None else settings.github_base_branch
        ).strip() or "main"
        self._client = httpx.Client(
            base_url=API_BASE,
            timeout=timeout,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.pat}" if self.pat else "",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "Toolpika-Studio/1.0",
            },
        )

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    @property
    def configured(self) -> bool:
        """Whether all required GitHub settings are present."""
        return bool(self.pat and self.owner and self.repo)

    def require_config(self) -> None:
        """Raise a descriptive error when GitHub settings are missing."""
        missing = [
            name
            for name, value in (
                ("GITHUB_PAT", self.pat),
                ("GITHUB_REPO_OWNER", self.owner),
                ("GITHUB_REPO_NAME", self.repo),
            )
            if not value
        ]
        if missing:
            raise GitHubClientError(
                "GitHub publishing is not configured. Missing: " + ", ".join(missing)
            )

    def _repo_path(self, suffix: str = "") -> str:
        return f"/repos/{self.owner}/{self.repo}{suffix}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        expected: tuple[int, ...] = (200, 201),
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Perform an authenticated request and normalise API errors."""
        if not self.configured:
            self.require_config()
        try:
            response = self._client.request(
                method, self._repo_path(path), params=params, json=payload
            )
        except httpx.HTTPError as exc:
            raise GitHubClientError(f"GitHub request failed: {exc}") from exc

        if response.status_code in {401, 403}:
            log.error(
                "github_authentication_failed",
                status=response.status_code,
                method=method,
                path=path,
                detail=response.text[:300],
            )
            raise GitHubAuthenticationError(
                "GitHub authentication failed. Check GITHUB_PAT and its repository "
                "scopes (Contents, Pull requests, Metadata).",
                status_code=response.status_code,
                body=response.text,
            )

        if response.status_code not in expected:
            log.error(
                "github_api_error",
                status=response.status_code,
                method=method,
                path=path,
                detail=response.text[:300],
            )
            raise GitHubClientError(
                f"GitHub API {method} {path} returned {response.status_code}: "
                f"{response.text[:300]}",
                status_code=response.status_code,
                body=response.text,
            )
        return response

    def get_branch_sha(self, branch: str | None = None) -> str:
        """Return the commit SHA at the tip of a branch."""
        target = branch or self.base_branch
        response = self._request(
            "GET", f"/git/ref/heads/{target}", expected=(200, 404)
        )
        if response.status_code == 404:
            raise GitHubClientError(f"Base branch not found on GitHub: {target}")
        data = response.json()
        sha = str((data.get("object") or {}).get("sha") or "")
        if not sha:
            raise GitHubClientError(f"GitHub returned no SHA for branch {target}")
        return sha

    def branch_exists(self, branch: str) -> bool:
        """Whether a branch already exists."""
        response = self._request(
            "GET", f"/git/ref/heads/{branch}", expected=(200, 404)
        )
        return response.status_code == 200

    def create_branch(self, branch: str, sha: str | None = None) -> None:
        """Create a branch from ``sha`` (defaults to the base branch tip)."""
        commit_sha = sha or self.get_branch_sha()
        response = self._request(
            "POST",
            "/git/refs",
            expected=(201, 422),
            payload={"ref": f"refs/heads/{branch}", "sha": commit_sha},
        )
        if response.status_code == 422:
            raise GitHubBranchExistsError(branch)
        log.info("github_branch_created", branch=branch, base=self.base_branch)

    def get_file(self, path: str, ref: str | None = None) -> tuple[str, str] | None:
        """Return ``(decoded_content, sha)`` for a file, or None when missing."""
        response = self._request(
            "GET",
            f"/contents/{path}",
            expected=(200, 404),
            params={"ref": ref or self.base_branch},
        )
        if response.status_code == 404:
            return None
        data = response.json()
        encoded = str(data.get("content") or "").replace("\n", "")
        try:
            content = base64.b64decode(encoded).decode("utf-8")
        except Exception as exc:  # noqa: BLE001 - corrupted GitHub payload
            raise GitHubClientError(f"Could not decode GitHub file {path}: {exc}") from exc
        return content, str(data.get("sha") or "")

    def create_or_update_file(
        self,
        path: str,
        content: str,
        branch: str,
        message: str,
        sha: str | None = None,
    ) -> dict[str, Any]:
        """Create a file, or update it using the SHA fetched from GitHub."""
        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        response = self._request(
            "PUT", f"/contents/{path}", payload=payload, expected=(200, 201)
        )
        data = response.json()
        log.info("github_file_committed", path=path, branch=branch)
        return {
            "path": path,
            "sha": str((data.get("content") or {}).get("sha") or ""),
            "commit_sha": str((data.get("commit") or {}).get("sha") or ""),
        }

    def create_pull_request(
        self, title: str, head: str, base: str, body: str
    ) -> dict[str, Any]:
        """Open a pull request from ``head`` into ``base``."""
        response = self._request(
            "POST",
            "/pulls",
            expected=(201, 422),
            payload={"title": title, "head": head, "base": base, "body": body[:6000]},
        )
        if response.status_code == 422:
            raise GitHubClientError(
                f"GitHub rejected the pull request: {response.text[:300]}",
                status_code=422,
                body=response.text,
            )
        data = response.json()
        log.info(
            "github_pull_request_created",
            number=data.get("number"),
            url=data.get("html_url"),
        )
        return {
            "number": int(data.get("number") or 0),
            "url": str(data.get("html_url") or ""),
        }

    def merge_pull_request(self, number: int, title: str) -> bool:
        """Squash-merge a PR when auto-merge is enabled. Returns success."""
        if not number:
            return False
        response = self._request(
            "PUT",
            f"/pulls/{number}/merge",
            expected=(200, 405, 409),
            payload={
                "commit_title": title[:200],
                "merge_method": "squash",
            },
        )
        if response.status_code in {405, 409}:
            log.warning(
                "github_auto_merge_skipped",
                number=number,
                status=response.status_code,
                detail=response.text[:200],
            )
            return False
        log.info("github_pull_request_merged", number=number)
        return True

    @staticmethod
    def _slug(slug: str) -> str:
        clean = re.sub(r"[^a-z0-9]+", "-", (slug or "").lower()).strip("-")
        return clean[:50] or "tool"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    def publish(
        self,
        slug: str,
        files: list[dict[str, Any]],
        title: str,
        body: str,
        auto_merge: bool | None = None,
    ) -> dict[str, Any]:
        """Commit ``files`` on a fresh branch and open a pull request.

        If the preferred branch already exists, a timestamp is appended and the
        operation is retried. Existing files are updated with their current SHA.
        """
        self.require_config()
        if not files:
            raise GitHubClientError("No files to publish to GitHub.")

        safe_slug = self._slug(slug)
        branch = f"studio/add-{safe_slug}"
        base_sha = self.get_branch_sha()
        for attempt in range(3):
            try:
                self.create_branch(branch, base_sha)
                break
            except GitHubBranchExistsError:
                if attempt == 2:
                    raise
                branch = f"studio/add-{safe_slug}-{self._timestamp()}-{attempt + 1}"

        committed: list[dict[str, Any]] = []
        for item in files:
            path = str(item["path"])
            content = str(item["content"])
            remote = self.get_file(path, branch)
            sha = remote[1] if remote else None
            committed.append(
                self.create_or_update_file(
                    path=path,
                    content=content,
                    branch=branch,
                    message=f"studio: add {safe_slug} tool ({path})",
                    sha=sha,
                )
            )

        pr = self.create_pull_request(title, branch, self.base_branch, body)
        should_merge = (
            settings.studio_auto_merge_pr if auto_merge is None else auto_merge
        )
        merged = False
        if should_merge:
            merged = self.merge_pull_request(pr["number"], title)

        result = {
            "success": True,
            "applied": True,
            "branch": branch,
            "base_branch": self.base_branch,
            "pr_number": pr["number"],
            "pr_url": pr["url"],
            "merged": merged,
            "files": [str(item["path"]) for item in files],
            "commits": committed,
        }
        log.info(
            "studio_github_publish_succeeded",
            slug=safe_slug,
            branch=branch,
            pr_url=pr["url"],
        )
        return result
