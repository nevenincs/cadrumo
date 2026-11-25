"""The withholding source files each perceptor's declared filing name and reports the names it cannot file.

Drives the real resolver over the published Modelo 190 layout: the name slot of a
type-2 record holds the name the person declared for that perceptor, never the
name the retention source printed, and a perceptor with no declared name leaves
the slot without content and is named once, with its door, in a diagnostic.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....core.aggregation import AggregationCaptureKind, RetencionClave
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition, revision_covering
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ....domain.filing.declared_party_name import DeclaredPartyFilingName, DeclaredPartyKind
from ....domain.filing.declared_party_name_filing import DECLARED_PARTY_NAME_DOOR_ACTION_ID
from ...invoices.source_resolver_ports import InvoiceSourcePersistenceError
from ...modelo.calculation_notes import note_record_verdict
from ..percepciones_observations_repository import PercepcionObservationPorts
from ..retencion_observations_repository import RetencionObservationPorts
from ..source_mesh import CalculationSourceContext
from ..withholding_source import WithholdingSourceResolver
from .test_withholding_source_resolver import (
    _EmptyRetencionObservationRepository,
    _InMemoryPercepcionObservationRepository,
)
from .withholding_filer_profile_support import withholding_work_profile
from .withholding_observation_support import perceptor_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NAME_BINDING = "modelo-190-perceptor-row-name"
_EXERCISE = newest_authored_edition("190")
_NAMED = "00001500M"
_UNNAMED = "00001501Y"
_NATURAL = DeclaredPartyFilingName(
    kind=DeclaredPartyKind.NATURAL_PERSON, primer_apellido="GARCIA", segundo_apellido="LOPEZ", nombre="ANA MARIA"
)


class _FilingNames:
    """Reader of the names a person declared, keyed by the identifier alone."""

    def __init__(self, names: dict[str, DeclaredPartyFilingName], *, unreadable: bool = False) -> None:
        self._names = names
        self._unreadable = unreadable
        self.asked: list[tuple[str, str | None]] = []

    def filing_name_of(self, tax_identifier: str, *, country_code: str | None) -> DeclaredPartyFilingName | None:
        if self._unreadable:
            raise InvoiceSourcePersistenceError("counterparty_filing_name_load")
        self.asked.append((tax_identifier, country_code))
        return self._names.get(tax_identifier)


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _resolver(filing_names: _FilingNames | None) -> WithholdingSourceResolver:
    repository = _InMemoryPercepcionObservationRepository()
    for quarter in ("1T", "2T", "3T", "4T"):
        repository.replace_observations(
            modelo="111",
            filing_year=_EXERCISE,
            period=Period.from_year_and_code(_EXERCISE, quarter),
            observations=[_observation(_NAMED, quarter), _observation(_UNNAMED, quarter)] if quarter == "1T" else [],
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
    return WithholdingSourceResolver(
        ports=PercepcionObservationPorts(repository=repository),
        retencion_ports=RetencionObservationPorts(repository=_EmptyRetencionObservationRepository()),
        filing_names=filing_names,
    )


def _observation(tax_id: str, quarter: str) -> WithholdingObservation:
    return perceptor_observation(tax_id, RetencionClave.from_registry("A")).model_copy(
        update={"perceptor_legal_name": f"IMPRESO {tax_id} {quarter}"}
    )


def _context(operation: PinnedAuthorityOperation) -> CalculationSourceContext:
    return CalculationSourceContext(
        operation=operation,
        bucket_id="operator",
        modelo="190",
        filing_year=_EXERCISE,
        period=Period.from_year_and_code(_EXERCISE, "0A"),
        revision=operation.revision_with_export_layouts("190", str(revision_covering("190", _EXERCISE).id)),
        profile=withholding_work_profile(operation),
    )


def test_each_perceptor_row_files_its_declared_name_and_never_the_printed_one(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    reader = _FilingNames({_NAMED: _NATURAL, _UNNAMED: _NATURAL.model_copy(update={"primer_apellido": "RUIZ"})})

    resolution = _resolver(reader).resolve(_context(authority_operation))

    names = sorted(
        str(value) for (binding, _), value in resolution.row_binding_values.items() if binding == _NAME_BINDING
    )
    assert names == ["GARCIA LOPEZ ANA MARIA", "RUIZ LOPEZ ANA MARIA"]
    assert not [item for item in resolution.diagnostics if item.reason == "declared_party_name_unresolved"]
    assert {tax_id for tax_id, _ in reader.asked} == {_NAMED, _UNNAMED}
    assert {country for _, country in reader.asked} == {None}


def test_a_perceptor_with_no_declared_name_is_named_once_with_its_door_and_its_slot_is_left_empty(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    resolution = _resolver(_FilingNames({_NAMED: _NATURAL})).resolve(_context(authority_operation))

    names = [str(value) for (binding, _), value in resolution.row_binding_values.items() if binding == _NAME_BINDING]
    assert names == ["GARCIA LOPEZ ANA MARIA"]
    (diagnostic,) = [item for item in resolution.diagnostics if item.reason == "declared_party_name_unresolved"]
    assert (diagnostic.source_ref or "").startswith("party-name:missing:")
    assert "IMPRESO" in diagnostic.message or _UNNAMED in diagnostic.message
    verdict = note_record_verdict(diagnostic.reason, diagnostic.fact)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == DECLARED_PARTY_NAME_DOOR_ACTION_ID


def test_a_resolver_composed_without_filing_names_fills_no_name_slot_and_reports_none(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    resolution = _resolver(None).resolve(_context(authority_operation))

    assert not [key for key in resolution.row_binding_values if key[0] == _NAME_BINDING]
    assert not [item for item in resolution.diagnostics if item.reason == "declared_party_name_unresolved"]


def test_unreadable_declared_names_degrade_the_source_instead_of_reporting_missing_names(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    resolution = _resolver(_FilingNames({}, unreadable=True)).resolve(_context(authority_operation))

    assert [item.reason for item in resolution.diagnostics] == ["storage_degraded"]
    assert not resolution.row_binding_values
