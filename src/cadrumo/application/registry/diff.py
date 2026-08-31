"""Year-to-year registry revision diff for one modelo.

Surfaces what changed in the AEAT filing rulebook between two
:class:`~domain.calculations.registry.ModeloRevision` instances of the
same modelo: added/removed/renumbered casillas, changed formulas, changed
``legal_refs``, changed parameters (rates/thresholds), and added/removed
bindings.

Revision resolution reuses the same ``period_selector.includes_year`` primitive
:meth:`~domain.calculations.registry.RegistryQueryService.bindings_for_year`
already uses (see :mod:`~application.modelo.registry_discovery`): given a
bare filing year, exactly one revision must cover it, or the request is
refused naming the modelo's declared revisions.

See Also:
    :class:`~domain.calculations.registry.ValidatedRegistryAuthority`
        Loads and validates the :class:`~domain.calculations.registry.ModeloDefinition`
        this module diffs two revisions from.
    :class:`~domain.calculations.registry.ModeloRevision`
        The versioned ruleset compared by :func:`~application.registry.diff_registry_revisions`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel

from ...core.casilla_id import CasillaId as _CasillaId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.resources.bundled_data import bundled_path as _bundled_path
from ...domain.calculations.registry.authority import ValidatedRegistryAuthority as _ValidatedRegistryAuthority
from ...domain.calculations.registry.errors import AmbiguousRevisionSelectionError as _AmbiguousRevisionSelectionError
from ...domain.calculations.registry.errors import NoRevisionForPeriodError as _NoRevisionForPeriodError
from ...domain.calculations.registry.ids import FormulaId as _FormulaId
from ...domain.calculations.registry.ids import LegalRefId as _LegalRefId
from ...domain.calculations.registry.ids import ParameterId as _ParameterId
from ...domain.calculations.registry.ids import RevisionId as _RevisionId
from ...domain.calculations.registry.schema import DataBindingDefinition as _DataBindingDefinition
from ...domain.calculations.registry.schema import ModeloDefinition as _ModeloDefinition
from ...domain.calculations.registry.schema import ModeloRevision as _ModeloRevision
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition as _CasillaDefinition
from ...domain.calculations.registry.temporal import select_revision_for_year as _select_revision_for_year
from .errors import RegistryPreconditionCondition, registry_terminal_refusal

__all__ = [
    "BindingDiff",
    "CasillaDiff",
    "FormulaDiff",
    "ParameterDiff",
    "RegistryRevisionDiffReport",
    "RenumberedCasilla",
    "diff_registry_revisions",
]


class CasillaDiff(BaseModel):
    """A minimal projection of one added or removed casilla."""

    model_config = STRICT_FROZEN_CONFIG

    id: _CasillaId
    number: str
    label: str


class RenumberedCasilla(BaseModel):
    """A casilla whose ``continuidad_id`` persisted but whose id/number changed.

    Tracks a casilla whose stable ``continuidad_id`` persisted but whose AEAT
    printed ``number`` (or canonical registry ``id``) changed across
    revisions.
    """

    model_config = STRICT_FROZEN_CONFIG

    continuidad_id: str
    from_id: _CasillaId
    from_number: str
    to_id: _CasillaId
    to_number: str


class FormulaDiff(BaseModel):
    """One formula whose expression, rounding, or legal grounding changed."""

    model_config = STRICT_FROZEN_CONFIG

    id: _FormulaId
    target_casilla_id: _CasillaId
    from_expression: dict[str, object]
    to_expression: dict[str, object]
    from_legal_refs: tuple[_LegalRefId, ...]
    to_legal_refs: tuple[_LegalRefId, ...]


class ParameterDiff(BaseModel):
    """One parameter (rate/threshold/bracket table) whose declared value changed."""

    model_config = STRICT_FROZEN_CONFIG

    id: _ParameterId
    data_type: str
    from_legal_refs: tuple[_LegalRefId, ...]
    to_legal_refs: tuple[_LegalRefId, ...]


class BindingDiff(BaseModel):
    """A minimal projection of one added or removed data binding."""

    model_config = STRICT_FROZEN_CONFIG

    id: str
    source: str


class RegistryRevisionDiffReport(BaseModel):
    """Structured year-to-year diff between two revisions of one modelo."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    from_year: int
    to_year: int
    from_revision_id: _RevisionId
    to_revision_id: _RevisionId
    same_revision: bool

    added_casillas: tuple[CasillaDiff, ...]
    removed_casillas: tuple[CasillaDiff, ...]
    renumbered_casillas: tuple[RenumberedCasilla, ...]
    changed_casilla_legal_refs: tuple[_CasillaId, ...]

    added_formulas: tuple[_FormulaId, ...]
    removed_formulas: tuple[_FormulaId, ...]
    changed_formulas: tuple[FormulaDiff, ...]

    added_parameters: tuple[_ParameterId, ...]
    removed_parameters: tuple[_ParameterId, ...]
    changed_parameters: tuple[ParameterDiff, ...]

    added_bindings: tuple[BindingDiff, ...]
    removed_bindings: tuple[BindingDiff, ...]

    revision_legal_refs_added: tuple[_LegalRefId, ...]
    revision_legal_refs_removed: tuple[_LegalRefId, ...]


def _revision_for_year(
    definition: _ModeloDefinition,
    *,
    filing_year: int,
    on: date | None = None,
) -> _ModeloRevision:
    """Resolve the one revision covering ``filing_year`` through the temporal authority.

    Diffing retains its actionable no-match message, while the domain temporal
    selector owns candidate discovery, effective-date filtering, and ambiguous
    candidate errors.
    """
    try:
        return _select_revision_for_year(definition, filing_year=filing_year, on=on)
    except _AmbiguousRevisionSelectionError as exc:
        # A filing year carrying a mid-year AEAT design boundary is covered by more
        # than one revision, so there is no single "the revision for this year" to
        # diff against and picking either side would silently diff the wrong pair.
        #
        # The candidates are SURFACED, not restated: the selector's own candidate-id
        # tuple rides on the error, so this refusal quotes it rather than composing a
        # second copy that could drift from the selector's.
        raise registry_terminal_refusal(
            condition=RegistryPreconditionCondition.DIFF_REVISION_SELECTION_UNAMBIGUOUS,
            translated_message="application.registry.errors.no_revision_for_diff_year",
            context={
                "modelo": str(definition.id),
                "filing_year": filing_year,
                "available_revisions": ", ".join(exc.candidate_ids),
            },
            facts={
                "modelo": str(definition.id),
                "filing_year": filing_year,
                "revision_selection_unambiguous": False,
                "candidate_revision_count": len(exc.candidate_ids),
            },
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ) from exc
    except _NoRevisionForPeriodError as exc:
        available = ", ".join(sorted(definition.revisions))
        raise registry_terminal_refusal(
            condition=RegistryPreconditionCondition.DIFF_REVISION_AVAILABLE,
            translated_message="application.registry.errors.no_revision_for_diff_year",
            context={
                "modelo": str(definition.id),
                "filing_year": filing_year,
                "available_revisions": available,
            },
            facts={
                "modelo": str(definition.id),
                "filing_year": filing_year,
                "revision_available": False,
                "candidate_revision_count": len(definition.revisions),
            },
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ) from exc


def _casilla_legal_refs_changed(from_casilla: _CasillaDefinition, to_casilla: _CasillaDefinition) -> bool:
    return set(from_casilla.legal_refs) != set(to_casilla.legal_refs)


def _casilla_diff_projection(casilla: _CasillaDefinition) -> CasillaDiff:
    return CasillaDiff(id=casilla.id, number=casilla.number, label=casilla.label)


def _binding_diff_projection(binding: _DataBindingDefinition) -> BindingDiff:
    return BindingDiff(id=binding.id, source=binding.source.value)


def _diff_casillas(
    from_casillas: tuple[_CasillaDefinition, ...],
    to_casillas: tuple[_CasillaDefinition, ...],
) -> tuple[
    tuple[CasillaDiff, ...],
    tuple[CasillaDiff, ...],
    tuple[RenumberedCasilla, ...],
    tuple[_CasillaId, ...],
]:
    from_by_id = {casilla.id: casilla for casilla in from_casillas}
    to_by_id = {casilla.id: casilla for casilla in to_casillas}
    from_ids = set(from_by_id)
    to_ids = set(to_by_id)

    from_by_continuidad = {
        casilla.continuidad_id: casilla for casilla in from_casillas if casilla.continuidad_id is not None
    }
    to_by_continuidad = {
        casilla.continuidad_id: casilla for casilla in to_casillas if casilla.continuidad_id is not None
    }

    renumbered: list[RenumberedCasilla] = []
    renumbered_from_ids: set[_CasillaId] = set()
    renumbered_to_ids: set[_CasillaId] = set()
    for continuidad_id in sorted(set(from_by_continuidad) & set(to_by_continuidad)):
        from_casilla = from_by_continuidad[continuidad_id]
        to_casilla = to_by_continuidad[continuidad_id]
        if from_casilla.id == to_casilla.id and from_casilla.number == to_casilla.number:
            continue
        renumbered.append(
            RenumberedCasilla(
                continuidad_id=continuidad_id,
                from_id=from_casilla.id,
                from_number=from_casilla.number,
                to_id=to_casilla.id,
                to_number=to_casilla.number,
            ),
        )
        renumbered_from_ids.add(from_casilla.id)
        renumbered_to_ids.add(to_casilla.id)

    added_ids = sorted((to_ids - from_ids) - renumbered_to_ids)
    removed_ids = sorted((from_ids - to_ids) - renumbered_from_ids)
    added = tuple(_casilla_diff_projection(to_by_id[cid]) for cid in added_ids)
    removed = tuple(_casilla_diff_projection(from_by_id[cid]) for cid in removed_ids)

    common_ids = (from_ids & to_ids) - renumbered_from_ids - renumbered_to_ids
    changed_legal_refs = tuple(
        sorted(cid for cid in common_ids if _casilla_legal_refs_changed(from_by_id[cid], to_by_id[cid])),
    )

    return added, removed, tuple(renumbered), changed_legal_refs


def _diff_formulas(
    from_revision: _ModeloRevision,
    to_revision: _ModeloRevision,
) -> tuple[tuple[_FormulaId, ...], tuple[_FormulaId, ...], tuple[FormulaDiff, ...]]:
    from_by_id = {formula.id: formula for formula in from_revision.formulas}
    to_by_id = {formula.id: formula for formula in to_revision.formulas}
    from_ids = set(from_by_id)
    to_ids = set(to_by_id)

    added = tuple(sorted(to_ids - from_ids))
    removed = tuple(sorted(from_ids - to_ids))

    changed: list[FormulaDiff] = []
    for formula_id in sorted(from_ids & to_ids):
        from_formula = from_by_id[formula_id]
        to_formula = to_by_id[formula_id]
        from_expression = from_formula.expression.model_dump(mode="json")
        to_expression = to_formula.expression.model_dump(mode="json")
        legal_refs_changed = set(from_formula.legal_refs) != set(to_formula.legal_refs)
        if from_expression == to_expression and not legal_refs_changed and from_formula.rounding == to_formula.rounding:
            continue
        changed.append(
            FormulaDiff(
                id=formula_id,
                target_casilla_id=to_formula.target_casilla_id,
                from_expression=from_expression,
                to_expression=to_expression,
                from_legal_refs=from_formula.legal_refs,
                to_legal_refs=to_formula.legal_refs,
            ),
        )
    return added, removed, tuple(changed)


def _diff_parameters(
    from_revision: _ModeloRevision,
    to_revision: _ModeloRevision,
) -> tuple[tuple[_ParameterId, ...], tuple[_ParameterId, ...], tuple[ParameterDiff, ...]]:
    from_by_id = {parameter.id: parameter for parameter in from_revision.parameters}
    to_by_id = {parameter.id: parameter for parameter in to_revision.parameters}
    from_ids = set(from_by_id)
    to_ids = set(to_by_id)

    added = tuple(sorted(to_ids - from_ids))
    removed = tuple(sorted(from_ids - to_ids))

    changed: list[ParameterDiff] = []
    for parameter_id in sorted(from_ids & to_ids):
        from_parameter = from_by_id[parameter_id]
        to_parameter = to_by_id[parameter_id]
        same_values = (
            from_parameter.data_type == to_parameter.data_type
            and from_parameter.values == to_parameter.values
            and from_parameter.brackets == to_parameter.brackets
            and from_parameter.keyed_brackets == to_parameter.keyed_brackets
        )
        legal_refs_changed = set(from_parameter.legal_refs) != set(to_parameter.legal_refs)
        if same_values and not legal_refs_changed:
            continue
        changed.append(
            ParameterDiff(
                id=parameter_id,
                data_type=to_parameter.data_type,
                from_legal_refs=from_parameter.legal_refs,
                to_legal_refs=to_parameter.legal_refs,
            ),
        )
    return added, removed, tuple(changed)


def _diff_bindings(
    from_revision: _ModeloRevision,
    to_revision: _ModeloRevision,
) -> tuple[tuple[BindingDiff, ...], tuple[BindingDiff, ...]]:
    from_by_id = {binding.id: binding for binding in from_revision.bindings}
    to_by_id = {binding.id: binding for binding in to_revision.bindings}
    from_ids = set(from_by_id)
    to_ids = set(to_by_id)

    added = tuple(_binding_diff_projection(to_by_id[bid]) for bid in sorted(to_ids - from_ids))
    removed = tuple(_binding_diff_projection(from_by_id[bid]) for bid in sorted(from_ids - to_ids))
    return added, removed


def diff_registry_revisions(
    modelo: str,
    *,
    from_year: int,
    to_year: int,
    registry_root: Path | None = None,
    source_root: Path | None = None,
    as_of: date | None = None,
) -> RegistryRevisionDiffReport:
    """Diff the two registry revisions covering ``from_year`` and ``to_year``.

    Each bare filing year resolves through the canonical temporal selector.
    When ``as_of`` is supplied, both revisions must also be valid on that date.
    A year with no covering revision is adapted to the diff command's
    actionable error, while an ambiguous selection retains the domain's typed
    candidate error.

    Returns:
        A :class:`~application.registry.RegistryRevisionDiffReport` enumerating casilla adds,
        removes, and continuidad-tracked renumbers; formula, parameter, and
        binding adds/removes/changes; and revision-level ``legal_refs``
        deltas. Diffing a modelo against itself for two years that resolve to
        the same revision id returns an all-empty report with
        ``same_revision=True``.
    """
    authority = _ValidatedRegistryAuthority.load(
        registry_root or _bundled_path("registry", "aeat"),
        source_root=source_root or _bundled_path(),
    )
    definition = authority.validate_modelo(modelo.strip())
    from_revision = _revision_for_year(definition, filing_year=from_year, on=as_of)
    to_revision = _revision_for_year(definition, filing_year=to_year, on=as_of)

    if from_revision.id == to_revision.id:
        return RegistryRevisionDiffReport(
            modelo=str(definition.id),
            from_year=from_year,
            to_year=to_year,
            from_revision_id=from_revision.id,
            to_revision_id=to_revision.id,
            same_revision=True,
            added_casillas=(),
            removed_casillas=(),
            renumbered_casillas=(),
            changed_casilla_legal_refs=(),
            added_formulas=(),
            removed_formulas=(),
            changed_formulas=(),
            added_parameters=(),
            removed_parameters=(),
            changed_parameters=(),
            added_bindings=(),
            removed_bindings=(),
            revision_legal_refs_added=(),
            revision_legal_refs_removed=(),
        )

    added_casillas, removed_casillas, renumbered_casillas, changed_casilla_legal_refs = _diff_casillas(
        from_revision.casillas,
        to_revision.casillas,
    )
    added_formulas, removed_formulas, changed_formulas = _diff_formulas(from_revision, to_revision)
    added_parameters, removed_parameters, changed_parameters = _diff_parameters(from_revision, to_revision)
    added_bindings, removed_bindings = _diff_bindings(from_revision, to_revision)

    from_revision_legal_refs = set(from_revision.legal_refs)
    to_revision_legal_refs = set(to_revision.legal_refs)

    return RegistryRevisionDiffReport(
        modelo=str(definition.id),
        from_year=from_year,
        to_year=to_year,
        from_revision_id=from_revision.id,
        to_revision_id=to_revision.id,
        same_revision=False,
        added_casillas=added_casillas,
        removed_casillas=removed_casillas,
        renumbered_casillas=renumbered_casillas,
        changed_casilla_legal_refs=changed_casilla_legal_refs,
        added_formulas=added_formulas,
        removed_formulas=removed_formulas,
        changed_formulas=changed_formulas,
        added_parameters=added_parameters,
        removed_parameters=removed_parameters,
        changed_parameters=changed_parameters,
        added_bindings=added_bindings,
        removed_bindings=removed_bindings,
        revision_legal_refs_added=tuple(sorted(to_revision_legal_refs - from_revision_legal_refs)),
        revision_legal_refs_removed=tuple(sorted(from_revision_legal_refs - to_revision_legal_refs)),
    )
