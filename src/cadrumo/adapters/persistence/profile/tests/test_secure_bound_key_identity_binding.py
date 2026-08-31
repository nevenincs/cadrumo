"""A secure-bound row's key and its payload's identity are one fact.

``SecureBoundRepository.save`` derives the SQL object key from the payload
itself, via ``extract_identifier`` -- for a justificante, the AEAT CSV. The two
are therefore two encodings of one fact, but nothing on the read path checked
that, so a row written under a different key returned its payload unremarked:
``load("CSV-B")`` handed back the record whose own ``csv`` is ``"CSV-A"``.

That is a quiet wrong answer rather than a loud failure. The returned object
describes itself truthfully and validates cleanly; it simply is not the record
that was asked for. A caller resolving a receipt by CSV -- to attach evidence
to a filing, or to answer "was this presented?" -- gets another taxpayer
artefact with no signal that anything is amiss.

``load`` now compares the payload's own identity with the key it was looked up
under and raises rather than returning ``None``: the row exists, and reporting
it absent would hide a real inconsistency behind an ordinary miss.

Real active profile, real SQLite, real AES-GCM. The mis-keyed row is written
through the substrate's own writer rather than by editing bytes, so it is a
genuinely well-formed row that differs only in the key it is filed under.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from .....core.period import Period
from .....domain.justificante import Justificante
from .....tests.aeat_literal_fixtures import justificante_wlpl_cotejo_url
from .....tests.secure_sql import isolated_runtime_profile
from ...storage.envelope.secure_bound_repository import SecureBoundRepository
from ...storage.errors import SecureObjectRowIdentityError
from ..justificante import JustificanteRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PRESENTED_AT = datetime(2026, 5, 27, 11, 15, 0, tzinfo=UTC)
_CSV_A = "AAAA11112222BBBB"
_CSV_B = "CCCC33334444DDDD"


def _justificante(csv: str) -> Justificante:
    return Justificante(
        csv=csv,
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        ejercicio="2025",
        presentation_id="PRES-2025-001-XYZ",
        presented_at=_PRESENTED_AT,
        tax_id="12345678Z",
        total_a_ingresar=Decimal("12345.67"),
        total_a_devolver=None,
        verification_url=AnyHttpUrl(justificante_wlpl_cotejo_url(csv)),
        source_pdf_path=Path("justificantes/303-2025-1T-AAAA.pdf"),
        source_pdf_sha256="a" * 64,
        parsed_at=_PRESENTED_AT,
    )


def _save_under_foreign_key(repository: JustificanteRepository, payload: Justificante, *, object_key: str) -> None:
    """Persist ``payload`` under ``object_key`` instead of its own identity.

    Written through the substrate's real writer with the repository's real
    envelope, so the row is well-formed in every respect except the key it is
    filed under -- isolating the key/payload binding as the only thing under
    test.
    """
    _, envelope = repository._identified_envelope(payload)
    repository._objects.save(
        namespace=repository.namespace,
        object_key=object_key,
        classification=repository.sensitivity,
        schema_version=repository.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )


def test_a_correctly_keyed_record_round_trips(tmp_path: Path) -> None:
    """Positive control: the ordinary save/load cycle is untouched.

    Every refusal below is only evidence against this. It also proves the
    comparison is not simply always-failing, which a naive identity check
    written against the wrong field would be.
    """
    record = _justificante(_CSV_A)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = JustificanteRepository()
        repository.save(record)

        assert repository.load(_CSV_A) == record
        assert repository.list_csvs() == (_CSV_A,)


def test_loading_a_mis_keyed_row_refuses_instead_of_returning_another_record(tmp_path: Path) -> None:
    """The discriminating case: asking for B must not yield A.

    Before the binding this returned the CSV-A record, so a caller resolving
    a receipt by CSV received a different artefact entirely and had no signal.
    """
    record = _justificante(_CSV_A)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = JustificanteRepository()
        _save_under_foreign_key(repository, record, object_key=_CSV_B)

        with pytest.raises(SecureObjectRowIdentityError):
            repository.load(_CSV_B)


def test_a_mis_keyed_row_is_absent_under_its_own_identity(tmp_path: Path) -> None:
    """The record is unreachable by its true CSV, which is the honest answer.

    Pins the other half of the inconsistency: the row is filed under B, so a
    lookup by A finds nothing. Distinguishing "absent" here from "refused"
    above is what shows the refusal is about the key/payload disagreement
    rather than about the record being unreadable in general.
    """
    record = _justificante(_CSV_A)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = JustificanteRepository()
        _save_under_foreign_key(repository, record, object_key=_CSV_B)

        assert repository.load(_CSV_A) is None


def test_verified_iteration_refuses_the_same_row(tmp_path: Path) -> None:
    """Lookup and verified enumeration reach the same verdict.

    The two surfaces previously disagreed -- lookup returned the record while
    enumeration reported its true identity -- so asserting them together is
    what establishes one invariant rather than two independent checks.
    """
    record = _justificante(_CSV_A)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = JustificanteRepository()
        _save_under_foreign_key(repository, record, object_key=_CSV_B)

        with pytest.raises(SecureObjectRowIdentityError):
            list(repository.iter_records())


def test_a_correctly_keyed_row_survives_verified_iteration(tmp_path: Path) -> None:
    """Positive control for the enumeration half."""
    record = _justificante(_CSV_A)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = JustificanteRepository()
        repository.save(record)

        assert list(repository.iter_records()) == [record]


def test_id_enumeration_refuses_the_same_row(tmp_path: Path) -> None:
    """``iter_ids`` reaches the same verdict as lookup and record enumeration.

    The id scan derived each id from the payload alone, so a row filed under
    B reported ``CSV-A`` -- an id the store does not hold that record at. A
    caller listing ids and then loading each one got a refusal on a key the
    same repository had just published, with nothing tying the two together.
    """
    record = _justificante(_CSV_A)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = JustificanteRepository()
        _save_under_foreign_key(repository, record, object_key=_CSV_B)

        with pytest.raises(SecureObjectRowIdentityError):
            list(repository.iter_ids())


def test_the_load_refusal_names_both_the_key_asked_for_and_the_identity_found(
    tmp_path: Path,
) -> None:
    """A mismatch refusal is only actionable if it names both sides.

    Naming one identity leaves the reader unable to tell which it reported --
    the key they asked for, or the one the row actually describes -- and those
    are the two facts needed to find the misfiled row.
    """
    record = _justificante(_CSV_A)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = JustificanteRepository()
        _save_under_foreign_key(repository, record, object_key=_CSV_B)

        with pytest.raises(SecureObjectRowIdentityError) as refusal:
            repository.load(_CSV_B)

    assert refusal.value.expected_identifier == _CSV_B
    assert refusal.value.payload_identifier == _CSV_A
    assert refusal.value.context is not None
    assert refusal.value.context["expected_identifier"] == _CSV_B
    assert refusal.value.context["payload_identifier"] == _CSV_A


def test_no_unverified_full_scan_survives_on_the_base() -> None:
    """Both scans route through the one identity-checking helper.

    STRUCTURAL, and deliberately so. Verification used to be reachable only
    through an opt-in ``iter_verified_records`` while ``iter_records`` and
    ``iter_ids`` stayed unchecked, which is fail-open by construction: the
    callers least likely to opt in are the ones that filter on payload fields
    and so are most exposed to a foreign row. No input can distinguish "the
    default verifies" from "a second unverified scan was reintroduced beside
    it" -- a new unchecked method is invisible to every behavioural test until
    something starts calling it. This is what notices.
    """
    scan_sources = {
        name: inspect.getsource(getattr(SecureBoundRepository, name)) for name in ("iter_records", "iter_ids")
    }
    for name, source in scan_sources.items():
        assert _calls(source, "_iter_identified_payloads"), f"{name} does not route through the verifying scan"

    verifier = inspect.getsource(SecureBoundRepository._iter_identified_payloads)
    assert "secure_object_key_digest(" in verifier, "the scan no longer recomputes the row key"
    assert "raise SecureObjectRowIdentityError(" in verifier, "the scan no longer refuses a misfiled row"

    public_scans = {
        name for name in vars(SecureBoundRepository) if not name.startswith("_") and name.startswith("iter")
    }
    assert public_scans == {"iter_records", "iter_ids"}, (
        f"an additional public scan surface exists: {sorted(public_scans)}; "
        "a second scan beside the verifying one re-opens the fail-open gap"
    )


def _calls(source: str, callee: str) -> bool:
    """Whether ``source`` actually CALLS ``callee``, not merely mentions it.

    The delegation half of this gate asked whether the verifying scan's NAME
    appeared in each public scan's source. A scan that stopped routing through
    it while keeping a sentence naming it passed -- which is the reintroduced
    unverified scan this module exists to notice.

    The two checks BELOW this one stay textual on purpose: they assert the
    verifier still contains its own recompute and its own refusal, where a
    stray mention fails safe by refusing something harmless rather than
    admitting an unverified scan.
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
    """DISCRIMINATING: a mention is not a call."""
    routing = "def iter_records(self):\n    return self._iter_identified_payloads()\n"
    mentioning = (
        "def iter_records(self):\n"
        '    """Rows come from _iter_identified_payloads() upstream."""\n'
        "    return self._raw_rows()\n"
    )

    assert _calls(routing, "_iter_identified_payloads")
    assert not _calls(mentioning, "_iter_identified_payloads")
