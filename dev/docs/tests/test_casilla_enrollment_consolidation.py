"""Real-authority gates for deterministic casilla enrollment.

These focused gates close the worked example that the broader projection and
anchor suites cannot name: M130/casilla 15 must exist in the validated registry
projection, carry its registry definition through the unified search record,
resolve from the individual source section, and land on the same generated
reference anchor the renderer emits.

No search vocabulary is invented here. The registry is the authority for the
casilla fields; the shared projection and target funnel are the product paths
under test; and the committed relevance mapping is used only for the census's
separate sparse-relevance axis.
"""

from __future__ import annotations

import pytest

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry import ValidatedRegistryAuthority
from dev._paths import REPO_ROOT

from ..casilla_reference import CasillaReferenceResult, render_casilla_reference
from ..terminology._casilla_anchor import casilla_page_anchor, casilla_reference_target
from ..terminology._casilla_projection import CasillaProjectionStats, project_casilla_search_records
from ..terminology._coverage import CasillaCoverageKind, compute_casilla_coverage_census
from ..terminology._resolution import ChunkHit, GroundingSurface, ResolvedTarget, TargetResolver
from ..terminology._search_record import CasillaSearchRecord
from ..terminology._unified_record import to_search_record

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT
_M130_CASILLA_15_SOURCE = (
    "src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/"
    "casillas/c01__csaldo-negativo-fin-periodo.toml"
)


from ._authority_fixtures import authority

__all__ = ["authority"]


@pytest.fixture(scope="module")
def projected(
    authority: ValidatedRegistryAuthority,
) -> tuple[tuple[CasillaSearchRecord, ...], CasillaProjectionStats]:
    """Project the full registry once through the production compiler."""
    return project_casilla_search_records(authority)


@pytest.fixture(scope="module")
def m130_casilla_15(
    authority: ValidatedRegistryAuthority,
    projected: tuple[tuple[CasillaSearchRecord, ...], CasillaProjectionStats],
) -> CasillaSearchRecord:
    """Return the canonical deduplicated M130/casilla-15 projection."""
    definition = authority.modelo("130")
    latest_revision = max(definition.revisions.values(), key=lambda revision: revision.valid_from)
    source_casilla = next(casilla for casilla in latest_revision.casillas if casilla.id == "15")
    records, _stats = projected
    record = next(
        (
            candidate
            for candidate in records
            if candidate.modelo.value == "130" and candidate.casilla_id == source_casilla.id
        ),
        None,
    )
    assert record is not None, "registry M130/casilla 15 is absent from the canonical projection"
    assert record.number == source_casilla.number
    assert record.descriptions[OutputLanguage.ES] == source_casilla.label
    assert record.data_type == source_casilla.data_type
    assert record.required is source_casilla.required
    assert record.formula_id == source_casilla.formula
    for locale, language in (
        ("en", OutputLanguage.EN),
        ("ca", OutputLanguage.CA),
        ("hu", OutputLanguage.HU),
    ):
        assert record.descriptions[language] == source_casilla.get_label(locale)
        assert record.localized_help[locale] == source_casilla.get_help(locale)
    return record


@pytest.fixture(scope="module")
def reference(
    projected: tuple[tuple[CasillaSearchRecord, ...], CasillaProjectionStats],
) -> CasillaReferenceResult:
    """Render the reference surface from the same full projection."""
    records, _stats = projected
    return render_casilla_reference(_REPO_ROOT, records=records)


def test_m130_casilla_15_is_enrolled_across_deterministic_census_surfaces(
    authority: ValidatedRegistryAuthority,
    projected: tuple[tuple[CasillaSearchRecord, ...], CasillaProjectionStats],
    m130_casilla_15: CasillaSearchRecord,
) -> None:
    """The worked casilla is projected, targetable, defined, and localised."""
    records, stats = projected
    census = compute_casilla_coverage_census(casilla_records=records, authority=authority)
    search_record = to_search_record(m130_casilla_15)

    assert stats.deduplicated_records == len(records)
    assert search_record.id not in census.surface(CasillaCoverageKind.PROJECTED).uncovered_ids
    assert search_record.id not in census.surface(CasillaCoverageKind.EXACT_TARGET).uncovered_ids
    assert search_record.id not in census.surface(CasillaCoverageKind.DEFINITION).uncovered_ids
    assert search_record.id not in census.surface(CasillaCoverageKind.LOCALE).uncovered_ids

    totals = {surface.total for surface in census.surfaces}
    assert totals == {len(records)}, "census surfaces must share the projected denominator"
    for surface in census.surfaces:
        assert surface.covered + len(surface.uncovered_ids) == len(records), surface.surface


def test_m130_casilla_15_rag_section_resolves_to_one_canonical_target(
    authority: ValidatedRegistryAuthority,
    m130_casilla_15: CasillaSearchRecord,
) -> None:
    """The real registry section locator resolves the named casilla only."""
    resolver = TargetResolver(authority)
    result = resolver.resolve(
        ChunkHit(
            path=_M130_CASILLA_15_SOURCE,
            line_start=207,
            line_end=219,
            score=0.97,
        )
    )

    assert isinstance(result, ResolvedTarget)
    assert result.surface is GroundingSurface.CASILLA
    assert result.record.metadata.modelo == "130"
    assert result.record.metadata.casilla_id == "15"
    assert result.record.id == to_search_record(m130_casilla_15).id
    assert result.record.target == casilla_reference_target("130", "15")


def test_m130_casilla_15_definition_and_target_match_reference(
    m130_casilla_15: CasillaSearchRecord,
    reference: CasillaReferenceResult,
) -> None:
    """The generated entry contains the registry definition and shared anchor."""
    page = next(page for page in reference.pages if page.modelo == "130")
    anchor = casilla_page_anchor("130", "15")
    unified = to_search_record(m130_casilla_15)

    assert anchor in page.anchors
    assert page.output_relpath.replace(".rst", ".html") + f"#{anchor}" == unified.target
    assert m130_casilla_15.descriptions[OutputLanguage.ES] in page.rst
    assert f":Data type: ``{m130_casilla_15.data_type}``" in page.rst
    assert f":Input kind: ``{m130_casilla_15.input_kind.value}``" in page.rst
    assert f":Required: {'yes' if m130_casilla_15.required else 'no'}" in page.rst
    if m130_casilla_15.formula_id is not None:
        assert f":Formula id: ``{m130_casilla_15.formula_id}``" in page.rst

    for language in (OutputLanguage.EN, OutputLanguage.CA, OutputLanguage.HU):
        label = m130_casilla_15.descriptions.get(language)
        help_text = m130_casilla_15.localized_help.get(language.value)
        assert label and label.strip(), f"M130/casilla 15 has no {language.value} label"
        assert help_text and help_text.strip(), f"M130/casilla 15 has no {language.value} help"
        assert label in page.rst
        assert help_text in page.rst
