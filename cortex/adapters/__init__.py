"""Adapter registry: maps a source `type` to its adapter class."""

from __future__ import annotations

from .base import Adapter, SourceSkipped
from .figma import FigmaAdapter
from .github import GitHubAdapter
from .jira import JiraAdapter

ADAPTERS: dict[str, type[Adapter]] = {
    JiraAdapter.type: JiraAdapter,
    FigmaAdapter.type: FigmaAdapter,
    GitHubAdapter.type: GitHubAdapter,
}

__all__ = ["ADAPTERS", "Adapter", "SourceSkipped"]
