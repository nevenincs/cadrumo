"""Actual journal access purges manual amounts before hydration and replay."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from .....core.json_shapes import model_json_object
from ...storage.errors import RepositoryError
from ..financial_journal_purge import FinancialEditJournalPurgeRefusedError
from ..journal import OperationJournalRepository
from .test_journal import _snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]
_SENTINEL = "93847562.19"


def _write_legacy(
    tmp_path: Path, *, policy: str, schema: int | None = None, definition: str = "modelo.edit.apply"
) -> tuple[OperationJournalRepository, Path]:
    snapshot = model_json_object(_snapshot(revision=0, sequence=1))
    identity = snapshot["identity"]
    assert isinstance(identity, dict)
    identity["definition_id"] = definition
    events = snapshot["events"]
    assert isinstance(events, list)
    event = events[0]
    assert isinstance(event, dict)
    event["identity"] = dict(identity)
    if schema is not None:
        snapshot["schema_version"] = schema
    snapshot["request_storage"] = policy
    snapshot["credential_free_request_json"] = (
        None if policy == "secure_reference" else json.dumps({"submission": {"scalar_intents": [{"value": _SENTINEL}]}})
    )
    if policy != "secure_reference":
        event["manual_amount"] = _SENTINEL
        snapshot["legacy_operand"] = _SENTINEL
    root = tmp_path / "operation-journals"
    root.mkdir()
    path = root / (("a" * 64) + ".json")
    path.write_text(json.dumps({"snapshot": snapshot, "history": [dict(event)]}), encoding="utf-8")
    return OperationJournalRepository(storage_root=tmp_path), path


@pytest.mark.parametrize("reader", ("load", "replay", "observation", "inventory"))
@pytest.mark.parametrize("policy", ("credential_free_journal", "secure_reference"))
@pytest.mark.parametrize("definition", ("modelo.edit.apply", "modelo.edit.preflight"))
def test_every_read_surface_purges_before_returning_any_operation_fact(
    tmp_path: Path, reader: str, policy: str, definition: str
) -> None:
    """Neither inline operands nor legacy content addresses survive a read."""
    repository, path = _write_legacy(tmp_path, policy=policy, definition=definition)
    original = json.loads(path.read_text(encoding="utf-8"))

    async def read() -> None:
        if reader == "load":
            await repository.load("a" * 64)
        elif reader == "replay":
            await repository.read_after("a" * 64, 0, limit=10)
        elif reader == "observation":
            await repository.read_observation("a" * 64, 0, limit=10)
        else:
            await repository.inventory_page(after=None, limit=10)

    asyncio.run(read())
    purged = path.read_bytes()
    assert _SENTINEL.encode() not in purged
    document = json.loads(purged)
    snapshot = document["snapshot"]
    assert snapshot["manual_edit_values_purged"] is True
    assert snapshot["identity"] == original["snapshot"]["identity"]
    assert snapshot["lifecycle"] == original["snapshot"]["lifecycle"]
    assert snapshot["revision"] == original["snapshot"]["revision"]
    assert snapshot["terminal_condition"] == original["snapshot"]["terminal_condition"]
    assert snapshot["effect"] == original["snapshot"]["effect"]
    assert snapshot["request_reference"] != original["snapshot"]["request_reference"]
    asyncio.run(read())
    assert path.read_bytes() == purged


def test_plaintext_snapshot_six_is_purged_and_still_refused_as_superseded(tmp_path: Path) -> None:
    """The purge never silently upgrades the plaintext version shipped before secure custody."""
    repository, path = _write_legacy(tmp_path, policy="credential_free_journal", schema=6)
    with pytest.raises(RepositoryError, match="invalid operation journal"):
        asyncio.run(repository.load("a" * 64))
    purged = path.read_bytes()
    assert _SENTINEL.encode() not in purged
    assert json.loads(purged)["snapshot"]["schema_version"] == 6
    with pytest.raises(RepositoryError, match="invalid operation journal"):
        asyncio.run(repository.read_after("a" * 64, 0, limit=10))
    assert path.read_bytes() == purged


def test_unrewritable_journal_has_bounded_typed_refusal_and_never_returns_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed hardened replacement leaves the old bytes unavailable to every reader."""
    repository, path = _write_legacy(tmp_path, policy="credential_free_journal")
    original = path.read_bytes()

    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError("replacement denied")

    monkeypatch.setattr("cadrumo.application.journal_repository.atomic_write_hardened_text", denied)
    with pytest.raises(FinancialEditJournalPurgeRefusedError) as raised:
        asyncio.run(repository.load("a" * 64))
    assert _SENTINEL not in str(raised.value)
    assert raised.value.__cause__ is None
    assert path.read_bytes() == original


def test_filename_mismatch_cannot_purge_a_different_operation(tmp_path: Path) -> None:
    """Purging never follows the identity contained in untrusted JSON to another file."""
    repository, path = _write_legacy(tmp_path, policy="credential_free_journal")
    mismatched = path.with_name(("b" * 64) + ".json")
    path.rename(mismatched)
    original = mismatched.read_bytes()
    with pytest.raises(FinancialEditJournalPurgeRefusedError):
        asyncio.run(repository.load("b" * 64))
    assert mismatched.read_bytes() == original
    assert not path.exists()


def test_successor_amount_free_request_is_unchanged(tmp_path: Path) -> None:
    """Current amount-free requests are not treated as legacy financial inputs."""
    repository, path = _write_legacy(tmp_path, policy="credential_free_journal")
    document = json.loads(path.read_text(encoding="utf-8"))
    document["snapshot"].pop("legacy_operand")
    document["snapshot"]["credential_free_request_json"] = '{"request_version":2,"baseline_ref":"baseline"}'
    for event in [*document["snapshot"]["events"], *document["history"]]:
        event.pop("manual_amount")
    path.write_text(json.dumps(document), encoding="utf-8")
    original = path.read_bytes()
    asyncio.run(repository.load("a" * 64))
    assert path.read_bytes() == original


def test_purge_preserves_an_already_committed_terminal_outcome(tmp_path: Path) -> None:
    """Settled identity, effect and receipt remain authoritative after operand disposal."""
    from .test_journal import _terminal_event

    repository, path = _write_legacy(tmp_path, policy="credential_free_journal")
    document = json.loads(path.read_text(encoding="utf-8"))
    identity = document["snapshot"]["identity"]
    terminal = model_json_object(_terminal_event())
    terminal["identity"] = identity
    receipt = terminal["receipt"]
    assert isinstance(receipt, dict)
    receipt["identity"] = identity
    document["snapshot"].update(
        lifecycle="terminal",
        terminal_condition="succeeded",
        terminal_receipt=receipt,
        events=[terminal],
        phase_code=None,
    )
    document["history"] = [terminal]
    path.write_text(json.dumps(document), encoding="utf-8")
    snapshot = asyncio.run(repository.load("a" * 64))
    assert snapshot.terminal_receipt is not None
    assert snapshot.terminal_receipt.model_dump(mode="json") == receipt
    assert _SENTINEL.encode() not in path.read_bytes()


@pytest.mark.parametrize("language", ("en", "es", "ca", "hu"))
def test_purge_refusal_is_registered_and_localized(language: str) -> None:
    """The fail-closed reason is a real bounded product error in every locale."""
    from .....core.errors.error_codes import get_registered_error_code
    from .....core.i18n.render import lookup_translation

    code = get_registered_error_code(FinancialEditJournalPurgeRefusedError())
    assert code.code == "REFUSED_FINANCIAL_EDIT_JOURNAL_PURGE"
    translated = lookup_translation(code.message_key, locale=language)
    assert translated is not None and translated != code.message_key
    assert _SENTINEL not in str(translated)
