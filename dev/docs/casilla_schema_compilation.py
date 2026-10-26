"""Compile exact-revision casilla derivation and modelo overview facts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from cadrumo.core.external_constants import OutputLanguage
from dev.registry.compiler.authority import compiled_bundled_authority

from .casilla_reference_models import CasillaFacts, CompiledSchema, ModeloOverview
from .compile_slots import active, language_text
from .terminology.search_record import CasillaSearchRecord

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
    from cadrumo.domain.calculations.registry.schema import FormulaDefinition, ModeloDefinition, ModeloRevision
    from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition


# ── Schema compilation ───────────────────────────────────────────────────────


def compile_schema(
    records: tuple[CasillaSearchRecord, ...],
    language: OutputLanguage,
    authority: ValidatedRegistryAuthority | None = None,
) -> CompiledSchema:
    """Compile the fill/derivation facts and modelo overviews the pages render.

    Each record is resolved back to the exact revision it was projected from
    (``source_revisions[0]``, latest first), so this reads the SAME casilla
    definition the search card describes rather than re-deriving which revision
    applies - one selection authority, not two.

    Args:
        records: The projected casilla records the pages will render.
        language: The build language; the Handbook definition and the modelo
            title/official name are read in this language only.
        authority: Validated registry authority; defaults to the bundled one.

    Returns:
        A :class:`CompiledSchema`. A record whose modelo, revision or casilla
        does not resolve is simply absent from the map, and its entry renders
        from the record alone.
    """

    resolved = authority if authority is not None else compiled_bundled_authority()
    modelos = {modelo.id: modelo for modelo in resolved.modelos}

    facts: dict[tuple[str, str], CasillaFacts] = {}
    revision_cache: dict[
        tuple[str, str],
        tuple[Mapping[str, CasillaDefinition], Mapping[str, FormulaDefinition], Mapping[str, str]],
    ] = {}

    for record in records:
        _compile_schema_record(record, modelos, revision_cache, facts)

    return CompiledSchema(
        casillas=facts,
        modelos=_compile_modelo_overviews({record.modelo.value for record in records}, language, modelos),
    )


def _compile_modelo_overviews(
    modelo_ids: set[str],
    language: OutputLanguage,
    modelos: Mapping[str, ModeloDefinition],
) -> dict[str, ModeloOverview]:
    """Compile each modelo's identity, cadence, grounding and curated definition.

    The identity is authored in every language, so under the one compile the
    title and the official name are marks reading each language's own, and the
    curated definitions are carried per language for the page to make its own
    paragraph out of (:class:`~dev.docs.casilla_reference_models.ModeloOverview`).
    """
    slots = active()
    carried = slots.languages if slots is not None else (language.value,)
    definitions = {tag: _handbook_definitions(OutputLanguage(tag)) for tag in carried}
    overviews: dict[str, ModeloOverview] = {}
    for modelo_id in sorted(modelo_ids):
        modelo = modelos.get(modelo_id)
        if modelo is None:
            continue
        overviews[modelo_id] = ModeloOverview(
            title=language_text(modelo.get_title, language.value),
            source_title=modelo.get_title(OutputLanguage.EN.value),
            official_name=language_text(modelo.get_official_name, language.value),
            definitions={tag: authored[modelo_id] for tag, authored in definitions.items() if modelo_id in authored},
            tax_domain=str(modelo.tax_domain),
            cadence=str(modelo.cadence),
            legal_refs=tuple(str(ref) for ref in modelo.legal_refs),
        )
    return overviews


def _handbook_definitions(language: OutputLanguage) -> dict[str, str]:
    """``modelo id -> curated definition`` for approved concepts, in ONE language.

    Only an ``approved`` concept that authored a definition in the build language
    contributes; a draft concept, or one translated into other locales but not
    this one, contributes nothing rather than a substituted string.
    """
    from cadrumo.core.concept_lifecycle import ConceptLifecycle

    from .terminology_handbook.loader import load_terminology_handbook

    definitions: dict[str, str] = {}
    for concept in load_terminology_handbook().concepts:
        if concept.lifecycle is not ConceptLifecycle.APPROVED:
            continue
        modelo_id = concept.concept_id.removeprefix("modelo-")
        if modelo_id == concept.concept_id:
            continue
        for section in concept.languages:
            if section.language is not language:
                continue
            text = (section.definition or "").strip()
            if text:
                definitions[modelo_id] = text
    return definitions


type _RevisionContent = tuple[Mapping[str, CasillaDefinition], Mapping[str, FormulaDefinition], Mapping[str, str]]


def _compile_schema_record(
    record: CasillaSearchRecord,
    modelos: Mapping[str, ModeloDefinition],
    revision_cache: dict[tuple[str, str], _RevisionContent],
    facts: dict[tuple[str, str], CasillaFacts],
) -> None:
    modelo = modelos.get(record.modelo.value)
    if modelo is None or not record.source_revisions:
        return
    revision = modelo.revisions.get(record.source_revisions[0])
    if revision is None:
        return

    key = (record.modelo.value, record.source_revisions[0])
    cached = _revision_facts(revision, key, revision_cache)
    casillas_by_id, formulas_by_target, binding_sources = cached

    casilla = casillas_by_id.get(record.casilla_id)
    if casilla is None:
        return

    facts[(record.modelo.value, str(record.casilla_id))] = _casilla_facts(casilla, formulas_by_target, binding_sources)


def _revision_facts(
    revision: ModeloRevision, key: tuple[str, str], revision_cache: dict[tuple[str, str], _RevisionContent]
) -> _RevisionContent:
    cached = revision_cache.get(key)
    if cached is None:
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
        formulas: dict[str, FormulaDefinition] = {}
        for formula in revision.formulas:
            formulas[str(formula.target_casilla_id)] = formula
        sources = {str(binding.id): str(binding.source) for binding in revision.bindings}
        cached = (casillas_by_id, formulas, sources)
        revision_cache[key] = cached
    return cached


def _casilla_facts(
    casilla: CasillaDefinition, formulas_by_target: Mapping[str, FormulaDefinition], binding_sources: Mapping[str, str]
) -> CasillaFacts:
    from cadrumo.domain.calculations.registry.binding_targets import bound_casilla_binding_ids
    from cadrumo.domain.calculations.registry.runtime_graph import expression_casilla_refs

    formula = formulas_by_target.get(str(casilla.id))
    formula_inputs = (
        () if formula is None else tuple(dict.fromkeys(str(ref) for ref in expression_casilla_refs(formula.expression)))
    )
    binding_ids = bound_casilla_binding_ids(casilla)
    return CasillaFacts(
        binding_sources=tuple(
            dict.fromkeys(
                source
                for source in (binding_sources.get(str(binding_id)) for binding_id in binding_ids)
                if source is not None
            ),
        ),
        formula_inputs=formula_inputs,
        constraints=casilla.constraints,
        form_number=casilla.form_number if casilla.form_number != casilla.number else None,
        internal_only=casilla.internal_only,
    )
