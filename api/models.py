"""Pydantic models for the Project Management API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Task(BaseModel):
    title: str
    description: str
    priority: str = "medium"  # high | medium | low
    status: str = "todo"      # todo | in-progress | done


class Milestone(BaseModel):
    title: str
    description: str


class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    github_url: str = ""
    name: str
    description: str = ""
    documentation: str = ""
    summary: str = ""
    tech_stack: List[str] = []
    stars: int = 0
    language: str = ""
    open_issues_count: int = 0
    contributors: List[str] = []
    tasks: List[Task] = []
    milestones: List[Milestone] = []
    status: str = "active"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    tech_stack: List[str] = []
    github_url: str = ""
    documentation: str = ""


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tech_stack: Optional[List[str]] = None
    github_url: Optional[str] = None
    documentation: Optional[str] = None
    status: Optional[str] = None


class AnalyzeRequest(BaseModel):
    github_url: str
