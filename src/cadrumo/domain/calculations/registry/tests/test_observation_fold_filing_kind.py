"""Modelo 100 casilla 0604 folds an original quarter's absent casilla 18 as zero, and nothing else.

Casilla 0604 credits, per quarter of the declarant's Modelo 130, casilla 18
plus the positive part of casilla 19 ("En el supuesto de autoliquidación
complementaria, consignaremos en esta casilla el resultado a ingresar de las
autoliquidaciones ... presentadas anteriormente"). An original has no earlier
autoliquidación, so its casilla 18 holds nothing; a complementaria's does, and an
unknown kind proves neither. The requirement is the real one the published
Modelo 100 revision declares and the complementaria-only declaration is the
published Modelo 130 one; every expected total is computed by hand below.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from ....modelos.filing_kind_evidence import (
    UNKNOWN_FILING_KIND,
    ObservedFilingKind,
    observed_filing_kind_for_local_revision,
)
from ....modelos.filing_record import FilingDeclarationKind
from ..bindings import CasillaObservation, RegistryModeloObservation
from ..errors import RegistryValidationError
from ..observation_fold import (
    SourceFilingKindEvidence,
    complementaria_only_casilla_ids,
    fold_observed_requirement_values,
    gather_observed_requirement_values,
)
from ..relations import RegistryFoldRequirement, relation_source_requirements
from .authored_editions import newest_authored_edition
from .published_authority import published_revision, published_selected_revision_id, published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_C18 = validated_casilla_id("18", surface="test_observation_fold_filing_kind.casilla")
_C19 = validated_casilla_id("19", surface="test_observation_fold_filing_kind.casilla")
_YEAR = newest_authored_edition("100")
_ORIGINAL = observed_filing_kind_for_local_revision(FilingDeclarationKind.ORIGINAL, source_locator="local-filing:q")
_COMPLEMENTARIA = observed_filing_kind_for_local_revision(
    FilingDeclarationKind.COMPLEMENTARIA, source_locator="local-filing:q"
)


def _m130_requirement() -> RegistryFoldRequirement:
    snapshot = published_snapshot("100", filing_year=_YEAR, period="0A")
    (requirement,) = [
        requirement
        for requirement in relation_source_requirements(snapshot.revision, filing_year=_YEAR, period="0A")
        if requirement.source_modelo == "130"
    ]
    assert requirement.source_casilla_ids == (_C19, _C18)
    return requirement


def _m130_complementaria_only() -> frozenset[CasillaId]:
    revision_id = published_selected_revision_id("130", filing_year=_YEAR, period="1T")
    return complementaria_only_casilla_ids(published_revision("130", revision_id))


def _quarter(period: str, values: dict[CasillaId, str]) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="130",
        filing_year=_YEAR,
        period=period,
        observations=tuple(
            CasillaObservation(
                casilla_id=casilla_id,
                value=Decimal(value),
                legal_refs=("rd-439-2007:art-110",),
                source_refs=("aeat-modelo-130-instructions",),
            )
            for casilla_id, value in values.items()
        ),
    )


def _fold(
    quarters: dict[str, tuple[dict[CasillaId, str], ObservedFilingKind]],
    *,
    complementaria_only: frozenset[CasillaId] | None = None,
) -> tuple[Decimal, tuple[tuple[str, CasillaId], ...]]:
    requirement = _m130_requirement()
    declared = _m130_complementaria_only() if complementaria_only is None else complementaria_only
    observations = tuple(_quarter(period, values) for period, (values, _) in quarters.items())
    kinds = {
        ("130", _YEAR, period): SourceFilingKindEvidence(filing_kind=kind, complementaria_only_casilla_ids=declared)
        for period, (_, kind) in quarters.items()
    }
    gathered = gather_observed_requirement_values(requirement, observations, source_filing_kinds=kinds)
    return fold_observed_requirement_values(requirement, gathered.values), gathered.proven_zero


def test_the_published_modelo_130_declares_casilla_18_complementaria_only() -> None:
    assert _m130_complementaria_only() == frozenset({_C18})


def test_four_original_quarters_without_casilla_18_credit_the_positive_results() -> None:
    """500 + max(0, -200) + 300 + 150 = 950.00, each quarter's casilla 18 proven zero."""
    total, proven_zero = _fold(
        {
            "1T": ({_C19: "500.00"}, _ORIGINAL),
            "2T": ({_C19: "-200.00"}, _ORIGINAL),
            "3T": ({_C19: "300.00"}, _ORIGINAL),
            "4T": ({_C19: "150.00"}, _ORIGINAL),
        },
    )

    assert total == Decimal("950.00")
    assert proven_zero == (("1T", _C18), ("2T", _C18), ("3T", _C18), ("4T", _C18))


def test_a_complementaria_quarter_credits_its_casilla_18_plus_its_positive_result() -> None:
    """500 + 0 + (300 + max(0, 40)) + 150 = 990.00; only the originals are proven zero."""
    total, proven_zero = _fold(
        {
            "1T": ({_C19: "500.00"}, _ORIGINAL),
            "2T": ({_C19: "-200.00"}, _ORIGINAL),
            "3T": ({_C18: "300.00", _C19: "40.00"}, _COMPLEMENTARIA),
            "4T": ({_C19: "150.00"}, _ORIGINAL),
        },
    )

    assert total == Decimal("990.00")
    assert proven_zero == (("1T", _C18), ("2T", _C18), ("4T", _C18))


@pytest.mark.parametrize(
    "kind",
    [UNKNOWN_FILING_KIND, _COMPLEMENTARIA],
    ids=("unknown-kind", "complementaria"),
)
def test_a_quarter_without_casilla_18_that_is_not_an_admitted_original_stays_unresolved(
    kind: ObservedFilingKind,
) -> None:
    with pytest.raises(RegistryValidationError, match=r"requires observed source casilla id '18'"):
        _fold(
            {
                "1T": ({_C19: "500.00"}, _ORIGINAL),
                "2T": ({_C19: "100.00"}, kind),
                "3T": ({_C19: "300.00"}, _ORIGINAL),
                "4T": ({_C19: "150.00"}, _ORIGINAL),
            },
        )


def test_without_the_registry_declaration_an_original_quarter_stays_unresolved() -> None:
    """Detector: remove the complementaria-only declaration and the original case refuses again."""
    with pytest.raises(RegistryValidationError, match=r"requires observed source casilla id '18'"):
        _fold(
            {period: ({_C19: "100.00"}, _ORIGINAL) for period in ("1T", "2T", "3T", "4T")},
            complementaria_only=frozenset(),
        )


def test_an_original_carrying_a_nonzero_casilla_18_is_refused_as_contradictory() -> None:
    with pytest.raises(RegistryValidationError, match=r"complementaria-only casilla '18'.*original"):
        _fold(
            {
                "1T": ({_C18: "120.00", _C19: "500.00"}, _ORIGINAL),
                "2T": ({_C19: "100.00"}, _ORIGINAL),
                "3T": ({_C19: "300.00"}, _ORIGINAL),
                "4T": ({_C19: "150.00"}, _ORIGINAL),
            },
        )


def test_without_filing_kind_evidence_the_fold_keeps_its_previous_refusal() -> None:
    requirement = _m130_requirement()
    observations = tuple(_quarter(period, {_C19: "10.00"}) for period in ("1T", "2T", "3T", "4T"))

    with pytest.raises(RegistryValidationError, match=r"requires observed source casilla id '18'"):
        gather_observed_requirement_values(requirement, observations)
