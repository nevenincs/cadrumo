"""Lazy workflow-repository resolution shared by authentication services."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..workflow import WorkflowStateRepository


def workflow_state_repository() -> WorkflowStateRepository:
    """Resolve the public workflow repository without an auth import cycle."""
    workflow = import_module("cadrumo.application.workflow")
    factory = workflow.workflow_state_repository
    return factory()
