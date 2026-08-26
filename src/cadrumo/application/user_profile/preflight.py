"""Preflight service: which schema fields a given modelo/revision needs.

:class:`ProfilePreflightService` inspects the schema's ``model_selectors``
against a :class:`UserProfileRecord` and returns a
:class:`ProfilePreflightReport` listing every required field that the
record does not yet carry.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from ...core import Modelo, Period
from ...domain.calculations.registry.authority import ValidatedRegistryAuthority
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.profile_grounding import (
    ProfileKeyGrounding,
    build_profile_grounding_index,
)
from ...domain.user_profile.errors import UserProfileNotFoundError
from ...domain.user_profile.labels import profile_field_label
from ...domain.user_profile.schema import ProfileSchemaDefinition
from ...domain.user_profile.values import UserProfileRecord, section_field_key
from .commands import (
    ProfilePreflightReport,
    ProfilePreflightRequirement,
)
from .completeness import conditional_profile_missing_required
from .projections import record_to_path_values

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema import ModeloRevision


def build_profile_preflight_requirement(
    path: str,
    *,
    schema: ProfileSchemaDefinition,
    selector: str | None = None,
    grounding_index: Mapping[str, ProfileKeyGrounding] | None = None,
) -> ProfilePreflightRequirement:
    """Build one requirement row for a profile path, enriched with a label and grounding.

    The shared builder behind every ``ProfilePreflightRequirement`` this
    package or :mod:`application.modelo`'s profile readiness gate
    constructs - the schema-required walk in :meth:`ProfilePreflightService.report`,
    its export-identity and conditional-requirement branches, and the
    modelo-work baseline/validation checks in ``_profile_readiness_gate.py``
    all route through this one function rather than maintaining parallel
    implementations.

    ``path`` is reduced to its declared ``section.field`` form via
    :func:`~domain.user_profile.values.section_field_key` before lookup, so a
    repeatable-row path (``activities.0.iae_epigraph``) and a bare
    non-dotted validation code both resolve correctly. The label is the
    locale-catalogue operator label (falling back to the field's declared
    ``description``, never a raw dotted path) when the reduced path names a
    real schema field; otherwise it falls back to ``selector`` or ``path``
    itself. The schema-declared ``legal_refs`` come from the field
    definition; the registry-binding-derived ``legal_refs`` and ``modelos``
    come from ``grounding_index`` when the reduced path is a known
    ``source = "profile"`` binding key. A path absent from either source
    contributes nothing to that source - never a fabricated value.
    ``modelos`` is always the grounded registry union, never the modelo the
    caller happens to be checking - the two are different facts and must
    not be conflated under one field.
    """
    reduced = section_field_key(path) if "." in path else path
    section_key, _, field_key = reduced.partition(".")
    if not field_key:
        section_key, field_key = "profile", section_key
    label = selector or path
    legal_refs: tuple[str, ...] = ()
    if "." in reduced:
        try:
            field = schema.field(reduced)
        except UserProfileNotFoundError:
            pass
        else:
            label = profile_field_label(section_key, field)
            legal_refs = field.legal_refs
    grounding = (grounding_index or {}).get(reduced)
    if grounding:
        legal_refs = tuple(sorted({*legal_refs, *grounding.legal_refs}))
    modelos = tuple(sorted({m.value for m in grounding.modelos})) if grounding else ()
    return ProfilePreflightRequirement(
        selector=selector or path,
        section_key=section_key,
        field_key=field_key,
        label=label,
        legal_refs=legal_refs,
        modelos=modelos,
    )


def format_profile_preflight_requirement(requirement: ProfilePreflightRequirement) -> str:
    """Render one requirement row as ``label (legal_ref, legal_ref)``.

    The single operator-facing rendering of a missing profile requirement,
    shared by every surface that names one: the modelo work readiness gate's
    refusal, the overview calendar/agenda/backlog refusals, and the data
    inventory checklist's unresolved-coefficient warning.

    Falls back to the bare label when the field carries no legal grounding -
    never a raw dotted path once a label is available, and never an invented
    citation when none is declared.
    """
    if requirement.legal_refs:
        return f"{requirement.label} ({', '.join(requirement.legal_refs)})"
    return requirement.label


def format_profile_selector_requirements(
    selectors: Iterable[str],
    *,
    schema: ProfileSchemaDefinition,
    grounding_index: Mapping[str, ProfileKeyGrounding] | None = None,
) -> tuple[str, ...]:
    """Render declared selector tokens as grounded requirement text, in order.

    Bridges the surfaces that hold a ``model_selectors`` TOKEN - a
    deadline-engine gating key, a registry binding's consumed profile key -
    rather than a ``section.field`` path, which is what
    :func:`build_profile_preflight_requirement` resolves.

    A token the schema resolves to exactly one field is rendered as that
    field's operator label with its legal grounding. A token the schema does
    not resolve - because it names no field, because two fields declare it, or
    because it belongs to another namespace entirely, such as a warning code
    that is not a profile field at all - is passed through unchanged. Callers
    mix both kinds in one stream, and a token rendered verbatim is the
    behaviour that surface already has, whereas a guessed label would be
    confidently wrong.
    """
    rendered: list[str] = []
    for selector in selectors:
        path = schema.path_for_model_selector(selector)
        if path is None:
            rendered.append(selector)
            continue
        rendered.append(
            format_profile_preflight_requirement(
                build_profile_preflight_requirement(
                    path,
                    schema=schema,
                    selector=selector,
                    grounding_index=grounding_index,
                ),
            ),
        )
    return tuple(rendered)


def format_profile_path_requirements(
    paths: Iterable[str],
    *,
    schema: ProfileSchemaDefinition,
    grounding_index: Mapping[str, ProfileKeyGrounding] | None = None,
) -> tuple[str, ...]:
    """Render profile PATHS as grounded requirement text, in order.

    The path-shaped sibling of :func:`format_profile_selector_requirements`.
    The distinction is not cosmetic and the two are not interchangeable: a
    registry binding names the profile fact it consumes by its
    ``section.field`` PATH, whereas the deadline engine's completeness gate
    names its fields by their declared ``model_selectors`` TOKEN. Routing
    binding keys through the selector lookup resolves nothing, so every key
    passes through unchanged and the rendering is silently a no-op.

    :func:`build_profile_preflight_requirement` already reduces a path to its
    declared form, so a row-indexed path resolves here too. A path naming no
    schema field - a derived-selector pattern expanded for a filing year, for
    instance - keeps its own text, since there is no label to show for it.
    """
    return tuple(
        format_profile_preflight_requirement(
            build_profile_preflight_requirement(
                path,
                schema=schema,
                grounding_index=grounding_index,
            ),
        )
        for path in paths
    )


class ProfilePreflightService:
    """Resolve required profile selectors for a given ``(modelo, revision, year, period)``.

    The service inspects the loaded schema's ``model_selectors`` and
    ``schedule_predicates`` declarations. Today every required field whose
    ``model_selectors`` reference the target modelo is considered required;
    revision-specific filtering will land alongside the registry-time
    selector inventory work.
    """

    def __init__(self, *, schema: ProfileSchemaDefinition) -> None:
        self._schema = schema

    def report(
        self,
        *,
        record: UserProfileRecord,
        modelo: str,
        revision_id: RevisionId,
        period: Period,
        revision: ModeloRevision | None = None,
        authority: ValidatedRegistryAuthority | None = None,
    ) -> ProfilePreflightReport:
        """Compute missing required profile fields for the given filing context.

        Walks every section and field in the schema.  A field is considered
        required for this filing when ``field.required`` is true and at
        least one of its ``model_selectors`` has the prefix
        ``modelo_<modelo>``.  Facts already present on ``record`` are
        excluded from the missing list.

        Args:
            record: The caller's current :class:`UserProfileRecord`.
            modelo: Numeric modelo identifier (e.g. ``"303"``).
            revision_id: Revision tag from the registry (e.g. ``"2024-0A"``).
            period: Typed filing period.
            revision: Optional :class:`ModeloRevision` whose export layouts
                contribute filing-grade declarant identity requirements.
            authority: Optional :class:`ValidatedRegistryAuthority` used to
                union each missing field's grounding with every consuming
                ``source = "profile"`` registry binding's ``legal_refs`` and
                modelos, via :func:`build_profile_grounding_index`. When
                omitted, grounding falls back to the schema field's own
                ``legal_refs`` only - nothing is invented.

        Returns:
            A :class:`ProfilePreflightReport` with ``ready=True`` when all
            required fields are present, or ``ready=False`` with the
            ``missing`` list populated.

            ``per_operation_requirements_assessed`` reports whether the
            per-modelo walk described above selected any field at all. The
            shipped schema declares grounded ``modelo_`` selectors only for
            Modelo 036, 100 and 303, and among those only ``identity.tax_id``
            (Modelo 100) is also schema-``required`` - every other tokenised
            field is optional, so it is never selected by this walk. The flag
            is therefore true for Modelo 100 and false for every other modelo,
            including 036 and 303, where ``ready`` reflects only the
            export-identity and conditional checks. A false value means
            nothing schema-required was examined for that modelo; it MUST NOT
            be rendered as a clean bill of health.
        """
        values = record_to_path_values(record)
        grounding_index: Mapping[str, ProfileKeyGrounding] = (
            build_profile_grounding_index(authority) if authority is not None else {}
        )
        missing: list[ProfilePreflightRequirement] = []
        target = self._selector_prefix(modelo)
        # Counts fields the per-operation axis SELECTED, not fields found missing.
        # A modelo whose selected fields are all present is assessed and ready; a
        # modelo that selected nothing was never assessed at all, and the two must
        # not both surface as ``ready=True`` with an empty ``missing``.
        per_operation_selected = 0
        for section in self._schema.sections:
            for field in section.fields:
                if not field.required:
                    continue
                if not self._selectors_match_modelo(field.model_selectors, target):
                    continue
                per_operation_selected += 1
                candidate_path = f"{section.key}.{field.key}"
                if self._has_value(values, candidate_path):
                    continue
                missing.append(
                    build_profile_preflight_requirement(
                        candidate_path,
                        schema=self._schema,
                        selector=field.model_selectors[0] if field.model_selectors else candidate_path,
                        grounding_index=grounding_index,
                    ),
                )
        if modelo.strip() == Modelo.M111.value:
            colegio_path = "withholding.colegio_concertado"
            per_operation_selected += 1
            if not self._has_value(values, colegio_path):
                missing.append(
                    build_profile_preflight_requirement(
                        colegio_path,
                        schema=self._schema,
                        selector="colegio_concertado",
                        grounding_index=grounding_index,
                    ),
                )
        missing.extend(self._missing_conditional_profile_requirements(values, missing, grounding_index))
        return ProfilePreflightReport(
            profile_id=record.profile_id,
            modelo=modelo,
            revision_id=revision_id,
            filing_year=period.filing_year,
            period=period,
            missing=tuple(missing),
            ready=not missing,
            per_operation_requirements_assessed=per_operation_selected > 0,
        )

    @staticmethod
    def _selector_prefix(modelo: str) -> str:
        return f"modelo_{modelo.strip()}"

    @staticmethod
    def _selectors_match_modelo(selectors: tuple[str, ...], target_prefix: str) -> bool:
        if not selectors:
            return False
        return any(selector.startswith(target_prefix) for selector in selectors)

    @staticmethod
    def _has_value(values: dict[str, str], path: str) -> bool:
        return bool((values.get(path) or "").strip())

    def _missing_conditional_profile_requirements(
        self,
        values: dict[str, str],
        existing: list[ProfilePreflightRequirement],
        grounding_index: Mapping[str, ProfileKeyGrounding],
    ) -> list[ProfilePreflightRequirement]:
        already_missing = {(item.section_key, item.field_key) for item in existing}
        missing: list[ProfilePreflightRequirement] = []
        for path in conditional_profile_missing_required(values):
            section_key, field_key = self._split_path(path)
            if (section_key, field_key) in already_missing:
                continue
            missing.append(
                build_profile_preflight_requirement(
                    f"{section_key}.{field_key}",
                    schema=self._schema,
                    selector=self._selector_for_path(path),
                    grounding_index=grounding_index,
                ),
            )
        return missing

    def _selector_for_path(self, path: str) -> str:
        section_key, field_key = self._split_path(path)
        for section in self._schema.sections:
            if section.key != section_key:
                continue
            for field in section.fields:
                if field.key == field_key:
                    return field.model_selectors[0] if field.model_selectors else path
        return path

    @staticmethod
    def _split_path(path: str) -> tuple[str, str]:
        section_key, _, field_key = section_field_key(path).partition(".")
        return section_key, field_key


__all__ = [
    "ProfilePreflightService",
    "build_profile_preflight_requirement",
    "format_profile_path_requirements",
    "format_profile_preflight_requirement",
    "format_profile_selector_requirements",
]
