"""Cross-surface agreement of the secure-object decryptability decision.

Quarantine, namespace counting, and per-row enumeration differ in what they DO
with an undecryptable row -- move it, count it, describe it -- but must agree
exactly on WHICH rows those are. These tests pin that agreement over a real
SQLite database, a real ``EphemeralMasterKeyProvider``, real AEAD, and a
genuinely undecryptable row produced by corrupting stored ciphertext.

What these tests prove, stated honestly: they lock the three surfaces to ONE
decryptability decision. They do not, on their own, prove the decision is
correct -- the mutation that discriminates is a change to the shared probe,
which must move all three surfaces together. Before the extraction each surface
carried its own copy, so such a change moved only one.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from ......tests.master_key import EphemeralMasterKeyProvider
from ._secure_objects_support import (
    UTC,
    Path,
    SensitivityClass,
    _repo_at,
    datetime,
    sqlite3,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo.integrity.agreement"
_READABLE_KEYS = ("agreement-readable-one", "agreement-readable-two")
_CORRUPT_KEY = "agreement-corrupt"


def test_every_integrity_surface_routes_through_the_shared_probe() -> None:
    """No integrity surface opens ciphertext itself; all three call the probe.

    DISCRIMINATING, and the only assertion here that survives a re-inlining
    mutation. The behavioural tests below compare the three surfaces' OUTPUT,
    so a byte-identical copy of the probe pasted back into one surface leaves
    them all green -- the outputs still agree, they are just computed three
    times again. This assertion is what notices, and it is therefore the one
    that proves the deduplication rather than merely the behaviour.
    """
    from .. import _secure_object_integrity as integrity_module

    surfaces = (
        integrity_module.quarantine_unreadable_rows,
        integrity_module.probe_namespace_integrity,
        integrity_module.iter_namespace_decryptability,
    )

    for surface in surfaces:
        source = inspect.getsource(surface)
        assert _calls(source, "probe_row_decryptability"), (
            f"{surface.__name__} does not route through the shared decryptability probe"
        )
        assert "decrypt_secure_object_payload(" not in source, (
            f"{surface.__name__} opens ciphertext directly instead of delegating to the shared probe"
        )
        assert "secure_object_payload_aad(" not in source, (
            f"{surface.__name__} rebuilds the row-identity AAD instead of delegating to the shared probe"
        )

    # The probe itself is the one place that may do those things.
    probe_source = inspect.getsource(integrity_module.probe_row_decryptability)
    assert "decrypt_secure_object_payload(" in probe_source
    assert "secure_object_payload_aad(" in probe_source


def _seed_mixed_namespace(db_path: Path) -> None:
    """Seed two decryptable rows and one whose stored ciphertext is corrupted.

    Corrupting the ciphertext in place (rather than re-keying the whole store)
    is what produces a genuine MIX under a single master key, so surface
    agreement is a real partition rather than an all-or-nothing answer.
    """
    with _repo_at(db_path) as repo:
        for key in (*_READABLE_KEYS, _CORRUPT_KEY):
            repo.save(
                namespace=_NAMESPACE,
                object_key=key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=f"payload-for-{key}".encode(),
            )
    with sqlite3.connect(db_path) as con:
        rows = con.execute(
            "SELECT id, payload FROM secure_objects WHERE namespace = ? ORDER BY id",
            (_NAMESPACE,),
        ).fetchall()
        # Flip the final ciphertext byte of the last row: the AEAD tag no
        # longer authenticates, so this row -- and only this row -- fails to
        # open under the very key that wrote it.
        target_id, payload = rows[-1]
        corrupted = payload[:-1] + bytes([payload[-1] ^ 0xFF])
        con.execute("UPDATE secure_objects SET payload = ? WHERE id = ?", (corrupted, target_id))


def test_count_and_enumeration_surfaces_agree(tmp_path: Path) -> None:
    """Namespace counting and per-row enumeration report the same partition.

    DISCRIMINATING: fails when the shared decryptability probe changes.
    """
    provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "agreement-count.db"
    with provider:
        _seed_mixed_namespace(db_path)
        with _repo_at(db_path) as repo:
            counted = repo.probe_namespace_integrity(_NAMESPACE)
            enumerated = tuple(repo.iter_namespace_decryptability(_NAMESPACE))

    assert counted.readable == 2
    assert counted.unreadable == 1

    enumerated_readable = sum(1 for row in enumerated if row.readable)
    enumerated_unreadable = sum(1 for row in enumerated if not row.readable)
    assert enumerated_readable == counted.readable
    assert enumerated_unreadable == counted.unreadable

    # The unreadable row carries a reason; readable rows carry none.
    for row in enumerated:
        assert (row.reason is None) is row.readable


def test_quarantine_moves_exactly_the_rows_the_probes_flag(tmp_path: Path) -> None:
    """Quarantine acts on precisely the partition the read-only surfaces report.

    DISCRIMINATING: fails when the shared decryptability probe changes, and is
    the assertion that ties the MUTATING surface to the read-only ones.
    """
    provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "agreement-quarantine.db"
    with provider:
        _seed_mixed_namespace(db_path)
        with _repo_at(db_path) as repo:
            enumerated = tuple(repo.iter_namespace_decryptability(_NAMESPACE))
            flagged_keys = {row.object_key for row in enumerated if not row.readable}
            report = repo.quarantine_unreadable_rows()

        with sqlite3.connect(db_path) as con:
            quarantined_keys = {
                row[0] if isinstance(row[0], bytes) else bytes(row[0])
                for row in con.execute("SELECT object_key FROM secure_objects_quarantine").fetchall()
            }
            remaining = con.execute(
                "SELECT COUNT(*) FROM secure_objects WHERE namespace = ?",
                (_NAMESPACE,),
            ).fetchone()[0]

    namespace_report = next(entry for entry in report if entry.namespace == _NAMESPACE)
    assert namespace_report.readable == 2
    assert namespace_report.unreadable == 1
    assert quarantined_keys == flagged_keys
    assert remaining == 2


def test_quarantine_preserves_the_probed_bytes(tmp_path: Path) -> None:
    """The row that moves is byte-identical to the row that was probed.

    DISCRIMINATING. Quarantine re-inserts the normalised bytes the shared probe
    returned, so a normalisation change cannot make the archived ciphertext
    differ from the ciphertext whose decryption failed.
    """
    provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "agreement-bytes.db"
    with provider:
        _seed_mixed_namespace(db_path)
        with sqlite3.connect(db_path) as con:
            before = con.execute(
                "SELECT object_key, payload FROM secure_objects WHERE namespace = ? ORDER BY id",
                (_NAMESPACE,),
            ).fetchall()
        with _repo_at(db_path) as repo:
            repo.quarantine_unreadable_rows()
        with sqlite3.connect(db_path) as con:
            archived = con.execute(
                "SELECT object_key, payload FROM secure_objects_quarantine",
            ).fetchall()

    assert len(archived) == 1
    archived_key, archived_payload = archived[0]
    # The corrupted row was seeded last.
    source_key, source_payload = before[-1]
    assert bytes(archived_key) == bytes(source_key)
    assert bytes(archived_payload) == bytes(source_payload)


def test_all_rows_readable_reports_clean_across_surfaces(tmp_path: Path) -> None:
    """With no corruption every surface reports a clean namespace.

    DISCRIMINATING. Doubles as the negative control for the partition tests
    above -- it confirms the corruption there is what produces the unreadable
    row, not the harness -- but it also fails under a mutation of the shared
    probe, because a broken decryptability decision turns these clean rows
    unreadable on every surface at once.
    """
    provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "agreement-clean.db"
    with provider:
        with _repo_at(db_path) as repo:
            for key in _READABLE_KEYS:
                repo.save(
                    namespace=_NAMESPACE,
                    object_key=key,
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=f"clean-{key}".encode(),
                )
        with _repo_at(db_path) as repo:
            counted = repo.probe_namespace_integrity(_NAMESPACE)
            enumerated = tuple(repo.iter_namespace_decryptability(_NAMESPACE))
            report = repo.quarantine_unreadable_rows()

    assert counted.readable == 2
    assert counted.unreadable == 0
    assert all(row.readable for row in enumerated)
    assert all(row.reason is None for row in enumerated)
    namespace_report = next(entry for entry in report if entry.namespace == _NAMESPACE)
    assert namespace_report.unreadable == 0


def _calls(source: str, callee: str) -> bool:
    """Whether ``source`` actually CALLS ``callee``, not merely mentions it.

    A membership test on source text passes when the name appears in a
    docstring or comment, so a surface that stopped delegating while keeping
    its prose reads as compliant.
    """
    tree = ast.parse(textwrap.dedent(source))
    return any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Attribute) and node.func.attr == callee)
            or (isinstance(node.func, ast.Name) and node.func.id == callee)
        )
        for node in ast.walk(tree)
    )


def test_the_delegation_check_rejects_a_docstring_mention() -> None:
    """DISCRIMINATING: a mention is not a call.

    The positive half of this gate asserted that the shared routine's NAME
    appeared in the surface's source. A surface that stopped calling it and
    kept a sentence naming it passed -- which is the regression the gate is
    for.
    """
    calling = "def surface(row):\n    return shared_routine(row)\n"
    mentioning = (
        "def surface(row):\n"
        '    """Delegates to shared_routine( ) in the core."""\n'
        "    return row\n"
    )

    assert _calls(calling, "shared_routine")
    assert not _calls(mentioning, "shared_routine")
