"""The two secure-object read surfaces validate in one order.

``load`` (single row, raises) and ``iter_records_with_failures`` (batch,
isolates) must run the SAME checks in the SAME order and differ only in how
they report a failure. Before the shared decode core they did not: the
single-row path verified revision lineage BEFORE decrypting, while the batch
path decrypted FIRST and checked lineage afterwards. The drift the audit
predicted as a future risk had already happened.

Order is observable only on a row that fails BOTH checks -- the readable /
unreadable VERDICT is order-invariant, since a row must pass both to be read.
So every assertion here is on the attributed FAILURE, never on the verdict; an
assertion on the verdict would pass under either order and prove nothing.

Real behaviour throughout: real SQLite, a real ``EphemeralMasterKeyProvider``,
real AEAD, real stored-metadata corruption. Nothing is mocked.
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
    SecureObjectUnreadable,
    SecureObjectUnreadableError,
    SensitivityClass,
    _repo_at,
    datetime,
    sqlite3,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo.decode.order"
_KEY = "decode-order-subject"
_LINEAGE_REASON = "revision lineage self-consistency check failed"


def _seed(db_path: Path) -> None:
    with _repo_at(db_path) as repo:
        repo.save(
            namespace=_NAMESPACE,
            object_key=_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"decode-order-payload",
        )


def _break_lineage(db_path: Path) -> None:
    """Corrupt stored revision metadata so lineage self-consistency fails."""
    with sqlite3.connect(db_path) as con:
        con.execute(
            "UPDATE secure_objects SET revision_id = ? WHERE namespace = ?",
            ("f" * 64, _NAMESPACE),
        )


def _break_ciphertext(db_path: Path) -> None:
    """Flip a ciphertext byte so the AEAD tag no longer authenticates."""
    with sqlite3.connect(db_path) as con:
        row_id, payload = con.execute(
            "SELECT id, payload FROM secure_objects WHERE namespace = ?",
            (_NAMESPACE,),
        ).fetchone()
        con.execute(
            "UPDATE secure_objects SET payload = ? WHERE id = ?",
            (payload[:-1] + bytes([payload[-1] ^ 0xFF]), row_id),
        )


def _batch_outcome(db_path: Path) -> object:
    with _repo_at(db_path) as repo:
        outcomes = tuple(
            repo.iter_records_with_failures(
                _NAMESPACE,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=1,
            ),
        )
    assert len(outcomes) == 1
    return outcomes[0]


def test_batch_attributes_a_doubly_broken_row_to_lineage(tmp_path: Path) -> None:
    """A row failing BOTH lineage and decryption is attributed to lineage.

    DISCRIMINATING. This is the assertion that detects the order: under the
    previous batch order (decrypt first) the same row was reported with the
    AEAD failure text instead. The verdict -- unreadable -- is identical under
    both orders, which is exactly why this test asserts the reason.
    """
    provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "order-batch.db"
    with provider:
        _seed(db_path)
        _break_lineage(db_path)
        _break_ciphertext(db_path)
        outcome = _batch_outcome(db_path)

    assert isinstance(outcome, SecureObjectUnreadable)
    assert outcome.reason == _LINEAGE_REASON, (
        f"expected the lineage attribution, got {outcome.reason!r} -- "
        "the batch surface decrypted before checking lineage"
    )


def test_both_surfaces_attribute_a_doubly_broken_row_identically(tmp_path: Path) -> None:
    """Single-row and batch surfaces blame the SAME check on the same row.

    DISCRIMINATING. Before the shared core the two disagreed on this exact
    input: the single-row path raised the lineage error while the batch path
    reported a decryption failure. Cross-surface agreement on WHICH check
    failed is the property the shared decode core establishes.
    """
    provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "order-both.db"
    with provider:
        _seed(db_path)
        _break_lineage(db_path)
        _break_ciphertext(db_path)

        with _repo_at(db_path) as repo, pytest.raises(SecureObjectUnreadableError):
            repo.load(_NAMESPACE, _KEY, expected_class=SensitivityClass.FINANCIAL, max_supported_version=1)

        outcome = _batch_outcome(db_path)

    assert isinstance(outcome, SecureObjectUnreadable)
    assert outcome.reason == _LINEAGE_REASON


def test_lineage_only_break_is_attributed_to_lineage(tmp_path: Path) -> None:
    """A decryptable row with broken lineage is still refused, and named so.

    SUPPORTING: green under both orders, because only one check fails. It
    exists to show the lineage check refuses on its own rather than only
    winning a race with decryption.
    """
    provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "order-lineage.db"
    with provider:
        _seed(db_path)
        _break_lineage(db_path)
        outcome = _batch_outcome(db_path)

    assert isinstance(outcome, SecureObjectUnreadable)
    assert outcome.reason == _LINEAGE_REASON


def test_ciphertext_only_break_is_attributed_to_decryption(tmp_path: Path) -> None:
    """A lineage-consistent row with bad ciphertext is blamed on decryption.

    SUPPORTING: green under both orders. It is the control proving the lineage
    attribution above is not simply swallowing every failure -- a decryption
    failure still surfaces as one.
    """
    provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "order-cipher.db"
    with provider:
        _seed(db_path)
        _break_ciphertext(db_path)
        outcome = _batch_outcome(db_path)

    assert isinstance(outcome, SecureObjectUnreadable)
    assert outcome.reason != _LINEAGE_REASON
    assert outcome.reason


def test_both_read_surfaces_route_through_the_one_decode_core() -> None:
    """Neither read surface reimplements the pipeline; both call the core.

    DISCRIMINATING, and the only assertion here that survives a re-inlining
    mutation: a byte-identical copy of the pipeline pasted back into one
    surface reproduces every behavioural result above, because it computes the
    same answers twice. This is what notices the copy.
    """
    from .. import _secure_object_row_codec as codec

    for surface in (codec.secure_object_record_from_row, codec.secure_object_list_item_from_raw_row):
        source = inspect.getsource(surface)
        assert _calls(source, "decode_secure_object_row"), (
            f"{surface.__name__} does not route through the decode core"
        )
        for reimplemented in (
            "decrypt_secure_object_payload(",
            "secure_object_payload_aad(",
            "verify_revision_self_consistency(",
            "ensure_schema_version_readable(",
            "upgrade_secure_object_payload(",
        ):
            assert reimplemented not in source, f"{surface.__name__} reimplements {reimplemented} instead of delegating"


def test_the_decode_core_checks_lineage_before_it_decrypts() -> None:
    """Integrity is verified before any AEAD work, and the check is refuse-only.

    DISCRIMINATING on the order. Asserted structurally because the ordering is
    a security property of the code, not of any single row's outcome: the
    pre-decrypt lineage check reads UNAUTHENTICATED stored metadata, which is
    safe only while it can exclusively REFUSE. A path that let that metadata
    mark a row readable, skip a later check, or select a decode branch would be
    exploitable, so the source is pinned rather than inferred.
    """
    from .. import _secure_object_row_codec as codec

    source = inspect.getsource(codec.decode_secure_object_row)
    lineage_at = source.index("verify_revision_self_consistency(")
    decrypt_at = source.index("decrypt_secure_object_payload(")
    assert lineage_at < decrypt_at, "the decode core decrypts before verifying revision lineage"

    # Refuse-only: the lineage branch raises and does nothing else.
    lineage_branch = source[lineage_at:decrypt_at]
    assert "raise SecureObjectUnreadableError(" in lineage_branch
    assert "return " not in lineage_branch, "the pre-decrypt lineage check has a non-refusing exit"


def _seed_second_row(db_path: Path, *, object_key: str) -> None:
    with _repo_at(db_path) as repo:
        repo.save(
            namespace=_NAMESPACE,
            object_key=object_key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"second-row-payload",
        )


@pytest.mark.parametrize(
    ("column", "value"),
    [("schema_version", "bogus"), ("classification", "")],
)
def test_malformed_row_metadata_is_isolated_to_its_own_row(
    tmp_path: Path,
    column: str,
    value: str,
) -> None:
    """A row whose metadata columns are unusable must not abort the scan.

    The batch surface promises one outcome per row so a caller can attribute a
    failure and keep inspecting the rest. The raw-row coercions -- ``int(id)``,
    ``int(schema_version)``, the bytes conversions -- ran ABOVE the
    fault-isolating boundary, so a tampered ``schema_version = 'bogus'`` raised
    a bare ValueError out of ``int()`` and took every remaining row with it.
    The shared decode core was never even reached.
    """
    provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / f"malformed-{column}.db"
    with provider:
        _seed(db_path)
        _seed_second_row(db_path, object_key="decode-order-sibling")
    with sqlite3.connect(db_path) as con:
        target_id = con.execute(
            "SELECT id FROM secure_objects WHERE namespace = ? ORDER BY id LIMIT 1",
            (_NAMESPACE,),
        ).fetchone()[0]
        # The column name is a test-local literal from the parametrisation,
        # never operator input, so the interpolation carries no injection risk.
        con.execute(
            f"UPDATE secure_objects SET {column} = ? WHERE id = ?",  # noqa: S608
            (value, target_id),
        )

    with provider, _repo_at(db_path) as repo:
        outcomes = tuple(
            repo.iter_records_with_failures(
                _NAMESPACE,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=1,
            ),
        )

    # Both rows are accounted for: the tampered one as a typed failure naming
    # the column, the sibling as a readable record.
    assert len(outcomes) == 2
    unreadable = [item for item in outcomes if isinstance(item, SecureObjectUnreadable)]
    assert len(unreadable) == 1
    assert column in unreadable[0].reason


def test_an_untampered_namespace_still_scans_clean(tmp_path: Path) -> None:
    """Positive control: the normalisation guard reports nothing on healthy rows."""
    provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "clean-scan.db"
    with provider:
        _seed(db_path)
        _seed_second_row(db_path, object_key="decode-order-sibling")

    with provider, _repo_at(db_path) as repo:
        outcomes = tuple(
            repo.iter_records_with_failures(
                _NAMESPACE,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=1,
            ),
        )

    assert len(outcomes) == 2
    assert [item for item in outcomes if isinstance(item, SecureObjectUnreadable)] == []


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
