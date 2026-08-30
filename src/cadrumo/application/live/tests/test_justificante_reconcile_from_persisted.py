"""Persisted justificante reconciliation tests."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pytest

from ...tests import isolated_profile_backend as _isolated_backend

__all__ = ["_isolated_backend"]

from ....core.modelo import Modelo
from ....core.directory_scan import scan_directory
from ...modelo.reconciliation import ReconciliationEvidenceInvalidError
from ...modelo.reconciliation_records import (
    ModeloReconciliationVerdict,
    list_modelo_reconciliations,
)
from ..justificante import JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE, reconcile_capture
from ._justificante_reconcile_support import (
    MODELO_130_FIXTURE,
    _active_bucket_id,
    _persist_capture,
    _seed_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_reconcile_from_persisted_capture_matches() -> None:
    """A persisted real-fixture capture reconciles to MATCHES against its work unit."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    report = reconcile_capture(work_unit_id=work_unit_id, snapshot=snapshot)

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert report.diffs == ()
    assert report.work_unit_id == work_unit_id
    assert report.source_path == f"secure-object://{JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE}/{snapshot.snapshot_id}"
    history = list_modelo_reconciliations(bucket_id=_active_bucket_id(), work_unit_id=work_unit_id)
    assert len(history) == 1
    assert history[0].source_path == report.source_path


def test_reconcile_from_persisted_capture_writes_nothing_to_disk(tmp_path: Path) -> None:
    """The live reconcile parses the receipt from in-memory bytes only.

    Honours ``sensitive-financial-data-secure-storage-only``: the decrypted
    justificante bytes must not persist as plaintext. The real secure store and
    parser run unmocked; this test verifies the reconciliation is addressed by
    its secure-object reference and that the isolated storage tree contains no
    durable copy of the raw PDF bytes after the reconcile call.
    """
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    pdf_bytes = MODELO_130_FIXTURE.read_bytes()
    snapshot = _persist_capture(
        pdf_bytes=pdf_bytes,
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    report = reconcile_capture(work_unit_id=work_unit_id, snapshot=snapshot)

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert report.source_path == f"secure-object://{JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE}/{snapshot.snapshot_id}"

    scan = _scan_for_plaintext(tmp_path, pdf_bytes)

    # An empty match set means "no plaintext copy" only if the scan actually
    # looked. Both other outcomes below produce the same empty set, and neither
    # is evidence of anything.
    assert scan.scanned, "the scan reached no files at all, so an empty match set below proves nothing"
    assert not scan.unreadable, (
        f"the scan could not read {len(scan.unreadable)} file(s), so they were never checked for the "
        f"plaintext they might hold: {scan.unreadable}"
    )
    assert scan.matches == ()


class _PlaintextScan(NamedTuple):
    """What a plaintext sweep found, and what it was unable to look at.

    ``unreadable`` exists because the previous form of this scan swallowed
    :exc:`OSError` and continued. A file it could not open was silently dropped
    from the sweep and the caller received the same empty tuple it receives for
    a genuinely clean tree -- so "no plaintext leaked" and "could not look"
    were one value. This share's defining property is that it fails under
    concurrent I/O, which makes that the likely reading rather than the
    paranoid one, and the failure is invisible in the direction that reassures.

    ``scanned`` is carried for the same reason one step earlier: a sweep over
    an empty tree also returns no matches.
    """

    matches: tuple[Path, ...]
    unreadable: tuple[Path, ...]
    scanned: int


def _cannot_carry(path: Path, needle: bytes) -> bool:
    """Whether ``path`` is physically too small to contain ``needle``.

    The one sanctioned reason to stop caring that a file could not be read.
    It is a SIZE fact rather than a name rule, and that distinction is the
    whole point: the file this exists for is the profile lock the test process
    itself holds open, which cannot be opened for reading while held. Excusing
    it as ``active-profile.lock`` would be a filename allowlist, and a filename
    allowlist is the swallow rebuilt one level up -- the next unreadable file
    with a different name gets excused by whoever extends the list.

    A file shorter than the needle cannot contain it, whatever it is called.
    A file that cannot even be measured is NOT excused: an unknown size clears
    nothing, and this must fail toward reporting rather than toward silence.
    """
    try:
        return path.stat().st_size < len(needle)
    except OSError:
        return False


def _scan_for_plaintext(root: Path, needle: bytes) -> _PlaintextScan:
    """Search every readable file under ``root`` for ``needle``.

    Reports what it could not read instead of skipping it, so the caller can
    tell a clean sweep from a blind one.
    """
    matches: list[Path] = []
    unreadable: list[Path] = []
    scanned = 0
    for path in (item for item in scan_directory(root, recursive=True) if item.is_file()):
        try:
            body = path.read_bytes()
        except OSError:
            if not _cannot_carry(path, needle):
                unreadable.append(path.relative_to(root))
            continue
        scanned += 1
        if needle in body:
            matches.append(path.relative_to(root))
    return _PlaintextScan(tuple(matches), tuple(unreadable), scanned)


def test_an_unreadable_file_is_excused_only_when_it_is_too_small_to_carry_the_needle(
    tmp_path: Path,
) -> None:
    """The carve-out that keeps the sibling guard from firing on a held lock.

    The guard above refuses a sweep that could not read something. On its first
    real outing it fired on ``cadrumo-storage/active-profile.lock`` -- held open
    by the profile lock for the duration of the test, so genuinely unreadable
    and genuinely incapable of hiding a PDF. A guard that reds on a legitimate
    case trains people to weaken it, so the carve-out is stated rather than
    left to a filename.

    This pins the predicate at its boundary, because a size test is exactly the
    kind that is written with the wrong comparison and never noticed: a file one
    byte short of the needle is excused, a file the same length is not. The
    equal-length case is the one that matters -- it is the smallest file that
    could still BE the needle.
    """
    needle = b"0123456789"
    (tmp_path / "shorter").write_bytes(b"012345678")
    (tmp_path / "exact").write_bytes(b"0123456789")
    (tmp_path / "longer").write_bytes(b"0123456789abc")

    assert _cannot_carry(tmp_path / "shorter", needle)
    assert not _cannot_carry(tmp_path / "exact", needle)
    assert not _cannot_carry(tmp_path / "longer", needle)

    # A file that cannot even be measured clears nothing. Unknown size must
    # fail toward reporting, which is the direction every blind instrument in
    # this tree has failed the other way.
    assert not _cannot_carry(tmp_path / "does-not-exist", needle)


def test_the_plaintext_scan_finds_a_planted_copy_so_its_silence_can_be_trusted(tmp_path: Path) -> None:
    """Positive control for the ``scan.matches == ()`` assertion above.

    That assertion passes for three reasons it cannot tell apart: because no
    plaintext copy was written, because the sweep reached no files, or because
    every file it wanted to read raised and was dropped. Only the first is the
    guarantee the test claims, and all three render as an empty tuple.

    So the predicate is driven against a copy planted where a real regression
    would put one -- a plain file on disk under the isolated storage root,
    which is exactly the shape ``sensitive-financial-data-secure-storage-only``
    forbids -- and required to name it. The sibling's silence is then measured
    reach rather than an untested expression that would stay quiet however the
    reconcile path changed.

    Nested one directory down deliberately: the sweep is recursive and a
    top-level-only regression in it would otherwise pass this control.
    """
    needle = b"%PDF-1.4\nplanted-plaintext-justificante-canary\n%%EOF\n"
    leaked_copy = tmp_path / "live" / "justificante" / "leaked.pdf"
    leaked_copy.parent.mkdir(parents=True, exist_ok=True)
    leaked_copy.write_bytes(needle)

    scan = _scan_for_plaintext(tmp_path, needle)

    assert scan.matches == (Path("live") / "justificante" / "leaked.pdf",), (
        "the plaintext scan did not find a file it was pointed straight at, so its silence in the "
        "sibling test above is evidence of nothing"
    )
    assert not scan.unreadable
    assert scan.scanned


def test_reconcile_from_persisted_capture_mismatches_on_modelo() -> None:
    """A 303 work unit reconciled against the persisted 130 capture mismatches."""
    work_unit_id = _seed_work_unit(modelo="303", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    report = reconcile_capture(work_unit_id=work_unit_id, snapshot=snapshot)

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    assert any(diff.field_name == "modelo" for diff in report.diffs)


def test_reconcile_from_malformed_capture_raises_without_leaking_temp_path() -> None:
    """A capture whose bytes are not a parseable justificante refuses cleanly.

    The persisted secure object reference is the only source identifier surfaced
    in the error; no plaintext filesystem path is involved.
    """
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=b"%PDF-1.4\nnot a real justificante\n%%EOF\n",
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(ReconciliationEvidenceInvalidError) as exc_info:
        reconcile_capture(work_unit_id=work_unit_id, snapshot=snapshot)
    message = str(exc_info.value)
    assert f"secure-object://{JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE}/{snapshot.snapshot_id}" in message
    assert "Temp" not in message
    assert ".pdf" not in message
