"""Tests for SQLite-backed project storage."""

import json

import pytest

from api import storage


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point storage at a temp SQLite DB so tests don't touch real data."""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "test.db")
    storage._init_db()


class TestInitDb:
    def test_creates_table(self):
        """_init_db should create the projects table without error."""
        # If we get here, the autouse fixture already succeeded
        assert storage.list_projects() == []

    def test_idempotent(self):
        """Calling _init_db twice should not raise."""
        storage._init_db()
        assert storage.list_projects() == []


class TestSaveProject:
    def test_save_and_retrieve(self):
        project = {"id": "p1", "name": "Alpha", "status": "active"}
        storage.save_project(project)
        result = storage.get_project("p1")
        assert result is not None
        assert result["name"] == "Alpha"
        assert result["status"] == "active"

    def test_save_returns_project(self):
        project = {"id": "p2", "name": "Beta"}
        returned = storage.save_project(project)
        assert returned["id"] == "p2"
        assert returned["name"] == "Beta"

    def test_update_existing(self):
        """save_project with same id should update, not duplicate."""
        storage.save_project({"id": "p1", "name": "Original"})
        storage.save_project({"id": "p1", "name": "Updated"})
        projects = storage.list_projects()
        assert len(projects) == 1
        assert projects[0]["name"] == "Updated"


class TestListProjects:
    def test_empty_initially(self):
        assert storage.list_projects() == []

    def test_lists_all_saved(self):
        storage.save_project({"id": "a", "name": "A"})
        storage.save_project({"id": "b", "name": "B"})
        projects = storage.list_projects()
        assert len(projects) == 2
        names = {p["name"] for p in projects}
        assert names == {"A", "B"}


class TestGetProject:
    def test_returns_none_for_missing(self):
        assert storage.get_project("nonexistent") is None

    def test_returns_correct_project(self):
        storage.save_project({"id": "x", "name": "X"})
        storage.save_project({"id": "y", "name": "Y"})
        result = storage.get_project("y")
        assert result["name"] == "Y"


class TestDeleteProject:
    def test_delete_existing(self):
        storage.save_project({"id": "d1", "name": "Doomed"})
        assert storage.delete_project("d1") is True
        assert storage.get_project("d1") is None

    def test_delete_nonexistent_returns_false(self):
        assert storage.delete_project("ghost") is False

    def test_delete_does_not_affect_others(self):
        storage.save_project({"id": "keep", "name": "Keep"})
        storage.save_project({"id": "drop", "name": "Drop"})
        storage.delete_project("drop")
        projects = storage.list_projects()
        assert len(projects) == 1
        assert projects[0]["name"] == "Keep"


class TestComplexData:
    def test_preserves_nested_structures(self):
        """Projects with tasks, lists, etc. should round-trip through JSON."""
        project = {
            "id": "complex",
            "name": "Complex",
            "tech_stack": ["Python", "React"],
            "tasks": [
                {"id": "t1", "title": "Task 1", "status": "todo"},
                {"id": "t2", "title": "Task 2", "status": "done"},
            ],
            "milestones": [{"title": "v1.0", "description": "First release"}],
        }
        storage.save_project(project)
        result = storage.get_project("complex")
        assert result["tech_stack"] == ["Python", "React"]
        assert len(result["tasks"]) == 2
        assert result["tasks"][0]["title"] == "Task 1"
        assert result["milestones"][0]["title"] == "v1.0"
