"""The submitted fichero's complementaria byte is the only capture evidence of a filing kind.

The positions are transcribed from AEAT's record designs, not read from the
code under test: Modelo 130 "Declaración complementaria" at position 432;
Modelo 131 at 613 in the 2019-2023 design and 692 from 2024, where the DPA
record adds an "Indicador de página complementaria" at position 12. Each design
gives the byte the domain ``blanco o "X"``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ......application.live.filed_observation_persistence import filed_observation_filing_kind
from ......core.casilla_id import validated_casilla_id
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.calculations.registry.binding_targets import revision_bindings_by_id
from ......domain.calculations.registry.export import resolve_export_layout
from ......domain.calculations.registry.filing_kind_marker import FilingKindMarkerRole, filing_kind_marker_role
from ......domain.modelos.filing_kind_evidence import (
    FilingKindEvidenceBasis,
    FilingKindUnknownReason,
    SubmittedFileFilingKindMarker,
    submitted_file_marker_reading,
)
from ......domain.modelos.filing_record import FilingDeclarationKind
from ..declarations_capture import _relation_source_gaps
from ..declarations_observations import observed_filing_kind_marker_from_submitted_file
from ..schema import FiledDeclaracionObservation
from ._declarations_support import _filed_observation, _modelo_130_snapshot, _submitted_file_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_C18 = validated_casilla_id("18", surface="test_declarations_filing_kind_marker.casilla")
_C19 = validated_casilla_id("19", surface="test_declarations_filing_kind_marker.casilla")
_M130_PAGE_01_OPEN_TAG = b"<T13001000>"
_M130_MARKER_OFFSET = 432


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period", "marker_offset", "indicator_offset"),
    [
        ("130", 2022, "1T", 432, None),
        ("130", 2026, "1T", 432, None),
        ("131", 2022, "1T", 613, None),
        ("131", 2023, "4T", 613, None),
        ("131", 2024, "1T", 692, 12),
        ("131", 2025, "2T", 692, 12),
        ("131", 2026, "1T", 692, 12),
        ("131", 2026, "3T", 692, 12),
    ],
)
def test_each_published_layout_names_exactly_the_design_positions(
    operation: PinnedAuthorityOperation,
    modelo: str,
    filing_year: int,
    period: str,
    marker_offset: int,
    indicator_offset: int | None,
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
    assert roles.get(FilingKindMarkerRole.PAGE_INDICATOR) == (None if indicator_offset is None else [indicator_offset])


def _m130_body_with_marker(token: bytes) -> bytes:
    body = _submitted_file_payload()
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
        snapshot=_modelo_130_snapshot(operation=operation),
        body=_m130_body_with_marker(token),
        operation=operation,
    )

    assert marker is not None
    assert marker.page_indicators == ()
    assert marker.declaration_marker.kind is kind
    assert marker.declaration_marker.source_locator.endswith(":432:1")


def test_an_unparseable_fichero_reads_no_marker_and_the_capture_kind_is_unknown(
    operation: PinnedAuthorityOperation,
) -> None:
    body = _submitted_file_payload()
    marker = observed_filing_kind_marker_from_submitted_file(
        snapshot=_modelo_130_snapshot(operation=operation),
        body=body[: len(body) // 2],
        operation=operation,
    )
    observation = _filed_observation(modelo="130", ejercicio=2026, period="1T", casilla_values={})

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
    observation = _filed_observation(
        modelo="130",
        ejercicio=2025,
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

    assert _relation_source_gaps(observation, {_C18, _C19}, operation=operation) == (missing, contradicted)
