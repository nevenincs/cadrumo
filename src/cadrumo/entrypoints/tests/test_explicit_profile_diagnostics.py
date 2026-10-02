"""Exact-profile diagnostics for a workbench with two live bucket capsules."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage.errors import StorageValidationError
from ...adapters.persistence.storage.secure_object_namespaces import SECURE_OBJECT_WORKFLOW_STATE_KEY
from ...adapters.persistence.storage.tests.secure_sql import isolated_two_bucket_runtime
from ...application.diagnostics import secure_object_unreadable_total
from ...core.classification.policies import SensitivityClass
from ..adapter_composition import build_diagnostics_ports, build_state_projection_read_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PRIMARY = "a1470000-0000-4000-8000-000000000001"
_SECONDARY = "a1470000-0000-4000-8000-000000000002"
_NAMESPACE = "cadrumo.workflow"


def test_workbench_diagnostics_follow_explicit_profile_and_refuse_another_active_session(tmp_path: Path) -> None:
    """A broken secondary row cannot be counted from the primary or served with its key."""
    with isolated_two_bucket_runtime(
        tmp_path=tmp_path,
        primary_bucket_id=_PRIMARY,
        secondary_bucket_id=_SECONDARY,
    ) as runtime:
        with runtime.switch_to_secondary():
            runtime.secondary.repository.save(
                namespace=_NAMESPACE,
                object_key=SECURE_OBJECT_WORKFLOW_STATE_KEY,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=b"secondary diagnostic witness",
            )

        with sqlite3.connect(runtime.secondary.paths.database_file) as database:
            row_id, payload = database.execute(
                "SELECT id, payload FROM secure_objects WHERE namespace = ?",
                (_NAMESPACE,),
            ).fetchone()
            database.execute(
                "UPDATE secure_objects SET payload = ? WHERE id = ?",
                (payload[:-1] + bytes([payload[-1] ^ 0xFF]), row_id),
            )

        primary_ports = build_state_projection_read_ports(diagnostics_ports=build_diagnostics_ports(bucket_id=_PRIMARY))
        assert primary_ports.workspace.read_workspace(bucket_id=_PRIMARY).unreadable_rows == 0

        secondary_diagnostics = build_diagnostics_ports(bucket_id=_SECONDARY)
        with pytest.raises(StorageValidationError):
            secondary_diagnostics.secure_object_repository.list_namespaces()

        with runtime.switch_to_secondary():
            secondary_ports = build_state_projection_read_ports(diagnostics_ports=secondary_diagnostics)
            assert secure_object_unreadable_total(ports=secondary_diagnostics) == 1
            assert secondary_ports.workspace.read_workspace(bucket_id=_SECONDARY).unreadable_rows == 1
