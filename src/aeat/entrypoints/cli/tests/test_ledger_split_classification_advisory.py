"""Real-behavior suite for the ``ledger split`` classification-dropped advisory.

Splitting a parent transaction deliberately resets every child to
``NOT_YET_PROCESSED`` to force conscious per-row tax treatment; the parent's
classification is not cloned. That drop is a non-blocking advisory, not a silent
side-effect (per ``no-silent-under-declaration`` /
``cli-notices-are-the-only-diagnostic-channel``): when the parent carried a real
classified outcome (BUSINESS / PERSONAL / MIXED) the split emits an ``info``
notice naming the dropped classification and pointing at ``ledger classify``.

Every test drives the real ``aeat app ledger`` CLI against an isolated profile
bucket through the real persistence stack — no mocks, no stubs, no skips.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        try:
            workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
            yield
        finally:
            dispose_engine()


def _add_row(*, amount: str, description: str, idempotency_key: str) -> str:
    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-02",
            "--amount",
            amount,
            "--direction",
            "OUTGOING",
            "--description",
            description,
            "--counterparty",
            "Proveedor SL",
            "--idempotency-key",
            idempotency_key,
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["result"]["transaction_id"]


def _classify_business(transaction_id: str) -> None:
    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "classify", transaction_id, "--classification", "BUSINESS"],
    )
    assert result.exit_code == 0, result.output


def _split_json(parent: str) -> dict:
    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "split",
            parent,
            "--child-amount",
            "40.00",
            "--child-description",
            "parte A",
            "--child-amount",
            "60.00",
            "--child-description",
            "parte B",
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_split_of_classified_parent_emits_dropped_classification_advisory() -> None:
    """A classified parent yields a notice naming the dropped classification."""
    parent = _add_row(amount="100.00", description="Subcontratacion", idempotency_key="row-1")
    _classify_business(parent)

    envelope = _split_json(parent)

    assert envelope["status"] == "success"
    notices = envelope["notices"]
    (notice,) = [n for n in notices if n["code"] == "ledger.split.classification_dropped"]
    assert notice["severity"] == "info"
    assert "BUSINESS" in notice["message"]
    assert "classify" in notice["suggestion"]
    assert notice["context"]["parent_classification"] == "BUSINESS"


def test_split_of_unclassified_parent_emits_no_dropped_classification_advisory() -> None:
    """A never-classified parent (NOT_YET_PROCESSED) drops nothing, so no notice."""
    parent = _add_row(amount="100.00", description="Subcontratacion", idempotency_key="row-2")

    envelope = _split_json(parent)

    codes = {n["code"] for n in envelope["notices"]}
    assert "ledger.split.classification_dropped" not in codes


def test_split_classification_advisory_folds_into_text_lines() -> None:
    """The advisory rides text output too, so JSON and text cannot drift."""
    parent = _add_row(amount="100.00", description="Subcontratacion", idempotency_key="row-3")
    _classify_business(parent)

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "split",
            parent,
            "--child-amount",
            "40.00",
            "--child-description",
            "parte A",
            "--child-amount",
            "60.00",
            "--child-description",
            "parte B",
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "ADVISORY" in result.output
    assert "BUSINESS" in result.output
