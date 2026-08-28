"""Structure and wiring tests for the per-revision conformance profile composer.

Grounded in the *real* bundled registry tree throughout: every fixture is the
shipped tree or a ``model_copy`` of a record read out of it, so no test double
stands between an assertion and the fact it claims to check.

What these tests deliberately do NOT assert is today's census. Pinning "90 rows
across 73 modelos" would turn every legitimate registry edit — a new modelo, a
new revision, a stamped review — into a red gate, and a gate that reds on
correct work gets weakened until it reds on nothing. The census is asserted as a
RELATION against the tree the composer read (one row per revision the tree
actually declares), plus an anti-vacuity floor far below the current tree that
an empty or collapsed compose cannot clear.

Every behavioural claim about a per-row value is proved by mutation: a composed
input is changed so a named row's value MUST change, and both the before and the
after are asserted. A composer that hardcoded the value, or that never read the
mutated field, fails the second assertion rather than merely being reached.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core import NON_REGISTRY_MODELOS, ExportLayoutFormat, Modelo, RevisionReviewStatus
from ....core.access_gate import AuthorizationState
from ....domain.calculations.registry.authority import ValidatedRegistryAuthority
from ....domain.calculations.registry.classification_coherence import build_classification_coherence_audit
from ....domain.calculations.registry.export_parse import xml_dictionary_entries
from ....domain.calculations.registry.external_grounding import (
    RegistryExternalGroundingAudit,
    build_external_grounding_audit,
    load_bundled_external_oracle_inventory,
)
from ....domain.calculations.registry.schema import ModeloDefinition
from ....tests.registry_tree import bundled_registry_tree
from ..conformance import (
    AnnualCasillaPopulationComparison,
    RegistryConformanceProfile,
    build_registry_conformance_profile,
    compare_annual_casilla_population,
    compare_annual_casilla_population_for_revision,
)
from ..errors import RegistryApplicationInputError
from ._conformance_profile_fixtures import degraded_profile, validated_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Anti-vacuity floors. Well below the tree's real size (73 modelos / 90
#: revisions at the time of writing) so ordinary registry growth or a modelo
#: retirement never reds these, while an empty tree, a collapsed fold, or a
#: composer that silently dropped most rows cannot clear them.
_MINIMUM_COMPOSED_MODELOS = 50
_MINIMUM_COMPOSED_REVISIONS = 60

#: Two real modelos used for the injected cases: 303 declares external grounding
#: on its current revision, and both carry more than one revision, which is what
#: makes the latest-revision scope question observable at all.
_GROUNDED_MODELO = "303"
_MULTI_REVISION_MODELO = "100"

# Independent census captured from the bundled year-specific AEAT dictionaries.
# This anchor is a fact about the AEAT ARTEFACT, so it is pinned as a number: a
# change here means the bundled corpus moved and is worth failing on.
#
# The registry-side counterpart used to be pinned the same way and was deleted.
# It is a tally over declarations this project AUTHORS, so it drifted every time
# a casilla was legitimately added, trained everyone to re-baseline it, and
# detected nothing in between. What it was standing in for is asserted below as
# a property instead.
_M100_DICTIONARY_CASILLA_COUNTS = {
    2020: 1531,
    2021: 1693,
    2022: 1852,
    2023: 1929,
    2024: 2072,
    2025: 2215,
}


@pytest.fixture(scope="module")
def tree_modelos() -> tuple[ModeloDefinition, ...]:
    """Every compiled modelo in the bundled tree, read without validation."""
    modelos, _catalogues = bundled_registry_tree()
    return modelos


def _compose(
    modelos: tuple[ModeloDefinition, ...],
    *,
    scope_diagnostics: tuple[str, ...] = (),
    external_grounding: RegistryExternalGroundingAudit | None = None,
) -> RegistryConformanceProfile:
    """Compose a degraded profile over ``modelos`` using the real folds.

    The default grounding audit is the real fold over the same modelos; a caller
    testing a grounding-dependent value passes a mutated one instead.
    """
    grounding = external_grounding or build_external_grounding_audit(
        modelos,
        inventory=load_bundled_external_oracle_inventory(),
        registry_validated=False,
    )
    classification = build_classification_coherence_audit(
        modelos,
        non_registry_modelo_codes=frozenset(item.value for item in NON_REGISTRY_MODELOS),
        known_modelo_codes=frozenset(item.value for item in Modelo),
        registry_validated=False,
    )
    return build_registry_conformance_profile(
        modelos,
        external_grounding=grounding,
        classification=classification,
        scope_diagnostics=scope_diagnostics,
        registry_validated=False,
    )


def _modelo(modelos: tuple[ModeloDefinition, ...], modelo_id: str) -> ModeloDefinition:
    for modelo in modelos:
        if modelo.id == modelo_id:
            return modelo
    raise AssertionError(f"the bundled registry no longer declares modelo {modelo_id!r}")


def test_composes_exactly_one_row_per_revision_the_tree_declares(
    tree_modelos: tuple[ModeloDefinition, ...],
    degraded_profile: RegistryConformanceProfile,
) -> None:
    """Row coverage is a relation against the tree, never a pinned count."""
    declared = {(modelo.id, revision_id) for modelo in tree_modelos for revision_id in modelo.revisions}
    composed = [(row.modelo, row.revision) for row in degraded_profile.rows]

    assert set(composed) == declared
    assert len(composed) == len(declared), "a revision was composed twice"


def test_composed_census_clears_the_vacuity_floor(degraded_profile: RegistryConformanceProfile) -> None:
    """An empty or collapsed compose must not be able to read as a pass."""
    assert degraded_profile.composed_revision_count >= _MINIMUM_COMPOSED_REVISIONS
    assert degraded_profile.composed_modelo_count >= _MINIMUM_COMPOSED_MODELOS
    assert all(row.modelo and row.revision for row in degraded_profile.rows)


def test_every_row_carries_a_declared_governance_stamp(degraded_profile: RegistryConformanceProfile) -> None:
    """Provenance is present on every row, and its reviewer pairing is coherent."""
    for row in degraded_profile.rows:
        stamp = row.governance
        assert isinstance(stamp.review_status, RevisionReviewStatus)
        if stamp.is_reviewed:
            assert stamp.reviewed_by is not None
            assert stamp.reviewed_at is not None
        else:
            assert stamp.reviewed_by is None
            assert stamp.reviewed_at is None


def test_review_status_census_names_every_status_including_unused_ones(
    degraded_profile: RegistryConformanceProfile,
) -> None:
    """A status no revision holds must report a real zero, not an absent key."""
    census = degraded_profile.review_status_census()

    assert set(census) == set(RevisionReviewStatus)
    assert sum(census.values()) == degraded_profile.composed_revision_count


def test_governance_stamp_is_read_from_the_revision_not_defaulted(
    tree_modelos: tuple[ModeloDefinition, ...],
) -> None:
    """Mutation proof: stamping a revision must flip its row's provenance.

    A composer that emitted the fail-closed default unconditionally would pass
    the baseline assertion and fail every assertion after the mutation.
    """
    modelo = _modelo(tree_modelos, _MULTI_REVISION_MODELO)
    revision_id = sorted(modelo.revisions)[0]

    # BOTH ends of this mutation proof are constructed. The baseline used to
    # assume the bundled tree left every modelo 100 revision unstamped, so a
    # test about the COMPOSER broke the moment the campaign legitimately
    # stamped one -- and the stamping it was reading is exactly the work this
    # project is here to do. Forcing the pending end makes the assertion "the
    # composer reads the field" rather than "nobody has reviewed anything yet".
    modelo = modelo.model_copy(
        update={
            "revisions": {
                candidate_id: revision.model_copy(
                    update={
                        "review_status": RevisionReviewStatus.PENDING_REVIEW,
                        "reviewed_by": None,
                        "reviewed_at": None,
                        "engineered_by": None,
                    },
                )
                for candidate_id, revision in modelo.revisions.items()
            },
        },
    )

    baseline = _compose((modelo,))
    baseline_row = next(row for row in baseline.rows if row.revision == revision_id)
    assert baseline_row.governance.review_status is RevisionReviewStatus.PENDING_REVIEW
    assert baseline_row.governance.is_reviewed is False
    assert baseline_row.governance.engineered_by is None
    assert baseline.reviewed_revision_count == 0
    assert baseline.engineered_by_declared_count == 0

    stamped_revision = modelo.revisions[revision_id].model_copy(
        update={
            "review_status": RevisionReviewStatus.OPERATOR_REVIEWED,
            "reviewed_by": "operator",
            "reviewed_at": date(2026, 7, 27),
            "engineered_by": "conformance-cli",
        },
    )
    stamped_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision_id: stamped_revision}},
    )

    mutated = _compose((stamped_modelo,))
    mutated_row = next(row for row in mutated.rows if row.revision == revision_id)
    assert mutated_row.governance.review_status is RevisionReviewStatus.OPERATOR_REVIEWED
    assert mutated_row.governance.is_reviewed is True
    assert mutated_row.governance.reviewed_by == "operator"
    assert mutated_row.governance.reviewed_at == date(2026, 7, 27)
    assert mutated_row.governance.engineered_by == "conformance-cli"
    assert mutated.reviewed_revision_count == 1
    assert mutated.engineered_by_declared_count == 1

    untouched_rows = [row for row in mutated.rows if row.revision != revision_id]
    assert untouched_rows, "the mutation subject must not be the modelo's only revision"
    assert all(row.governance.review_status is RevisionReviewStatus.PENDING_REVIEW for row in untouched_rows)


def test_independent_check_coverage_distinguishes_absent_from_zero(
    tree_modelos: tuple[ModeloDefinition, ...],
) -> None:
    """Mutation proof: a revision that reconciles nothing scores ``None``, not ``0.0``.

    Three composes over the same modelo, differing only in the grounding row
    injected, must produce three different answers. Collapsing absence into zero
    fails the third assertion; hardcoding any single value fails two of them.
    """
    modelo = _modelo(tree_modelos, _GROUNDED_MODELO)
    grounding = build_external_grounding_audit(
        (modelo,),
        inventory=load_bundled_external_oracle_inventory(),
        registry_validated=False,
    )
    # The subject must DECLARE grounding, because the mutations below remove it
    # and compare. Selecting purely by "reconciles the most casillas" picked a
    # revision that legitimately declares none: modelo 303's 2024 is split at
    # September, and the external grounding belongs to the EARLY half because
    # its oracle is the AEAT Manual practico IVA 2024 first-trimester supuesto
    # practico. Declaring it on the September-onward half would ground a figure
    # that worked example never covers.
    grounded_rows = tuple(row for row in grounding.rows if row.declared_grounded_casilla_ids)
    assert grounded_rows, "modelo 303 no longer declares external grounding on any revision"
    subject = max(grounded_rows, key=lambda row: len(row.reconciled_casilla_ids))
    assert subject.reconciled_casilla_ids, "modelo 303 no longer reconciles any casilla"

    baseline_row = next(
        row for row in _compose((modelo,), external_grounding=grounding).rows if row.revision == subject.revision
    )
    baseline_coverage = baseline_row.independent_check_coverage
    assert baseline_coverage is not None
    assert baseline_coverage > 0.0
    assert baseline_row.reconciles_nothing is False

    ungrounded = grounding.model_copy(
        update={
            "rows": tuple(
                row.model_copy(update={"declared_grounded_casilla_ids": ()})
                if row.revision == subject.revision
                else row
                for row in grounding.rows
            ),
        },
    )
    ungrounded_row = next(
        row for row in _compose((modelo,), external_grounding=ungrounded).rows if row.revision == subject.revision
    )
    assert ungrounded_row.independent_check_coverage == 0.0
    assert ungrounded_row.reconciles_nothing is False

    unreconciled = grounding.model_copy(
        update={
            "rows": tuple(
                row.model_copy(update={"declared_grounded_casilla_ids": (), "reconciled_casilla_ids": ()})
                if row.revision == subject.revision
                else row
                for row in grounding.rows
            ),
        },
    )
    unreconciled_row = next(
        row for row in _compose((modelo,), external_grounding=unreconciled).rows if row.revision == subject.revision
    )
    assert unreconciled_row.reconciles_nothing is True
    assert unreconciled_row.independent_check_coverage is None


def test_registry_wide_coverage_is_absent_when_nothing_reconciles(
    tree_modelos: tuple[ModeloDefinition, ...],
) -> None:
    """The envelope ratio has no denominator to report, so it reports none."""
    modelo = _modelo(tree_modelos, _GROUNDED_MODELO)
    grounding = build_external_grounding_audit(
        (modelo,),
        inventory=load_bundled_external_oracle_inventory(),
        registry_validated=False,
    )
    assert _compose((modelo,), external_grounding=grounding).independent_check_coverage is not None

    emptied = grounding.model_copy(
        update={
            "rows": tuple(
                row.model_copy(update={"declared_grounded_casilla_ids": (), "reconciled_casilla_ids": ()})
                for row in grounding.rows
            ),
        },
    )
    assert _compose((modelo,), external_grounding=emptied).independent_check_coverage is None


def test_degraded_mode_stamps_every_row_and_withholds_the_authority_axes(
    degraded_profile: RegistryConformanceProfile,
) -> None:
    """The unvalidated label rides on each row, and unchecked axes stay absent."""
    assert degraded_profile.registry_validated is False
    assert degraded_profile.rows

    for row in degraded_profile.rows:
        assert row.registry_validated is False
        assert row.model_law_coverage is None
        assert row.latest_revision_support is None
        assert row.has_required_coverage_gap is None
        # Absent, NOT the default-deny verdict: reporting UNAUTHORIZED here
        # would assert an authorization state nobody checked.
        assert row.modelo_authorization is None


def test_degraded_authorization_absence_is_not_the_unauthorized_verdict(
    degraded_profile: RegistryConformanceProfile,
    validated_profile: RegistryConformanceProfile,
) -> None:
    """The validated read produces real verdicts where the degraded read produces none."""
    assert all(row.modelo_authorization is None for row in degraded_profile.rows)

    states = {row.modelo_authorization.state for row in validated_profile.rows if row.modelo_authorization}
    assert states, "the validated read produced no authorization verdict at all"
    assert AuthorizationState.AUTHORIZED in states
    assert AuthorizationState.UNAUTHORIZED in states


def test_validated_mode_carries_every_authority_dependent_axis(
    validated_profile: RegistryConformanceProfile,
) -> None:
    """What the degraded read withholds, the validating read supplies on every row."""
    assert validated_profile.registry_validated is True
    assert validated_profile.rows

    for row in validated_profile.rows:
        assert row.registry_validated is True
        assert row.model_law_coverage is not None
        assert row.latest_revision_support is not None
        assert row.modelo_authorization is not None
        assert row.has_required_coverage_gap is not None
        coverage = row.model_law_coverage
        assert set(coverage.required_tier_gaps) <= set(coverage.gap_tiers)
        assert not set(coverage.satisfied_tiers) & set(coverage.gap_tiers)


def test_support_probe_names_the_revision_it_probed(
    validated_profile: RegistryConformanceProfile,
) -> None:
    """The latest-revision probe is never silently attributed to an older revision."""
    rows = [row for row in validated_profile.rows if row.modelo == _MULTI_REVISION_MODELO]
    assert len(rows) > 1, "modelo 100 no longer carries several revisions"

    probes = [row.latest_revision_support for row in rows]
    assert all(probe is not None for probe in probes)
    probed = {probe.probed_revision for probe in probes if probe}
    assert len(probed) == 1, "one modelo's rows disagree about which revision was probed"

    describing = [
        row for row in rows if row.latest_revision_support and row.latest_revision_support.describes_this_revision
    ]
    assert len(describing) == 1
    assert describing[0].revision in probed

    for row in rows:
        probe = row.latest_revision_support
        assert probe is not None
        assert probe.describes_this_revision is (probe.probed_revision == row.revision)


def test_per_revision_capabilities_are_read_from_their_own_revision(
    validated_profile: RegistryConformanceProfile,
    tree_modelos: tuple[ModeloDefinition, ...],
) -> None:
    """Capability counts must match the revision on the row, not the latest one."""
    revisions = {
        (modelo.id, revision_id): revision
        for modelo in tree_modelos
        for revision_id, revision in modelo.revisions.items()
    }
    for row in validated_profile.rows:
        revision = revisions[(row.modelo, row.revision)]
        assert row.capabilities.casilla_count == len(revision.casillas)
        assert row.capabilities.formula_count == len(revision.formulas)
        assert row.capabilities.verification_expectation_count == len(revision.verification_expectations)
        assert row.capabilities.has_completeness_manifest is (revision.completeness_manifest is not None)


def test_scope_diagnostics_attribute_to_their_row_and_the_rest_are_preserved(
    tree_modelos: tuple[ModeloDefinition, ...],
) -> None:
    """A diagnostic naming a row lands on it; one naming no row is kept, not dropped."""
    modelo = _modelo(tree_modelos, _MULTI_REVISION_MODELO)
    target_revision = sorted(modelo.revisions)[0]
    other_revision = sorted(modelo.revisions)[1]
    owned = f"modelo {modelo.id} revision {target_revision}: injected per-revision diagnostic"
    registry_wide = "registry: injected corpus-wide diagnostic"

    profile = _compose((modelo,), scope_diagnostics=(owned, registry_wide))

    target_row = next(row for row in profile.rows if row.revision == target_revision)
    other_row = next(row for row in profile.rows if row.revision == other_revision)
    assert target_row.scope_diagnostics == (owned,)
    assert other_row.scope_diagnostics == ()
    assert profile.scope_diagnostics == (owned, registry_wide)
    assert profile.unattributed_scope_diagnostics == (registry_wide,)


def test_missing_grounding_row_refuses_rather_than_dropping_the_revision(
    tree_modelos: tuple[ModeloDefinition, ...],
) -> None:
    """A revision the composer cannot fully describe must not vanish from the census."""
    modelo = _modelo(tree_modelos, _MULTI_REVISION_MODELO)
    grounding = build_external_grounding_audit(
        (modelo,),
        inventory=load_bundled_external_oracle_inventory(),
        registry_validated=False,
    )
    dropped_revision = grounding.rows[0].revision
    truncated = grounding.model_copy(update={"rows": grounding.rows[1:]})

    with pytest.raises(RegistryApplicationInputError) as excinfo:
        _compose((modelo,), external_grounding=truncated)

    assert excinfo.value.context == {"modelo": modelo.id, "revision_id": dropped_revision}


def test_empty_coverage_gap_list_is_separable_from_unmeasured_coverage(
    degraded_profile: RegistryConformanceProfile,
    validated_profile: RegistryConformanceProfile,
) -> None:
    """An empty gap list must not read as a clean bill of health on an unmeasured profile."""
    assert degraded_profile.required_coverage_gap_rows == ()
    assert len(degraded_profile.coverage_unmeasured_rows) == degraded_profile.composed_revision_count

    assert validated_profile.coverage_unmeasured_rows == ()
    assert set(validated_profile.required_coverage_gap_rows) <= set(validated_profile.rows)


def test_classification_finding_count_is_named_for_its_modelo_scope(
    validated_profile: RegistryConformanceProfile,
) -> None:
    """The modelo-level count repeats across a modelo's revisions, so its name says so."""
    by_modelo: dict[str, set[int]] = {}
    for row in validated_profile.rows:
        by_modelo.setdefault(row.modelo, set()).add(row.modelo_classification_finding_count)

    assert all(len(counts) == 1 for counts in by_modelo.values())


def test_declared_axis_census_reaches_the_profile(degraded_profile: RegistryConformanceProfile) -> None:
    """A dead schema axis must be visible as unused rather than silently passing."""
    assert degraded_profile.declared_axis_usage
    for usage in degraded_profile.declared_axis_usage:
        assert usage.declaration_count <= usage.population
        assert usage.status in {"exercised", "unused"}


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_annual_casilla_comparison_uses_the_selected_year_dictionary(
    registry_authority: ValidatedRegistryAuthority,
    filing_year: int,
) -> None:
    """The comparator measures each law-selected M100 dictionary independently."""
    snapshot = registry_authority.snapshot("100", filing_year=filing_year, period="0A")
    comparison = compare_annual_casilla_population(snapshot, source_root=registry_authority.source_root)

    assert isinstance(comparison, AnnualCasillaPopulationComparison)
    assert comparison.modelo == "100"
    assert comparison.filing_year == filing_year
    assert comparison.period == "0A"
    assert comparison.law_selected_revision == str(filing_year)
    assert comparison.identity_measurement == "measured"
    assert comparison.printed_form_membership == "unsupported"
    assert comparison.xsd_only_attributes == "unsupported"
    assert comparison.printed_form_source_refs == (f"boe-modelo-100-{filing_year}-form",)
    assert comparison.xsd_source_refs == (f"aeat-dr-100-{filing_year}-xsd",)

    dictionary_layout = next(
        layout for layout in snapshot.revision.export_layouts if layout.format is ExportLayoutFormat.XML_DICTIONARY
    )
    assert len(comparison.layout_comparisons) == len(snapshot.revision.export_layouts)
    layout_comparison = next(item for item in comparison.layout_comparisons if item.layout_id == dictionary_layout.id)
    assert layout_comparison.layout_format == ExportLayoutFormat.XML_DICTIONARY.value
    assert layout_comparison.identity_measurement == "measured"
    assert layout_comparison.printed_form_membership == "unsupported"
    assert layout_comparison.xsd_only_attributes == "unsupported"
    assert layout_comparison.dictionary_source_ref == f"aeat-dr-100-{filing_year}-dictionary"
    assert layout_comparison.parser_exposed_attributes == ("field_id", "path", "data_type", "casilla_id")
    assert "data_type" in layout_comparison.unmeasured_attributes
    assert layout_comparison.dictionary_casilla_count == _M100_DICTIONARY_CASILLA_COUNTS[filing_year]

    # Every casilla AEAT declares for this year is declared by the registry.
    assert layout_comparison.extra_casilla_ids == ()

    # And every registry casilla carrying an AEAT NUMBER appears in that year's
    # dictionary. Boxes AEAT does not number -- the ``*NN`` datos-identificativos
    # series, the unnumbered ``###`` rows, and app-internal values -- carry
    # descriptive ids and are legitimately absent, so they are excluded by shape
    # rather than by being counted.
    #
    # This bites: modelo 100 declared casilla ``0058`` for 2024 and ``0059`` for
    # 2025, both for the LIRPF art. 7.h exempt INSS benefit, and neither number
    # appears in ANY bundled AEAT source for its year -- not the dictionary it
    # cited, not the input dictionary, not the XSD, not the Renta manual. Both
    # now carry a descriptive id.
    fabricated = sorted(
        casilla_id for casilla_id in (layout_comparison.missing_casilla_ids or ()) if casilla_id.isdigit()
    )
    assert not fabricated, (
        f"{filing_year} declares AEAT-numbered casilla(s) {fabricated} that its own dictionary does not contain"
    )

    entries = xml_dictionary_entries(
        dictionary_layout,
        source_root=registry_authority.source_root,
        sources=snapshot.sources,
    )
    dictionary_ids = {str(entry.casilla_id) for entry in entries if entry.casilla_id is not None}
    registry_ids = {str(casilla.id) for casilla in snapshot.revision.casillas if not casilla.internal_only}
    assert layout_comparison.dictionary_entry_count == len(entries)
    assert layout_comparison.dictionary_casilla_count == len(dictionary_ids)
    assert set(layout_comparison.missing_casilla_ids) == registry_ids - dictionary_ids
    assert set(layout_comparison.extra_casilla_ids) == dictionary_ids - registry_ids
    assert comparison.missing_casilla_ids == layout_comparison.missing_casilla_ids
    assert comparison.extra_casilla_ids == layout_comparison.extra_casilla_ids


def test_annual_casilla_comparison_retains_unmeasured_when_source_root_is_unavailable(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """A declared layout without its parser source is not reported as a clean result."""
    snapshot = registry_authority.snapshot("100", filing_year=2025, period="0A")

    comparison = compare_annual_casilla_population(snapshot)
    dictionary_layout = next(
        layout for layout in snapshot.revision.export_layouts if layout.format is ExportLayoutFormat.XML_DICTIONARY
    )
    layout_comparison = next(item for item in comparison.layout_comparisons if item.layout_id == dictionary_layout.id)

    assert comparison.identity_measurement == "unmeasured"
    assert layout_comparison.identity_measurement == "unmeasured"
    assert layout_comparison.dictionary_entry_count is None
    assert layout_comparison.dictionary_casilla_count is None
    assert layout_comparison.missing_casilla_ids == ()
    assert layout_comparison.extra_casilla_ids == ()
    assert layout_comparison.parser_exposed_attributes == ("field_id", "path", "data_type", "casilla_id")
    assert layout_comparison.diagnostic is not None
    assert "requires source_root" in layout_comparison.diagnostic
    assert comparison.printed_form_membership == "unsupported"
    assert comparison.xsd_only_attributes == "unsupported"


def test_annual_casilla_comparison_accepts_typed_inspection_without_snapshot(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """Static annual schema evidence does not cross the filing snapshot gate."""
    inspection = registry_authority.inspect_revision("100", filing_year=2025, period="0A")
    revision = registry_authority.modelo("100").revisions[inspection.revision_id]

    comparison = compare_annual_casilla_population_for_revision(
        modelo=inspection.modelo_id,
        revision=revision,
        filing_year=2025,
        period="0A",
        sources=inspection.sources,
        source_root=registry_authority.source_root,
    )

    assert comparison.authority_scope == "inspection_only"
    assert comparison.law_selected_revision == inspection.revision_id
    assert comparison.identity_measurement == "measured"
    assert comparison.layout_comparisons


def test_a_modelo_absent_from_the_classification_audit_is_refused(
    tree_modelos: tuple[ModeloDefinition, ...],
) -> None:
    """A modelo the classification audit omits must refuse before any row is built."""
    modelos = (_modelo(tree_modelos, _GROUNDED_MODELO),)
    grounding = build_external_grounding_audit(
        modelos,
        inventory=load_bundled_external_oracle_inventory(),
        registry_validated=False,
    )
    classification = build_classification_coherence_audit(
        modelos,
        non_registry_modelo_codes=frozenset(item.value for item in NON_REGISTRY_MODELOS),
        known_modelo_codes=frozenset(item.value for item in Modelo),
        registry_validated=False,
    )
    assert classification.rows, "the classification fold must produce a row to drop"
    emptied = classification.model_copy(update={"rows": ()})

    with pytest.raises(RegistryApplicationInputError) as excinfo:
        build_registry_conformance_profile(
            modelos,
            external_grounding=grounding,
            classification=emptied,
            scope_diagnostics=(),
            registry_validated=False,
        )

    assert excinfo.value.context == {"modelo": _GROUNDED_MODELO}


__all__ = ["degraded_profile", "validated_profile"]
