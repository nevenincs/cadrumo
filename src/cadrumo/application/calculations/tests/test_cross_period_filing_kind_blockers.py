"""The cross-period clean-state gate applies the same complementaria-only predicate as the fold.

A Modelo 130 quarter feeding Modelo 100 casilla 0604 must carry casillas 18 and
19. An admitted original proves an absent casilla 18 zero; a complementaria or
an unknown kind does not; an original carrying a nonzero casilla 18, or a
disagreement over the kind, is a filing-kind blocker. The complementaria-only
declaration is read from the published Modelo 130 revision the observation is
stamped with.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....domain.calculations.registry.tests.registry_observations import revision_id_for_observation
from ....domain.modelos.filing_kind_evidence import (
    UNKNOWN_FILING_KIND,
    ObservedFilingKind,
    SubmittedFileFilingKindMarker,
    observed_filing_kind_for_local_revision,
    observed_filing_kind_from_capture,
    register_tipo_solicitud_reading,
    submitted_file_marker_reading,
)
from ....domain.modelos.filing_record import FilingDeclarationKind
from ..cross_period_dependency_evaluation import declared_source_blockers
from ..cross_period_models import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
)
from ..observations_repository import ObservationEnvelopePayload, ObservationSourceKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_C18 = validated_casilla_id("18", surface="test_cross_period_filing_kind_blockers.casilla")
_C19 = validated_casilla_id("19", surface="test_cross_period_filing_kind_blockers.casilla")
_PERIOD = Period.from_year_and_code(2025, "2T")
_ORIGINAL = observed_filing_kind_for_local_revision(FilingDeclarationKind.ORIGINAL, source_locator="local-filing:q2")
_COMPLEMENTARIA = observed_filing_kind_for_local_revision(
    FilingDeclarationKind.COMPLEMENTARIA, source_locator="local-filing:q2"
)
_DISAGREEMENT = observed_filing_kind_from_capture(
    SubmittedFileFilingKindMarker(
        declaration_marker=submitted_file_marker_reading("", source_locator="m130:432:1"),
    ),
    register_reading=register_tipo_solicitud_reading("Complementaria", source_locator="aeat-register:m130:tipo"),
)

_REQUIREMENT = CrossPeriodDependencyRequirement(
    source_modelo="130",
    filing_year=2025,
    period=_PERIOD,
    source_casilla_ids=(_C19, _C18),
    origin=CrossPeriodDependencyOrigin.REGISTRY_RELATION,
    origin_ids=("renta-modelo-130-pagos-fraccionados",),
    legal_refs=("rd-439-2007:art-110",),
    source_refs=("aeat-modelo-130-instructions",),
)


def _payload(values: dict[str, str], filing_kind: ObservedFilingKind | None) -> ObservationEnvelopePayload:
    observation = RegistryModeloObservation(
        modelo="130",
        filing_year=2025,
        period="2T",
        observations=tuple(
            CasillaObservation(
                casilla_id=validated_casilla_id(key, surface="test.casilla"),
                value=Decimal(value),
                legal_refs=("rd-439-2007:art-110",),
                source_refs=("aeat-modelo-130-instructions",),
            )
            for key, value in values.items()
        ),
    )
    return ObservationEnvelopePayload(
        observation=observation,
        captured_at=datetime(2025, 7, 20, 9, 0, 0, tzinfo=UTC),
        source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
        stamped_revision_id=revision_id_for_observation(observation),
        filing_kind=filing_kind,
    )


@pytest.mark.parametrize(
    ("values", "filing_kind", "expected"),
    [
        ({"19": "300.00"}, _ORIGINAL, []),
        ({"19": "300.00"}, None, [CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA]),
        ({"19": "300.00"}, UNKNOWN_FILING_KIND, [CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA]),
        ({"19": "300.00"}, _COMPLEMENTARIA, [CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA]),
        ({"18": "120.00", "19": "40.00"}, _COMPLEMENTARIA, []),
        ({"18": "120.00", "19": "300.00"}, _ORIGINAL, [CrossPeriodCleanStateBlocker.FILING_KIND_DISAGREEMENT]),
        ({"18": "0", "19": "300.00"}, _ORIGINAL, []),
        (
            {"19": "300.00"},
            _DISAGREEMENT,
            [
                CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA,
                CrossPeriodCleanStateBlocker.FILING_KIND_DISAGREEMENT,
            ],
        ),
        ({"18": "0", "19": "300.00"}, _DISAGREEMENT, [CrossPeriodCleanStateBlocker.FILING_KIND_DISAGREEMENT]),
    ],
    ids=(
        "original-absent-proven-zero",
        "legacy-row-absent-missing",
        "unknown-absent-missing",
        "complementaria-absent-missing",
        "complementaria-observed",
        "original-nonzero-contradicted",
        "original-observed-zero",
        "disagreement-absent",
        "disagreement-observed",
    ),
)
def test_the_clean_state_gate_reads_filing_kind_through_the_shared_predicate(
    operation: PinnedAuthorityOperation,
    values: dict[str, str],
    filing_kind: ObservedFilingKind | None,
    expected: list[CrossPeriodCleanStateBlocker],
) -> None:
    assert declared_source_blockers(_REQUIREMENT, _payload(values, filing_kind), operation=operation) == expected
