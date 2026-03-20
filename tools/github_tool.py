"""GitHub tool — fetch public repo data via REST API (no auth required)."""

from __future__ import annotations

import re

import httpx

_GITHUB_URL_RE = re.compile(r"github\.com/([^/]+)/([^/\s?#]+)")
_OWNER_REPO_RE = re.compile(r"^([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)$")

_README_MAX_CHARS = 10_000
_TIMEOUT = 15
_TREE_MAX_PATHS = 500


def parse_github_identifier(value: str) -> tuple[str, str]:
    """Parse a GitHub URL or 'owner/repo' string into (owner, repo)."""
    value = value.strip()
    if not value:
        raise ValueError("Empty GitHub identifier")

    m = _GITHUB_URL_RE.search(value)
    if m:
        owner = m.group(1)
        repo = m.group(2).rstrip("/").removesuffix(".git")
        return owner, repo

    m = _OWNER_REPO_RE.match(value)
    if m:
        return m.group(1), m.group(2)

    raise ValueError(f"Cannot parse GitHub identifier: {value}")


def _fetch_repo_tree(owner: str, repo: str) -> list[str]:
    """Fetch the repo file tree via Git Trees API. Returns flat list of file paths."""
    try:
        resp = httpx.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1",
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        paths = [
            entry["path"]
            for entry in data.get("tree", [])
            if entry.get("type") == "blob"
        ]
        return paths[:_TREE_MAX_PATHS]
    except (httpx.HTTPError, KeyError):
        return []


def _fetch_file_content(owner: str, repo: str, path: str, max_chars: int = 10_000) -> str:
    """Fetch raw file content from a repo. Returns empty string on failure."""
    try:
        resp = httpx.get(
            f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}",
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return ""
        return resp.text[:max_chars]
    except httpx.HTTPError:
        return ""


# Public alias so LangChain tools can import without reaching into a private name.
fetch_file_content = _fetch_file_content


_MANIFEST_FILES = {
    "package.json", "requirements.txt", "setup.py", "pyproject.toml",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "Gemfile", "composer.json", "Makefile", "Dockerfile",
    "tsconfig.json",
}

_MAX_MANIFESTS = 5


def _detect_and_fetch_manifests(owner: str, repo: str, tree: list[str]) -> dict[str, str]:
    """Detect root-level manifest files in tree and fetch their contents."""
    manifests: dict[str, str] = {}
    for path in tree:
        # Only root-level files (no '/' in path)
        if "/" in path:
            continue
        if path not in _MANIFEST_FILES:
            continue
        content = _fetch_file_content(owner, repo, path)
        if content:
            manifests[path] = content
        if len(manifests) >= _MAX_MANIFESTS:
            break
    return manifests


def fetch_repo_data(github_input: str) -> dict:
    """Fetch public repo data from GitHub REST API. Returns a rich dict."""
    owner, repo = parse_github_identifier(github_input)

    # 1. Repo metadata
    resp = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        timeout=_TIMEOUT,
    )
    if resp.status_code == 404:
        raise ValueError(f"Repository {owner}/{repo} not found")
    resp.raise_for_status()
    meta = resp.json()

    # 2. Languages
    lang_resp = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}/languages",
        timeout=_TIMEOUT,
    )
    languages = lang_resp.json() if lang_resp.status_code == 200 else {}

    # 3. Contributors (top 10)
    contrib_resp = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}/contributors?per_page=10",
        timeout=_TIMEOUT,
    )
    contributors = (
        [c["login"] for c in contrib_resp.json()]
        if contrib_resp.status_code == 200
        else []
    )

    # 4. README
    readme_resp = httpx.get(
        f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md",
        timeout=_TIMEOUT,
    )
    readme_content = (
        readme_resp.text[:_README_MAX_CHARS]
        if readme_resp.status_code == 200
        else ""
    )

    # 5. Open issues (exclude PRs)
    issues_resp = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=10",
        timeout=_TIMEOUT,
    )
    all_issues = issues_resp.json() if issues_resp.status_code == 200 else []
    recent_issues = [
        {"title": i["title"], "number": i["number"]}
        for i in all_issues
        if i.get("pull_request") is None
    ]

    # 6. File tree
    file_tree = _fetch_repo_tree(owner, repo)

    # 7. Auto-detect and fetch manifest/config files
    manifest_contents = _detect_and_fetch_manifests(owner, repo, file_tree)

    return {
        "owner": owner,
        "repo": repo,
        "name": meta.get("name", repo),
        "description": meta.get("description") or "",
        "stars": meta.get("stargazers_count", 0),
        "primary_language": meta.get("language") or "",
        "open_issues_count": meta.get("open_issues_count", 0),
        "languages": languages,
        "contributors": contributors,
        "readme_content": readme_content,
        "recent_issues": recent_issues,
        "topics": meta.get("topics", []),
        "html_url": meta.get("html_url", ""),
        "file_tree": file_tree,
        "manifest_contents": manifest_contents,
    }
