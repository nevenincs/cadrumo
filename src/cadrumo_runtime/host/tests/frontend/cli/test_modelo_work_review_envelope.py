"""Envelope contract for the canonical modelo work review record."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from cadrumo.adapters.persistence.storage.secure_object_namespaces import (
    MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
)
from cadrumo.adapters.persistence.storage.sql.orm import SecureObjectRow
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    mutate_encrypted_secure_object_json,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.cli.tests.review_envelope_support import (
    RAW_ROW_IDENTITY,
    ROW_FINGERPRINT,
    persist_blocked_review,
)

from .portable_human_cli_runtime import portable_human_cli_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _orphan_row_source_identity(document: dict[str, Any]) -> None:
    revision = next(iter(document["payload"]["revisions"].values()))
    identity = revision["row_source_identities"][0]
    assert identity["source_row_identity"] == RAW_ROW_IDENTITY
    assert identity["fingerprint"] == ROW_FINGERPRINT
    identity["row_index"] = 2
    assert identity["source_row_identity"] == RAW_ROW_IDENTITY
    assert identity["fingerprint"] == ROW_FINGERPRINT


def test_runtime_review_command_redacts_identity_in_success_and_mutated_record_refusal(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, *, authority_operation: PinnedAuthorityOperation
) -> None:
    with (
        persist_blocked_review(tmp_path, operation=authority_operation) as seeded,
        portable_human_cli_runtime(
            storage_root=seeded.storage_root, profile_id=seeded.profile_id, label=seeded.label
        ) as runtime,
    ):
        review, objects = seeded.review, seeded.objects
        command = runtime.invoke(
            ["--format", "json", "app", "modelo", "work", "review", review.work_unit_id],
        )
        assert command.exit_code == 0, command.output
        command_surface = f"{command.stdout} {command.stderr} {command.exception!r}"
        assert RAW_ROW_IDENTITY not in command_surface
        assert ROW_FINGERPRINT not in command.stdout
        assert RAW_ROW_IDENTITY not in caplog.text

        mutate_encrypted_secure_object_json(
            objects._engine,
            row_statement=select(SecureObjectRow).where(
                SecureObjectRow.namespace == MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace,
                SecureObjectRow.object_key
                == MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.require_default_object_key(),
            ),
            mutate=_orphan_row_source_identity,
        )
        failed = runtime.invoke(
            ["--format", "json", "app", "modelo", "work", "review", review.work_unit_id],
        )
        assert failed.exit_code != 0
        formatted = "" if failed.exception is None else "".join(traceback.format_exception(failed.exception))
        failure_surface = f"{failed.stdout} {failed.stderr} {failed.exception!r} {formatted} {caplog.text}"
        assert RAW_ROW_IDENTITY not in failure_surface
        assert ROW_FINGERPRINT not in failure_surface
