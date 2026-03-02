"""Tests for the GitHub tool (parse + fetch)."""

from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from tools.github_tool import (
    parse_github_identifier,
    fetch_repo_data,
    _fetch_repo_tree,
    _fetch_file_content,
    _detect_and_fetch_manifests,
)


# --- parse_github_identifier ---


class TestParseGithubIdentifier:
    def test_full_url(self):
        owner, repo = parse_github_identifier("https://github.com/pallets/flask")
        assert owner == "pallets"
        assert repo == "flask"

    def test_full_url_with_trailing_slash(self):
        owner, repo = parse_github_identifier("https://github.com/pallets/flask/")
        assert owner == "pallets"
        assert repo == "flask"

    def test_full_url_with_git_suffix(self):
        owner, repo = parse_github_identifier("https://github.com/pallets/flask.git")
        assert owner == "pallets"
        assert repo == "flask"

    def test_owner_repo_string(self):
        owner, repo = parse_github_identifier("pallets/flask")
        assert owner == "pallets"
        assert repo == "flask"

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            parse_github_identifier("not-a-repo")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_github_identifier("")


# --- fetch_repo_data ---


def _mock_response(status_code: int, json_data=None, text: str = ""):
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp,
        )
    return resp


class TestFetchRepoData:
    def test_success(self):
        repo_json = {
            "name": "flask",
            "description": "A micro web framework",
            "stargazers_count": 65000,
            "language": "Python",
            "open_issues_count": 20,
            "topics": ["web", "python"],
            "html_url": "https://github.com/pallets/flask",
        }
        langs_json = {"Python": 90000, "HTML": 5000}
        contribs_json = [{"login": "alice"}, {"login": "bob"}]
        issues_json = [
            {"title": "Bug A", "number": 1, "pull_request": None},
            {"title": "PR X", "number": 2, "pull_request": {"url": "..."}},
        ]

        def mock_get(url, **kwargs):
            if "/repos/pallets/flask/languages" in url:
                return _mock_response(200, langs_json)
            if "/repos/pallets/flask/contributors" in url:
                return _mock_response(200, contribs_json)
            if "/repos/pallets/flask/issues" in url:
                return _mock_response(200, issues_json)
            if "raw.githubusercontent.com" in url:
                return _mock_response(200, text="# Flask\nA micro framework.")
            # Default: repo metadata
            return _mock_response(200, repo_json)

        with patch("tools.github_tool.httpx.get", side_effect=mock_get):
            result = fetch_repo_data("pallets/flask")

        assert result["owner"] == "pallets"
        assert result["repo"] == "flask"
        assert result["name"] == "flask"
        assert result["description"] == "A micro web framework"
        assert result["stars"] == 65000
        assert result["primary_language"] == "Python"
        assert result["open_issues_count"] == 20
        assert result["languages"] == {"Python": 90000, "HTML": 5000}
        assert result["contributors"] == ["alice", "bob"]
        assert "Flask" in result["readme_content"]
        assert result["topics"] == ["web", "python"]
        assert result["html_url"] == "https://github.com/pallets/flask"
        # Issues should exclude PRs
        assert len(result["recent_issues"]) == 1
        assert result["recent_issues"][0]["title"] == "Bug A"

    def test_readme_404_returns_empty_string(self):
        repo_json = {
            "name": "tiny",
            "description": "",
            "stargazers_count": 0,
            "language": None,
            "open_issues_count": 0,
            "topics": [],
            "html_url": "https://github.com/owner/tiny",
        }

        def mock_get(url, **kwargs):
            if "raw.githubusercontent.com" in url:
                return _mock_response(404)
            if "/languages" in url:
                return _mock_response(200, {})
            if "/contributors" in url:
                return _mock_response(200, [])
            if "/issues" in url:
                return _mock_response(200, [])
            return _mock_response(200, repo_json)

        with patch("tools.github_tool.httpx.get", side_effect=mock_get):
            result = fetch_repo_data("owner/tiny")

        assert result["readme_content"] == ""

    def test_repo_not_found_raises(self):
        with patch(
            "tools.github_tool.httpx.get",
            return_value=_mock_response(404),
        ):
            with pytest.raises(ValueError, match="not found"):
                fetch_repo_data("owner/nonexistent")


# --- _fetch_repo_tree ---


class TestFetchRepoTree:
    def test_success(self):
        tree_json = {
            "tree": [
                {"path": "src/index.ts", "type": "blob"},
                {"path": "src", "type": "tree"},
                {"path": "package.json", "type": "blob"},
            ],
            "truncated": False,
        }

        with patch(
            "tools.github_tool.httpx.get",
            return_value=_mock_response(200, tree_json),
        ):
            result = _fetch_repo_tree("owner", "repo")

        # Should only include blobs, not tree entries
        assert result == ["src/index.ts", "package.json"]

    def test_404_returns_empty(self):
        with patch(
            "tools.github_tool.httpx.get",
            return_value=_mock_response(404),
        ):
            result = _fetch_repo_tree("owner", "repo")

        assert result == []


# --- _fetch_file_content ---


class TestFetchFileContent:
    def test_success(self):
        with patch(
            "tools.github_tool.httpx.get",
            return_value=_mock_response(200, text='{"name": "my-app"}'),
        ):
            result = _fetch_file_content("owner", "repo", "package.json")

        assert result == '{"name": "my-app"}'

    def test_truncates_to_max_chars(self):
        long_text = "x" * 200
        with patch(
            "tools.github_tool.httpx.get",
            return_value=_mock_response(200, text=long_text),
        ):
            result = _fetch_file_content("owner", "repo", "big.txt", max_chars=50)

        assert len(result) == 50

    def test_404_returns_empty(self):
        with patch(
            "tools.github_tool.httpx.get",
            return_value=_mock_response(404),
        ):
            result = _fetch_file_content("owner", "repo", "missing.txt")

        assert result == ""


# --- _detect_and_fetch_manifests ---


class TestDetectAndFetchManifests:
    def test_finds_root_package_json(self):
        tree = ["src/index.ts", "package.json", "README.md"]

        with patch(
            "tools.github_tool._fetch_file_content",
            return_value='{"name": "app"}',
        ) as mock_fetch:
            result = _detect_and_fetch_manifests("owner", "repo", tree)

        assert "package.json" in result
        assert result["package.json"] == '{"name": "app"}'
        mock_fetch.assert_called_once_with("owner", "repo", "package.json")

    def test_skips_nested_manifests(self):
        tree = ["node_modules/foo/package.json", "vendor/composer.json", "src/index.ts"]

        with patch(
            "tools.github_tool._fetch_file_content",
            return_value="content",
        ) as mock_fetch:
            result = _detect_and_fetch_manifests("owner", "repo", tree)

        assert result == {}
        mock_fetch.assert_not_called()

    def test_caps_at_five(self):
        # 7 root-level manifests — only first 5 should be fetched
        tree = [
            "package.json", "requirements.txt", "setup.py",
            "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml",
        ]

        with patch(
            "tools.github_tool._fetch_file_content",
            return_value="content",
        ):
            result = _detect_and_fetch_manifests("owner", "repo", tree)

        assert len(result) == 5


# --- fetch_repo_data integration (new fields) ---


class TestFetchRepoDataNewFields:
    """Verify fetch_repo_data includes file_tree and manifest_contents."""

    _REPO_JSON = {
        "name": "myapp",
        "description": "A cool app",
        "stargazers_count": 10,
        "language": "TypeScript",
        "open_issues_count": 0,
        "topics": [],
        "html_url": "https://github.com/owner/myapp",
    }

    _TREE_JSON = {
        "tree": [
            {"path": "src/index.ts", "type": "blob"},
            {"path": "src", "type": "tree"},
            {"path": "package.json", "type": "blob"},
            {"path": "tsconfig.json", "type": "blob"},
        ],
        "truncated": False,
    }

    def _mock_get(self, url, **kwargs):
        if "/git/trees/" in url:
            return _mock_response(200, self._TREE_JSON)
        if "/repos/owner/myapp/languages" in url:
            return _mock_response(200, {"TypeScript": 9000})
        if "/repos/owner/myapp/contributors" in url:
            return _mock_response(200, [])
        if "/repos/owner/myapp/issues" in url:
            return _mock_response(200, [])
        if "raw.githubusercontent.com" in url:
            if "package.json" in url:
                return _mock_response(200, text='{"name":"myapp"}')
            if "tsconfig.json" in url:
                return _mock_response(200, text='{"compilerOptions":{}}')
            # README
            return _mock_response(404)
        return _mock_response(200, self._REPO_JSON)

    def test_includes_file_tree(self):
        with patch("tools.github_tool.httpx.get", side_effect=self._mock_get):
            result = fetch_repo_data("owner/myapp")

        assert "file_tree" in result
        assert "src/index.ts" in result["file_tree"]
        assert "package.json" in result["file_tree"]
        # tree entries (directories) should be excluded
        assert "src" not in result["file_tree"]

    def test_includes_manifest_contents(self):
        with patch("tools.github_tool.httpx.get", side_effect=self._mock_get):
            result = fetch_repo_data("owner/myapp")

        assert "manifest_contents" in result
        assert "package.json" in result["manifest_contents"]
        assert '"myapp"' in result["manifest_contents"]["package.json"]
