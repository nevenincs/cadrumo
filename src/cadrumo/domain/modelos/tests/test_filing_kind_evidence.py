"""Filing-kind evidence admits only the submitted-file marker and a local revision.

The expected kinds are transcribed from the record designs' value domains --
"Declaración complementaria" is ``blanco o "X"`` and the Modelo 131 page
indicator is ``Blanco (No complementaria) o "C"`` -- never read from the code
under test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.casilla_id import validated_casilla_id
from ..calculation_revision_amendment import (
    CalculationRevisionAmendmentIdentity,
    CalculationRevisionAmendmentKind,
    filing_declaration_kind_for_amendment,
)
from ..filing_kind_evidence import (
    UNKNOWN_FILING_KIND,
    ComplementariaOnlySourceOutcome,
    FilingKindEvidenceBasis,
    FilingKindReadingSource,
    FilingKindUnknownReason,
    ObservedFilingKind,
    SubmittedFileFilingKindMarker,
    complementaria_only_source_outcome,
    filing_kind_or_unknown,
    observed_filing_kind_for_local_revision,
    observed_filing_kind_from_capture,
    register_tipo_solicitud_reading,
    submitted_file_marker_reading,
    submitted_file_page_indicator_reading,
)
from ..filing_record import FilingDeclarationKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_C18 = validated_casilla_id("18", surface="test_filing_kind_evidence.casilla")
_C19 = validated_casilla_id("19", surface="test_filing_kind_evidence.casilla")
_MARKER_LOCATOR = "modelo-130-fichero-boe:modelo-130-page-01:modelo-130-page-01-declaracion-complementaria:432:1"
_DPA_LOCATOR = "modelo-131-fichero-boe:modelo-131-dpa:modelo-131-dpa-complementaria-indicator:12:1"
_REGISTER_LOCATOR = "aeat-register:202610013522223B:tipo_solicitud"


def _marker(token: str, *indicators: str) -> SubmittedFileFilingKindMarker:
    return SubmittedFileFilingKindMarker(
        declaration_marker=submitted_file_marker_reading(token, source_locator=_MARKER_LOCATOR),
        page_indicators=tuple(
            submitted_file_page_indicator_reading(indicator, source_locator=_DPA_LOCATOR) for indicator in indicators
        ),
    )


@pytest.mark.parametrize(
    ("token", "kind"),
    [
        (" ", FilingDeclarationKind.ORIGINAL),
        ("", FilingDeclarationKind.ORIGINAL),
        ("X", FilingDeclarationKind.COMPLEMENTARIA),
    ],
)
def test_the_submitted_file_marker_admits_the_kind_its_design_value_states(
    token: str, kind: FilingDeclarationKind
) -> None:
    observed = observed_filing_kind_from_capture(_marker(token))

    assert observed.kind is kind
    assert observed.basis is FilingKindEvidenceBasis.SUBMITTED_FILE_MARKER
    assert observed.admitted_kind is kind
    assert observed.source_locator == _MARKER_LOCATOR
    assert observed.unknown_reason is None


def test_a_marker_token_outside_the_design_domain_is_unknown() -> None:
    observed = observed_filing_kind_from_capture(_marker("S"))

    assert observed.basis is FilingKindEvidenceBasis.NONE
    assert observed.kind is None
    assert observed.unknown_reason is FilingKindUnknownReason.UNREADABLE_MARKER
    assert [reading.token for reading in observed.readings] == ["S"]


def test_no_marker_is_unknown_even_when_the_register_names_a_correction() -> None:
    """A register-only or PDF-fallback capture never admits a kind."""
    register = register_tipo_solicitud_reading("Complementaria", source_locator=_REGISTER_LOCATOR)

    observed = observed_filing_kind_from_capture(None, register_reading=register)

    assert observed.basis is FilingKindEvidenceBasis.NONE
    assert observed.unknown_reason is FilingKindUnknownReason.NO_ADMITTED_EVIDENCE
    assert observed.readings == (register,)
    assert observed.admitted_kind is None


@pytest.mark.parametrize("tipo_solicitud", ["Presentación", "Original", "", None])
def test_a_register_request_type_naming_no_correction_is_no_reading(tipo_solicitud: str | None) -> None:
    assert register_tipo_solicitud_reading(tipo_solicitud, source_locator=_REGISTER_LOCATOR) is None


@pytest.mark.parametrize(
    ("marker", "register"),
    [
        (_marker(" ", "C"), None),
        (_marker("X", " "), None),
        (_marker(" ", " ", "Z"), None),
        (_marker(" "), "complementaria"),
    ],
    ids=("dpa-c-beside-blank", "dpa-blank-beside-x", "dpa-unreadable", "register-beside-blank"),
)
def test_readings_naming_another_kind_make_the_kind_unknown(
    marker: SubmittedFileFilingKindMarker, register: str | None
) -> None:
    register_reading = register_tipo_solicitud_reading(register, source_locator=_REGISTER_LOCATOR)

    observed = observed_filing_kind_from_capture(marker, register_reading=register_reading)

    assert observed.basis is FilingKindEvidenceBasis.NONE
    assert observed.unknown_reason is FilingKindUnknownReason.DISAGREEMENT
    assert observed.admitted_kind is None
    sources = {reading.source for reading in observed.readings}
    assert FilingKindReadingSource.SUBMITTED_FILE_MARKER in sources


def test_agreeing_page_indicators_keep_the_marker_kind_and_add_nothing() -> None:
    observed = observed_filing_kind_from_capture(_marker("X", "C", "C"))

    assert observed.kind is FilingDeclarationKind.COMPLEMENTARIA
    assert observed.basis is FilingKindEvidenceBasis.SUBMITTED_FILE_MARKER
    assert len(observed.readings) == 3


@pytest.mark.parametrize(
    ("identity_kind", "expected"),
    [
        (None, FilingDeclarationKind.ORIGINAL),
        (CalculationRevisionAmendmentKind.COMPLEMENTARIA, FilingDeclarationKind.COMPLEMENTARIA),
        (CalculationRevisionAmendmentKind.SUSTITUTIVA, FilingDeclarationKind.SUSTITUTIVA),
        (CalculationRevisionAmendmentKind.RECTIFICATIVA, FilingDeclarationKind.RECTIFICATIVA),
    ],
)
def test_a_local_revision_is_original_without_an_amendment_identity_and_its_kind_otherwise(
    identity_kind: CalculationRevisionAmendmentKind | None, expected: FilingDeclarationKind
) -> None:
    identity = (
        None
        if identity_kind is None
        else CalculationRevisionAmendmentIdentity(
            kind=identity_kind,
            amends_filing_record_id="a" * 64,
            m303_rectificativa_motive=None,
        )
    )

    observed = observed_filing_kind_for_local_revision(
        filing_declaration_kind_for_amendment(identity),
        source_locator="local-filing:fixture",
    )

    assert observed.kind is expected
    assert observed.basis is FilingKindEvidenceBasis.LOCAL_REVISION
    assert observed.admitted_kind is expected


def test_an_absent_projection_reads_as_unknown() -> None:
    assert filing_kind_or_unknown(None) is UNKNOWN_FILING_KIND
    assert UNKNOWN_FILING_KIND.basis is FilingKindEvidenceBasis.NONE
    assert UNKNOWN_FILING_KIND.admitted_kind is None


@pytest.mark.parametrize(
    "payload",
    [
        {"basis": "none", "kind": "original", "unknown_reason": "no_admitted_evidence"},
        {"basis": "submitted_file_marker", "source_locator": _MARKER_LOCATOR},
        {"basis": "submitted_file_marker", "kind": "original"},
        {"basis": "none"},
        {"basis": "local_revision", "kind": "original", "source_locator": "x", "unknown_reason": "disagreement"},
    ],
    ids=("kind-without-basis", "basis-without-kind", "basis-without-locator", "none-without-reason", "reason-on-basis"),
)
def test_the_projection_refuses_a_kind_and_basis_that_disagree(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ObservedFilingKind.model_validate(payload)


def test_a_stored_projection_round_trips_through_json() -> None:
    observed = observed_filing_kind_from_capture(
        _marker(" ", " "),
        register_reading=None,
    )

    assert ObservedFilingKind.model_validate_json(observed.model_dump_json()) == observed


_ORIGINAL = observed_filing_kind_for_local_revision(FilingDeclarationKind.ORIGINAL, source_locator="local-filing:x")
_COMPLEMENTARIA = observed_filing_kind_for_local_revision(
    FilingDeclarationKind.COMPLEMENTARIA, source_locator="local-filing:x"
)
_DECLARED = frozenset({_C18})


@pytest.mark.parametrize(
    ("casilla_id", "value", "filing_kind", "declared", "expected"),
    [
        (_C18, None, _ORIGINAL, _DECLARED, ComplementariaOnlySourceOutcome.PROVEN_ZERO),
        (_C18, None, _COMPLEMENTARIA, _DECLARED, ComplementariaOnlySourceOutcome.UNRESOLVED),
        (_C18, None, UNKNOWN_FILING_KIND, _DECLARED, ComplementariaOnlySourceOutcome.UNRESOLVED),
        (_C18, None, _ORIGINAL, frozenset(), ComplementariaOnlySourceOutcome.UNRESOLVED),
        (_C19, None, _ORIGINAL, _DECLARED, ComplementariaOnlySourceOutcome.UNRESOLVED),
        (_C18, Decimal("0"), _ORIGINAL, _DECLARED, ComplementariaOnlySourceOutcome.OBSERVED),
        (_C18, Decimal("120.00"), _ORIGINAL, _DECLARED, ComplementariaOnlySourceOutcome.CONTRADICTED),
        (_C18, Decimal("120.00"), _COMPLEMENTARIA, _DECLARED, ComplementariaOnlySourceOutcome.OBSERVED),
        (_C18, Decimal("120.00"), UNKNOWN_FILING_KIND, _DECLARED, ComplementariaOnlySourceOutcome.OBSERVED),
    ],
    ids=(
        "original-absent-proven-zero",
        "complementaria-absent-unresolved",
        "unknown-absent-unresolved",
        "undeclared-absent-unresolved",
        "other-casilla-absent-unresolved",
        "original-observed-zero",
        "original-nonzero-contradicted",
        "complementaria-observed",
        "unknown-observed",
    ),
)
def test_only_an_admitted_original_proves_an_absent_complementaria_only_casilla_zero(
    casilla_id: object,
    value: Decimal | None,
    filing_kind: ObservedFilingKind,
    declared: frozenset[object],
    expected: ComplementariaOnlySourceOutcome,
) -> None:
    assert (
        complementaria_only_source_outcome(
            validated_casilla_id(str(casilla_id), surface="test_filing_kind_evidence.casilla"),
            observed_value=value,
            filing_kind=filing_kind,
            complementaria_only_casilla_ids=frozenset(
                validated_casilla_id(str(item), surface="test_filing_kind_evidence.casilla") for item in declared
            ),
        )
        is expected
    )
