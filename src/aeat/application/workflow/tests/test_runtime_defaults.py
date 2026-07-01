"""Runtime-default guards for workflow persistence repositories."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from ....adapters.persistence.storage.errors import StorageValidationError
from ....adapters.persistence.storage.sql import dispose_engine
from ....core.config import override_settings
from .._persistence import WorkflowRunRepository, workflow_state_repository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    "repository_factory",
    (
        pytest.param(workflow_state_repository, id="workflow-state"),
        pytest.param(WorkflowRunRepository, id="workflow-run"),
    ),
)
def test_workflow_defaults_refuse_explicit_database_without_active_profile(
    tmp_path: Path,
    repository_factory: Callable[[], object],
) -> None:
    """An explicit SQL URL must not revive pre-runtime workflow persistence defaults."""

    explicit_db = tmp_path / "explicit.db"
    with override_settings(
        aeat_local_storage_root=tmp_path / "storage",
        aeat_active_profile=None,
        aeat_database_url=f"sqlite:///{explicit_db.as_posix()}",
    ) as settings:
        dispose_engine(settings)
        try:
            with pytest.raises(StorageValidationError) as exc_info:
                repository_factory()
            assert exc_info.value.translated_message == "errors.storage.runtime.not_ready"
        finally:
            dispose_engine(settings)

    assert not explicit_db.exists()
