"""The submitted fichero's complementaria byte is the only capture evidence of a filing kind.

The positions are transcribed from AEAT's record designs, not read from the
code under test: Modelo 130 "Declaración complementaria" at position 432;
Modelo 131 at 613 in the 2019-2023 design and 692 from 2024. Each design gives
the byte the domain ``blanco o "X"``. The Modelo 131 DPA record's "Indicador de
página complementaria" at position 12 marks a continuation page and is no
evidence of the filing kind.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ......application.filing.draft_construction import build_draft
from ......application.filing.export import export_draft
from ......application.filing.producer_snapshot import GeneralFilingProfileFacts, build_filing_producer_snapshot
from ......application.filing.runtime import ModeloOperatorProfile
from ......application.filing.tests.export_support import export_schema_provider, typed_producer_snapshot
from ......application.live.filed_observation_persistence import filed_observation_filing_kind
from ......core.casilla_id import validated_casilla_id
from ......core.modelo import Modelo
from ......core.period import Period
from ......core.prior_domiciliation_election import PriorDomiciliationElection
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.calculations.registry.binding_targets import revision_bindings_by_id
from ......domain.calculations.registry.export import resolve_export_layout
from ......domain.calculations.registry.filing_kind_marker import FilingKindMarkerRole, filing_kind_marker_role
from ......domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    authored_revisions_where,
    filing_year_envelope,
)
from ......domain.filing.software_identity import development_mock_software_identity
from ......domain.modelos.filing_kind_evidence import (
    FilingKindEvidenceBasis,
    FilingKindUnknownReason,
    SubmittedFileFilingKindMarker,
    submitted_file_marker_reading,
)
from ......domain.modelos.filing_record import FilingDeclarationKind
from ......domain.submission.models import ModeloDraftStatus
from ..declarations_capture import relation_source_gaps
from ..declarations_observations import observed_filing_kind_marker_from_submitted_file
from ..schema import FiledDeclaracionObservation
from .declarations_support import filed_observation, modelo_130_snapshot, submitted_file_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_YEAR = filing_year_envelope().horizon

_C18 = validated_casilla_id("18", surface="test_declarations_filing_kind_marker.casilla")
_C19 = validated_casilla_id("19", surface="test_declarations_filing_kind_marker.casilla")
_M130_PAGE_01_OPEN_TAG = b"<T13001000>"
_M130_MARKER_OFFSET = 432


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period", "marker_offset"),
    [
        ("130", 2022, "1T", 432),
        ("130", 2026, "1T", 432),
        ("131", 2022, "1T", 613),
        ("131", 2023, "4T", 613),
        ("131", 2024, "1T", 692),
        ("131", 2025, "2T", 692),
        ("131", 2026, "1T", 692),
        ("131", 2026, "3T", 692),
    ],
)
def test_each_published_layout_names_exactly_the_design_positions(
    operation: PinnedAuthorityOperation,
    modelo: str,
    filing_year: int,
    period: str,
    marker_offset: int,
) -> None:
    snapshot = operation.snapshot(modelo, filing_year=filing_year, period=period)
    resolved = resolve_export_layout(snapshot)
    bindings_by_id = revision_bindings_by_id(snapshot.revision)
    roles: dict[FilingKindMarkerRole, list[int | None]] = {}
    for field in resolved.fields_by_id.values():
        role = filing_kind_marker_role(field, bindings_by_id=bindings_by_id)
        if role is not None:
            roles.setdefault(role, []).append(field.offset)

    assert roles.get(FilingKindMarkerRole.DECLARATION_MARKER) == [marker_offset]
    assert set(roles) == {FilingKindMarkerRole.DECLARATION_MARKER}


def _m130_body_with_marker(token: bytes) -> bytes:
    body = submitted_file_payload()
    position = body.index(_M130_PAGE_01_OPEN_TAG) + _M130_MARKER_OFFSET - 1
    assert body[position : position + 1] == b" "
    return body[:position] + token + body[position + 1 :]


@pytest.mark.parametrize(
    ("token", "kind"),
    [(b" ", FilingDeclarationKind.ORIGINAL), (b"X", FilingDeclarationKind.COMPLEMENTARIA)],
)
def test_the_modelo_130_fichero_marker_admits_the_kind_it_states(
    operation: PinnedAuthorityOperation, token: bytes, kind: FilingDeclarationKind
) -> None:
    marker = observed_filing_kind_marker_from_submitted_file(
        snapshot=modelo_130_snapshot(operation=operation),
        body=_m130_body_with_marker(token),
        operation=operation,
    )

    assert marker is not None
    assert marker.declaration_marker.kind is kind
    assert marker.declaration_marker.source_locator.endswith(":432:1")


def test_an_unparseable_fichero_reads_no_marker_and_the_capture_kind_is_unknown(
    operation: PinnedAuthorityOperation,
) -> None:
    body = submitted_file_payload()
    marker = observed_filing_kind_marker_from_submitted_file(
        snapshot=modelo_130_snapshot(operation=operation),
        body=body[: len(body) // 2],
        operation=operation,
    )
    observation = filed_observation(modelo="130", ejercicio=_YEAR, period="1T", casilla_values={})

    assert marker is None
    filing_kind = filed_observation_filing_kind(observation.model_copy(update={"filing_kind_marker": marker}))
    assert filing_kind.basis is FilingKindEvidenceBasis.NONE
    assert filing_kind.unknown_reason is FilingKindUnknownReason.NO_ADMITTED_EVIDENCE


def _marker(token: str) -> SubmittedFileFilingKindMarker:
    return SubmittedFileFilingKindMarker(
        declaration_marker=submitted_file_marker_reading(token, source_locator="modelo-130-fichero-boe:page-01:432:1"),
    )


def _m130_quarter(
    values: dict[str, Decimal], *, marker: SubmittedFileFilingKindMarker | None
) -> FiledDeclaracionObservation:
    observation = filed_observation(
        modelo="130",
        ejercicio=_YEAR,
        period="2T",
        casilla_values={validated_casilla_id(key, surface="test.casilla"): value for key, value in values.items()},
    )
    return observation.model_copy(update={"filing_kind_marker": marker})


def test_a_register_request_type_that_disagrees_with_the_marker_makes_the_kind_unknown() -> None:
    observation = _m130_quarter({"19": Decimal("10.00")}, marker=_marker(" "))
    observation = observation.model_copy(
        update={"metadata": {**observation.metadata, "tipo_solicitud": "Complementaria"}}
    )

    filing_kind = filed_observation_filing_kind(observation)

    assert filing_kind.basis is FilingKindEvidenceBasis.NONE
    assert filing_kind.unknown_reason is FilingKindUnknownReason.DISAGREEMENT


@pytest.mark.parametrize(
    ("values", "marker", "missing", "contradicted"),
    [
        ({"19": Decimal("300.00")}, _marker(" "), [], []),
        ({"19": Decimal("300.00")}, None, [_C18], []),
        ({"19": Decimal("300.00")}, _marker("X"), [_C18], []),
        ({"18": Decimal("120.00"), "19": Decimal("300.00")}, _marker(" "), [], [_C18]),
        ({"18": Decimal("120.00"), "19": Decimal("40.00")}, _marker("X"), [], []),
        ({"18": Decimal("120.00")}, _marker("X"), [_C19], []),
    ],
    ids=(
        "original-absent-proven-zero",
        "no-marker-absent-missing",
        "complementaria-absent-missing",
        "original-nonzero-contradicted",
        "complementaria-observed",
        "other-casilla-still-required",
    ),
)
def test_live_relation_capture_applies_the_shared_complementaria_only_predicate(
    operation: PinnedAuthorityOperation,
    values: dict[str, Decimal],
    marker: SubmittedFileFilingKindMarker | None,
    missing: list[object],
    contradicted: list[object],
) -> None:
    observation = _m130_quarter(values, marker=marker)

    assert relation_source_gaps(observation, {_C18, _C19}, operation=operation) == (missing, contradicted)


_M131_PAGE_01_OPEN_TAG = b"<T13101000>"
_M131_MARKER_OFFSET = 692
_M131_DPA_OPEN_TAG = b"<T131DPA00>"
_M131_PAGE_INDICATOR_POSITION = 12
_M131_CASILLA_03 = validated_casilla_id("03", surface="test_declarations_filing_kind_marker.casilla")
_M131_CASILLA_05 = validated_casilla_id("05", surface="test_declarations_filing_kind_marker.casilla")


def _m131_multi_activity_file(tmp_path: Path, *, complementaria: bool, filing_year: int, period: str = "1T") -> bytes:
    """Export a two-activity Modelo 131 fichero through the real renderer."""
    template = typed_producer_snapshot(complementaria=complementaria)
    producer_snapshot = build_filing_producer_snapshot(
        modelo=Modelo("131"),
        taxpayer_tax_id=template.taxpayer_tax_id,
        taxpayer_identity=template.taxpayer_identity,
        presenter=template.presenter,
        model_profile=GeneralFilingProfileFacts(),
        elections=template.elections,
        amendment_evidence=template.amendment_evidence,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )
    provider = export_schema_provider(filing_year=filing_year, period=period, modelos=("131",))
    draft = build_draft(
        modelo="131",
        period=Period.from_year_and_code(filing_year, period),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Filing kind fixture"),
        inputs={
            _M131_CASILLA_03: Decimal("1000"),
            _M131_CASILLA_05: Decimal("500"),
            "modelo-131.page1.actividad-1-epigrafe": "722",
            "modelo-131.page1.actividad-1-rendimiento-neto": Decimal("1200.50"),
            "modelo-131.dpa.epigrafe-iae": ["722", "845"],
            "modelo-131.did.iban": "ES9121000418450200051332",
            **({"modelo-131-resultados-negativos-anteriores": Decimal("0")} if period != "1T" else {}),
        },
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    output_path = tmp_path / "modelo-131.txt"
    export_draft(
        draft,
        output_path=output_path,
        producer_snapshot=producer_snapshot,
        product_software_identity=development_mock_software_identity(),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        schema_provider=provider,
    )
    return output_path.read_bytes()


@pytest.mark.parametrize(
    ("complementaria", "kind"),
    [(False, FilingDeclarationKind.ORIGINAL), (True, FilingDeclarationKind.COMPLEMENTARIA)],
)
def test_a_modelo_131_continuation_page_indicator_never_disagrees_with_the_page_01_marker(
    operation: PinnedAuthorityOperation, tmp_path: Path, complementaria: bool, kind: FilingDeclarationKind
) -> None:
    body = _m131_multi_activity_file(tmp_path, complementaria=complementaria, filing_year=_YEAR)
    page_one = body.index(_M131_PAGE_01_OPEN_TAG) + _M131_MARKER_OFFSET - 1
    assert body[page_one : page_one + 1] == (b"X" if complementaria else b" ")
    starts = [index for index in range(len(body)) if body.startswith(_M131_DPA_OPEN_TAG, index)]
    position = _M131_PAGE_INDICATOR_POSITION
    assert [body[start + position - 1 : start + position] for start in starts] == [b" ", b"C"]

    marker = observed_filing_kind_marker_from_submitted_file(
        snapshot=operation.snapshot("131", filing_year=_YEAR, period="1T"),
        body=body,
        operation=operation,
    )
    observation = filed_observation(modelo="131", ejercicio=_YEAR, period="1T", casilla_values={})

    assert marker is not None
    assert marker.declaration_marker.token == ("X" if complementaria else "")
    assert marker.declaration_marker.source_locator.endswith(":692:1")
    filing_kind = filed_observation_filing_kind(observation.model_copy(update={"filing_kind_marker": marker}))
    assert filing_kind.kind is kind
    assert filing_kind.basis is FilingKindEvidenceBasis.SUBMITTED_FILE_MARKER
    assert filing_kind.unknown_reason is None
    assert [reading.token for reading in filing_kind.readings] == [marker.declaration_marker.token]


_M131_DPA_INPUT_KEYS = frozenset({"modelo-131.dpa.epigrafe-iae", "modelo-131.did.iban"})


def _authored_edition_probes() -> list[object]:
    """One probe per authored Modelo 131 edition in the envelope that declares the multi-activity export inputs.

    Each probe is the edition's first supported exercise and the first period
    its selector serves in it, so a split exercise yields one probe per design.
    """
    envelope = filing_year_envelope()
    declaring = {
        str(revision.id)
        for revision in authored_revisions_where(
            "131",
            lambda revision: (
                {str(item.id) for item in revision.casillas} | {str(item.id) for item in revision.bindings}
                >= _M131_DPA_INPUT_KEYS
            ),
        )
    }
    return [
        pytest.param(year, revision.period_selector.periods_for_year(year)[0], id=str(revision.id))
        for revision in authored_revisions("131")
        if str(revision.id) in declaring
        and (year := max(revision.valid_from.year, envelope.floor))
        <= (revision.valid_to.year if revision.valid_to is not None else envelope.horizon)
    ]


@pytest.mark.parametrize(
    ("filing_year", "period"),
    _authored_edition_probes(),
)
@pytest.mark.parametrize(
    ("complementaria", "kind"),
    [(False, FilingDeclarationKind.ORIGINAL), (True, FilingDeclarationKind.COMPLEMENTARIA)],
)
def test_an_exported_modelo_131_fichero_reads_back_as_the_kind_it_was_exported_with(
    operation: PinnedAuthorityOperation,
    tmp_path: Path,
    filing_year: int,
    period: str,
    complementaria: bool,
    kind: FilingDeclarationKind,
) -> None:
    body = _m131_multi_activity_file(tmp_path, complementaria=complementaria, filing_year=filing_year, period=period)

    marker = observed_filing_kind_marker_from_submitted_file(
        snapshot=operation.snapshot("131", filing_year=filing_year, period=period),
        body=body,
        operation=operation,
    )

    assert marker is not None
    assert marker.declaration_marker.token == ("X" if complementaria else "")
    assert marker.declaration_marker.kind is kind
