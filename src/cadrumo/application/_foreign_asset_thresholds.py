"""Registry-resolved thresholds for Modelo 720 and Modelo 721 foreign assets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType

from ..core import (
    ForeignAssetObligationGroup,
    Modelo,
    RevisionReviewStatus,
    obligation_groups_established_by_legal_refs,
)
from ..core.resources import bundled_path
from ..domain.calculations.registry.errors import RegistryValidationError
from ..domain.calculations.registry.formula_runtime_ops import resolve_parameter
from ..domain.calculations.registry.loader import load_registry_tree
from ..domain.calculations.registry.schema import ModeloRevision
from ..domain.calculations.registry.schema_formula import ParameterDefinition
from ..domain.calculations.registry.temporal import select_revision

_ANNUAL_PERIOD = "0A"
_INITIAL_PARAMETER_IDS = {
    Modelo.M720: "modelo-720-asset-declaration-threshold-eur",
    Modelo.M721: "modelo-721-asset-declaration-threshold-eur",
}
_REDECLARATION_PARAMETER_IDS = {
    Modelo.M720: "modelo-720-redeclaration-increment-threshold-eur",
    Modelo.M721: "modelo-721-redeclaration-increment-threshold-eur",
}


@dataclass(frozen=True, slots=True)
class ForeignAssetDeclarationThreshold:
    """One selected revision's declaration and re-declaration limits for a bloque."""

    group: ForeignAssetObligationGroup
    initial_declaration_floor_eur: Decimal
    redeclaration_increase_delta_eur: Decimal
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    revision_review_status: RevisionReviewStatus
    """Whether a human has attested the revision these figures were read from.

    Carried beside ``legal_refs`` and ``source_refs`` because it is the same kind
    of fact: provenance travelling with the value. Obligation is answered from an
    unattested revision on purpose — refusing would make a legal duty
    unanswerable rather than merely unfilable — but the answer then rests on a
    figure nobody has verified, and a taxpayer told they fall BELOW a wrong
    threshold misses a penalised filing obligation silently.

    This field only makes that knowable. It is not a disposition and it lets no
    gate pass: the filing path still refuses an unattested revision. Surfacing it
    to the operator belongs at the CLI envelope's ``notices`` channel, which no
    caller of this module currently reaches.
    """

    @property
    def is_operator_attested(self) -> bool:
        """Whether the figures rest on a revision a human has signed off."""
        return self.revision_review_status is RevisionReviewStatus.OPERATOR_REVIEWED


def foreign_asset_declaration_thresholds(
    *,
    modelo: str,
    filing_year: int,
) -> Mapping[ForeignAssetObligationGroup, ForeignAssetDeclarationThreshold]:
    """Resolve foreign-asset thresholds from the selected bundled registry revision.

    Deciding whether a taxpayer is OBLIGED to declare happens before, and
    independently of, filing: a filing-grade snapshot would additionally
    require operator review, so an unreviewed revision would make the
    obligation unanswerable rather than merely unfilable. The filing path
    builds its own filing-grade snapshot when it files.

    Reads directly through ``load_registry_tree`` + ``select_revision``
    rather than :class:`~domain.calculations.registry.ValidatedRegistryAuthority`:
    obtaining that authority object at all means its ``.load()``'s
    unconditional, tree-wide ``validate_registry()`` call, which refuses
    whenever ANY modelo anywhere lacks an export layout -- entirely unrelated
    to whether this modelo's own obligation can be answered.
    """
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    definition = next(candidate for candidate in modelos if candidate.id == modelo)
    selected = select_revision(
        definition,
        filing_year=filing_year,
        period=_ANNUAL_PERIOD,
        on=date(filing_year, 12, 31),
    )
    return foreign_asset_declaration_thresholds_for_parameters(
        modelo=modelo,
        parameters=selected.parameters,
        filing_date=date(filing_year, 12, 31),
        revision_review_status=selected.review_status,
    )


def foreign_asset_declaration_thresholds_for_revision(
    *,
    modelo: str,
    revision: ModeloRevision,
    filing_date: date,
) -> Mapping[ForeignAssetObligationGroup, ForeignAssetDeclarationThreshold]:
    """Resolve the threshold parameters declared by one already-selected revision.

    Args:
        modelo: The Modelo 720/721 code the thresholds are declared under.
        revision: The already-selected :class:`ModeloRevision` whose
            parameters carry the initial-declaration and re-declaration
            threshold values.
        filing_date: The date used to resolve a date-scoped parameter value.
    """
    return foreign_asset_declaration_thresholds_for_parameters(
        modelo=modelo,
        parameters=revision.parameters,
        filing_date=filing_date,
        revision_review_status=revision.review_status,
    )


def foreign_asset_declaration_thresholds_for_parameters(
    *,
    modelo: str,
    parameters: Sequence[ParameterDefinition],
    filing_date: date,
    revision_review_status: RevisionReviewStatus,
) -> Mapping[ForeignAssetObligationGroup, ForeignAssetDeclarationThreshold]:
    """Resolve the thresholds from a already-selected revision's parameter declarations.

    The parameters are the whole input, so a caller holding a non-filing revision
    projection can resolve an obligation threshold without constructing a
    filing-grade snapshot it has no use for.

    Args:
        modelo: The Modelo 720/721 code the thresholds are declared under.
        parameters: The selected revision's parameter declarations.
        filing_date: The date used to resolve a date-scoped parameter value.
        revision_review_status: The selected revision's attestation stamp, carried
            onto every threshold so a consumer can tell whether the figures rest
            on a revision a human has verified.
    """
    try:
        modelo_member = Modelo(modelo)
    except ValueError as exc:
        raise RegistryValidationError(f"modelo {modelo!r} has no foreign-asset threshold parameter contract") from exc
    initial_parameter_id = _INITIAL_PARAMETER_IDS.get(modelo_member)
    redeclaration_parameter_id = _REDECLARATION_PARAMETER_IDS.get(modelo_member)
    if initial_parameter_id is None or redeclaration_parameter_id is None:
        raise RegistryValidationError(f"modelo {modelo!r} has no foreign-asset threshold parameter contract")
    by_id = {parameter.id: parameter for parameter in parameters}
    initial = _required_parameter(by_id, initial_parameter_id, modelo)
    redeclaration = _required_parameter(by_id, redeclaration_parameter_id, modelo)
    date_context = {"filing_period": filing_date}
    initial_value = resolve_parameter(initial, date_context)
    redeclaration_value = resolve_parameter(redeclaration, date_context)
    legal_refs = tuple(sorted(set(initial.legal_refs) | set(redeclaration.legal_refs)))
    source_refs = tuple(sorted(set(initial.source_refs) | set(redeclaration.source_refs)))
    groups = tuple(sorted(obligation_groups_established_by_legal_refs(legal_refs), key=lambda group: group.value))
    if not groups:
        raise RegistryValidationError(
            f"modelo {modelo} revision cites no RGAT provision establishing a foreign-asset bloque, "
            "so its thresholds have no scope to apply to; the obligation's scope is read from the "
            "establishing articles the threshold parameters declare in legal_refs",
        )
    thresholds = {
        group: ForeignAssetDeclarationThreshold(
            group=group,
            initial_declaration_floor_eur=initial_value,
            redeclaration_increase_delta_eur=redeclaration_value,
            legal_refs=legal_refs,
            source_refs=source_refs,
            revision_review_status=revision_review_status,
        )
        for group in groups
    }
    return MappingProxyType(thresholds)


def _required_parameter(
    parameters: Mapping[str, ParameterDefinition],
    parameter_id: str,
    modelo: str,
) -> ParameterDefinition:
    try:
        return parameters[parameter_id]
    except KeyError as exc:
        raise RegistryValidationError(
            f"modelo {modelo} revision is missing foreign-asset parameter {parameter_id!r}",
        ) from exc


__all__ = [
    "ForeignAssetDeclarationThreshold",
    "foreign_asset_declaration_thresholds",
    "foreign_asset_declaration_thresholds_for_parameters",
    "foreign_asset_declaration_thresholds_for_revision",
]
