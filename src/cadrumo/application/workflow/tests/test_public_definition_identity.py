"""Runtime ownership proofs for every public workflow defining module."""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType

import pytest

import cadrumo.application.workflow.abort as abort
import cadrumo.application.workflow.active_profile as active_profile
import cadrumo.application.workflow.adapters as adapters
import cadrumo.application.workflow.engine as engine
import cadrumo.application.workflow.engine_helpers as engine_helpers
import cadrumo.application.workflow.engine_recording as engine_recording
import cadrumo.application.workflow.errors as errors
import cadrumo.application.workflow.events as events
import cadrumo.application.workflow.persistence as persistence
import cadrumo.application.workflow.profile_bucket_models as profile_bucket_models
import cadrumo.application.workflow.profile_bucket_scan as profile_bucket_scan
import cadrumo.application.workflow.profile_health as profile_health
import cadrumo.application.workflow.protocols as protocols
import cadrumo.application.workflow.resume as resume
import cadrumo.application.workflow.review_models as review_models
import cadrumo.application.workflow.run_models as run_models
import cadrumo.application.workflow.state_models as state_models

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PUBLIC_DEFINING_MODULES: tuple[ModuleType, ...] = (
    abort,
    active_profile,
    adapters,
    engine,
    engine_helpers,
    engine_recording,
    errors,
    events,
    persistence,
    profile_bucket_models,
    profile_bucket_scan,
    profile_health,
    protocols,
    resume,
    review_models,
    run_models,
    state_models,
)


def _imported_names(module: ModuleType) -> frozenset[str]:
    """Return names imported into a module namespace by its source file."""
    source_path = Path(module.__file__ or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return frozenset(names)


@pytest.mark.parametrize("module", _PUBLIC_DEFINING_MODULES, ids=lambda module: module.__name__)
def test_every_public_workflow_export_has_runtime_identity_at_its_defining_module(module: ModuleType) -> None:
    """Every listed workflow contract is defined here, never re-exported."""
    exported = tuple(module.__all__)
    assert exported
    assert len(exported) == len(set(exported))

    missing = [name for name in exported if name not in vars(module)]
    assert missing == []

    foreign_runtime_exports = {
        name: getattr(getattr(module, name), "__module__", None)
        for name in exported
        if getattr(getattr(module, name), "__module__", None) not in (None, module.__name__)
    }
    assert foreign_runtime_exports == {}

    foreign_static_exports = sorted(set(exported) & _imported_names(module))
    assert foreign_static_exports == []
