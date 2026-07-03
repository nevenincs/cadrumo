"""Behaviour gate for the ``aeat app contract`` capability manifest command.

Asserts the read-only manifest command surfaces the full operator-surface
contract through the shared :class:`SchemaEnvelope`: both roots, every mounted
command family with its mutability and intent, the ``CALCULATE -> VERIFY -> FILE``
lifecycle, and a non-empty registered-command-schema index that includes the
command's own ``contract`` key. The expected shape is grounded in the
authoritative backend contract (``build_operator_surface_contract``) rather than
hand-enumerated, so the gate fails if the manifest drops or distorts any family.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....application.operator_surface import (
    OperatorMutability,
    build_operator_surface_contract,
)
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_sessionless_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path) -> Iterator[None]:
    # The command is read-only and session-free, but storage isolation
    # keeps the run off any shared local-state root.
    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        yield


def _manifest() -> dict[str, object]:
    result = invoke_cached_cli(["--format", "json", "app", "contract"])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "contract"
    assert envelope["status"] == "success"
    return envelope["result"]


def test_manifest_envelope_is_a_success_document() -> None:
    manifest = _manifest()
    assert manifest["manifest_version"] == "1"
    assert manifest["envelope_schema_version"] == "2"
    assert {"contract", "command_schemas"} <= set(manifest)


def test_manifest_carries_both_pinned_roots() -> None:
    contract = _manifest()["contract"]
    root_names = [root["name"] for root in contract["roots"]]
    assert root_names == ["config", "app"]


def test_manifest_lifecycle_is_calculate_verify_file() -> None:
    contract = _manifest()["contract"]
    steps = contract["lifecycle"]["steps"]
    assert steps == ["calculate", "verify", "file"]
    assert contract["lifecycle"]["live_submission_enabled"] is False


def test_manifest_covers_every_command_family_with_mutability() -> None:
    contract = _manifest()["contract"]
    families = contract["command_families"]
    expected = build_operator_surface_contract().command_families
    assert len(families) == len(expected)

    valid_mutabilities = {member.value for member in OperatorMutability}
    by_child = {family["child"]: family for family in families}
    for source in expected:
        emitted = by_child[source.child]
        assert emitted["mutability"] in valid_mutabilities
        assert emitted["mutability"] == source.mutability.value
        assert emitted["operator_question"] == source.operator_question
        assert emitted["service_owner"] == source.service_owner


def test_manifest_command_schema_index_includes_self() -> None:
    manifest = _manifest()
    schemas = manifest["command_schemas"]
    assert schemas, "command schema index must not be empty"
    commands = {entry["command"] for entry in schemas}
    # The manifest indexes the whole registered surface, including its own key.
    assert "contract" in commands
    assert "modelo.work.calculate" in commands
    for entry in schemas:
        assert entry["command"]
        assert entry["schema_name"]


def test_manifest_indexes_all_payload_module_naming_shapes() -> None:
    # The payload-discovery loader must catch every payload-module naming
    # shape, not only the ``_payloads`` suffix: ``_payloads_modelo_reconcile``
    # and ``_modelo_payloads_m036`` register real commands too. A regression in
    # the loader's name match silently drops these from the manifest.
    commands = {entry["command"] for entry in _manifest()["command_schemas"]}
    assert "modelo.reconcile.pull" in commands  # _payloads_modelo_reconcile.py
    assert "modelo.m036.alta" in commands  # _modelo_payloads_m036.py
    assert len(commands) >= 200


def test_manifest_marks_read_only_and_mutating_families() -> None:
    contract = _manifest()["contract"]
    by_child = {family["child"]: family["mutability"] for family in contract["command_families"]}
    assert by_child["overview"] == OperatorMutability.READ_ONLY.value
    assert by_child["review"] == OperatorMutability.READ_ONLY.value
    assert by_child["ledger"] == OperatorMutability.LOCAL_STATE_MUTATING.value
