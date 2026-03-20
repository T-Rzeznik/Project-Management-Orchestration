"""Tests for LangChain tool wrappers."""

from unittest.mock import patch, MagicMock

import pytest

from tools.langchain_tools import read_github_repo, create_project, read_repo_file


class TestReadGithubRepo:
    def test_returns_repo_data(self):
        fake_data = {
            "owner": "pallets",
            "repo": "flask",
            "name": "flask",
            "description": "A micro framework",
            "stars": 65000,
        }
        with patch("tools.langchain_tools.fetch_repo_data", return_value=fake_data):
            result = read_github_repo.invoke({"github_url": "pallets/flask"})

        assert result["owner"] == "pallets"
        assert result["name"] == "flask"

    def test_propagates_errors(self):
        with patch(
            "tools.langchain_tools.fetch_repo_data",
            side_effect=ValueError("Cannot parse"),
        ):
            with pytest.raises(ValueError, match="Cannot parse"):
                read_github_repo.invoke({"github_url": "bad"})

    def test_is_langchain_tool(self):
        from langchain_core.tools import BaseTool
        assert isinstance(read_github_repo, BaseTool)

    def test_has_correct_name(self):
        assert read_github_repo.name == "read_github_repo"


class TestCreateProject:
    @pytest.fixture(autouse=True)
    def clean_storage(self, tmp_path, monkeypatch):
        from api import storage
        monkeypatch.setattr(storage, "DB_PATH", tmp_path / "test.db")
        storage._init_db()

    def test_creates_project_with_name(self):
        result = create_project.invoke({"name": "My Project"})
        assert result["status"] == "created"
        assert result["name"] == "My Project"
        assert "project_id" in result

    def test_saves_to_storage(self):
        from api import storage
        create_project.invoke({"name": "Saved Project"})
        projects = storage.list_projects()
        assert len(projects) == 1
        assert projects[0]["name"] == "Saved Project"

    def test_sets_defaults(self):
        from api import storage
        create_project.invoke({"name": "Defaults"})
        project = storage.list_projects()[0]
        assert project["status"] == "active"
        assert project["tech_stack"] == []
        assert project["tasks"] == []

    def test_accepts_full_fields(self):
        from api import storage
        result = create_project.invoke({
            "name": "Full",
            "description": "A full project",
            "tech_stack": ["Python", "React"],
            "github_url": "https://github.com/a/b",
            "tasks": [
                {"title": "Task 1", "description": "Do thing", "priority": "high", "status": "todo"},
            ],
            "milestones": [{"title": "v1.0", "description": "First release"}],
        })
        assert result["name"] == "Full"
        project = storage.list_projects()[0]
        assert project["description"] == "A full project"
        assert project["tech_stack"] == ["Python", "React"]
        assert len(project["tasks"]) == 1
        assert project["tasks"][0]["title"] == "Task 1"

    def test_is_langchain_tool(self):
        from langchain_core.tools import BaseTool
        assert isinstance(create_project, BaseTool)

    def test_has_correct_name(self):
        assert create_project.name == "create_project"


class TestReadRepoFile:
    def test_returns_file_content(self):
        with patch("tools.langchain_tools.fetch_file_content", return_value="print('hello')"):
            result = read_repo_file.invoke({
                "owner": "pallets",
                "repo": "flask",
                "path": "src/flask/app.py",
            })
        assert result == "print('hello')"

    def test_passes_args_to_fetch(self):
        with patch("tools.langchain_tools.fetch_file_content", return_value="content") as mock_fetch:
            read_repo_file.invoke({
                "owner": "myorg",
                "repo": "myrepo",
                "path": "README.md",
            })
        mock_fetch.assert_called_once_with("myorg", "myrepo", "README.md")

    def test_returns_empty_on_missing_file(self):
        with patch("tools.langchain_tools.fetch_file_content", return_value=""):
            result = read_repo_file.invoke({
                "owner": "pallets",
                "repo": "flask",
                "path": "nonexistent.py",
            })
        assert result == ""

    def test_is_langchain_tool(self):
        from langchain_core.tools import BaseTool
        assert isinstance(read_repo_file, BaseTool)

    def test_has_correct_name(self):
        assert read_repo_file.name == "read_repo_file"
