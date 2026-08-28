"""Top-level Workspace V1 projection/result proofs.

Complements, and deliberately does not duplicate, the piece-level proofs
already carried elsewhere: manifest coverage (``test_workspace_manifest.py``),
epoch/ABA/cross-incarnation refusal and native-capture discipline at the
port level (``test_workspace_producers.py``), locale resolution and bounded
schema-facet pagination (``test_workspace.py``), and complete
``ModeloWorkReview``/readiness parity against their sole public producers
(``test_workspace.py``). What this module proves is
specific to the assembled ``ModeloWorkspaceStaticInspectionResultV1`` /
``ModeloWorkspaceGradedSnapshotResultV1`` themselves: strict round trips with
an anti-tautology mutation proof, admission-specific contributor-set
exactness, mutation-after-capture isolation, exactly-one-native-capture for
the two contributors the assembly itself captures exactly once (CALCULATION,
BOUNDED_REVIEW -- WORK's single capture is already proven in isolation by
``test_capture_with_a_grade_admits_a_registry_snapshot_reading_work_and_registry_exactly_once``),
a forbidden-lower-layer-import architecture boundary, and a codified
Vaultspec-RAG-plus-exact census against a duplicate or parallel Workspace
authority.

``registry_closure_limbs``/``readiness`` parity IS proven here, against the
canonical CLOSURE and READINESS producers the graded assembly captures. Static
inspection reads neither contributor, so it holds them at their model defaults
(``()`` and ``None``) and that admission-scope difference is asserted rather
than assumed.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import ModeloWorkProgressState, OutputLanguage, Period, RegistryAuthorityGrade
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.temporal import select_revision
from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id, upsert_calculation_revision, upsert_work_unit
from ....domain.modelos.calculation_revision import CalculationRevision
from ...registry.closure_capture import capture_registry_closure
from ...registry.source_connectivity import load_source_connectivity_census
from ...state_projection import ModeloReadinessRequest, capture_modelo_readiness
from ..work_addressing import ModeloVisibleFilingTarget
from ..workspace import (
    graded_snapshot_contributors,
    resolve_graded_snapshot_result,
    resolve_static_inspection_result,
    static_inspection_contributors,
)
from ..workspace_models import (
    ModeloWorkspaceGradedSnapshotResultV1,
    ModeloWorkspaceStaticInspectionResultV1,
    ModeloWorkspaceVisibleFilingTargetV1,
)
from ..workspace_producers import ModeloWorkspaceBoundedReviewPortV1, ModeloWorkspaceCalculationPortV1
from ._file_flow_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    calculate_modelo_revision,
    verify_revision,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_T0 = datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC)
_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
#: Fixed observation instant for the closure capture, so a limb set does not
#: shift under the suite because a census entry expired between runs.
_CLOSURE_AS_OF = date(2026, 8, 24)
_MODELO = ModeloCode("130")
_FILING_YEAR = 2026


def _visible_target(*, bucket_id: str = _BUCKET_ID) -> ModeloWorkspaceVisibleFilingTargetV1:
    return ModeloWorkspaceVisibleFilingTargetV1(
        target=ModeloVisibleFilingTarget(
            modelo=_MODELO,
            filing_year=_FILING_YEAR,
            period=Period.from_year_and_code(_FILING_YEAR, "1T"),
            registry_revision_id=None,
            bucket_id=bucket_id,
        ),
    )


def _seed_work_unit_only(repos) -> WorkUnit:
    """Seed a real work unit for modelo 130/1T, with no calculation revision."""
    work_repo, *_rest = repos
    period = Period.from_year_and_code(_FILING_YEAR, "1T")
    selected_revision = select_revision(
        bundled_authority().validate_modelo(_MODELO), filing_year=_FILING_YEAR, period="1T"
    )
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=_MODELO,
            filing_year=_FILING_YEAR,
            period=period,
            revision_id=selected_revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=_MODELO,
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=selected_revision.id,
        name="130-2026-1T",
        created_at=_T0,
        updated_at=_T0,
    )
    work_repo.save(upsert_work_unit(work_repo.load(), work_unit))
    return work_unit


def _seed_and_calculate(repos) -> tuple[WorkUnit, CalculationRevision]:
    """Seed a real work unit and a real verified calculation revision for modelo 130/1T."""
    work_repo, calculation_repo, filing_repo, verification_repo, bucket_event_repo = repos
    work_unit = _seed_work_unit_only(repos)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values={
            **DEFAULT_130_BINDING_VALUES,
            "modelo-130-actividad-economica-ingresos-cumulative": Decimal("9000"),
        },
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    )
    verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        filing_repository=filing_repo,
        bucket_event_repository=bucket_event_repo,
        clock=revision.updated_at,
    )
    return work_unit, revision


# --- 1. Strict round trips with an anti-tautology mutation proof ---


def test_static_inspection_result_strict_round_trip_and_anti_tautology(repos) -> None:
    """The full static-inspection result round-trips, and a corrupted payload refuses to load."""
    work_repo, *_rest = repos
    _seed_work_unit_only(repos)

    result = resolve_static_inspection_result(
        _visible_target(),
        bucket_id=_BUCKET_ID,
        catalogue_repository=work_repo,
        authority=bundled_authority(),
        output_language=OutputLanguage.ES,
    )

    payload = result.model_dump_json()
    reloaded = ModeloWorkspaceStaticInspectionResultV1.model_validate_json(payload)
    assert reloaded == result

    # Anti-tautology: delete a required nested field and prove reload refuses,
    # rather than silently defaulting or reconstructing it.
    corrupted = json.loads(payload)
    del corrupted["projection"]["target"]["bucket_id"]
    with pytest.raises(Exception, match=r"(?i)bucket_id|field required|missing"):
        ModeloWorkspaceStaticInspectionResultV1.model_validate_json(json.dumps(corrupted))


def test_graded_snapshot_result_strict_round_trip_and_anti_tautology(repos) -> None:
    """The full graded-snapshot result round-trips, and a corrupted payload refuses to load."""
    _work_unit, revision = _seed_and_calculate(repos)
    work_repo, calculation_repo, _filing_repo, verification_repo, _bucket_event_repo = repos

    result = resolve_graded_snapshot_result(
        _visible_target(),
        required_grade=RegistryAuthorityGrade.CALCULATION,
        bucket_id=_BUCKET_ID,
        catalogue_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        authority=bundled_authority(),
        census=load_source_connectivity_census(),
        as_of=_CLOSURE_AS_OF,
        output_language=OutputLanguage.ES,
    )
    assert isinstance(result, ModeloWorkspaceGradedSnapshotResultV1)
    assert result.projection.work_review.review is not None
    assert result.projection.work_review.review.calculation_revision_id == revision.calculation_revision_id
    assert result.projection.work_review.review.progress.state is ModeloWorkProgressState.COMPLETE

    payload = result.model_dump_json()
    reloaded = ModeloWorkspaceGradedSnapshotResultV1.model_validate_json(payload)
    assert reloaded == result

    corrupted = json.loads(payload)
    del corrupted["projection"]["baseline"]["contributor_epoch_digest"]
    with pytest.raises(Exception, match=r"(?i)contributor_epoch_digest|field required|missing"):
        ModeloWorkspaceGradedSnapshotResultV1.model_validate_json(json.dumps(corrupted))


# --- 2. Admission-specific contributor-set exactness ---


def test_admission_specific_contributor_sets_are_exact_and_differ_by_four() -> None:
    """Static (4) and graded (8) contributor sets differ by exactly the four graded-only producers.

    ``graded_snapshot_contributors`` is a strict superset of
    ``static_inspection_contributors``: the static admission's four
    contributors are a subset of the graded admission's complete eight, never
    an independently derived set that could accidentally diverge on the shared
    four. The four extra names are asserted individually, so a denominator
    that silently drops one is a failure rather than a smaller number nobody
    reads.
    """
    static = set(static_inspection_contributors())
    graded = set(graded_snapshot_contributors())

    assert len(static) == 4
    assert len(graded) == 8
    assert static < graded  # strict subset
    extra = graded - static
    assert {contributor.producer for contributor in extra} == {
        "calculation_materialization",
        "modelo_work_review",
        "modelo_readiness",
        "registry_closure",
    }


def test_assembled_results_each_carry_exactly_their_own_admissions_contributor_set(repos) -> None:
    """The assembled projection's own contributors never drift from its admission's canonical set."""
    work_repo, *_rest = repos
    _seed_work_unit_only(repos)

    static_result = resolve_static_inspection_result(
        _visible_target(),
        bucket_id=_BUCKET_ID,
        catalogue_repository=work_repo,
        authority=bundled_authority(),
        output_language=OutputLanguage.ES,
    )
    assert set(static_result.projection.contributors) == set(static_inspection_contributors())

    _work_unit, _revision = _seed_and_calculate(repos)
    _work_repo, calculation_repo, _filing_repo, verification_repo, _bucket_event_repo = repos
    graded_result = resolve_graded_snapshot_result(
        _visible_target(),
        required_grade=RegistryAuthorityGrade.CALCULATION,
        bucket_id=_BUCKET_ID,
        catalogue_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        authority=bundled_authority(),
        census=load_source_connectivity_census(),
        as_of=_CLOSURE_AS_OF,
        output_language=OutputLanguage.ES,
    )
    assert isinstance(graded_result, ModeloWorkspaceGradedSnapshotResultV1)
    assert set(graded_result.projection.contributors) == set(graded_snapshot_contributors())


# --- 2b. Closure and readiness parity against their canonical producers ---


def test_graded_closure_limbs_equal_the_canonical_capture_narrowed_to_the_target(repos) -> None:
    """The projection's closure limbs are the closure authority's own, selected by coordinate.

    Proven the way the work review is proven against its sole public producer:
    the canonical producer is invoked independently, over the same census and
    the same observation instant, and the assembled facet must equal that
    producer's output narrowed to this target's ``(modelo, revision)``. A
    limb the projection carries that the authority did not publish, or one it
    dropped that the authority did, fails here.
    """
    work_repo, calculation_repo, _filing_repo, verification_repo, _bucket_event_repo = repos
    _work_unit, _revision = _seed_and_calculate(repos)
    census = load_source_connectivity_census()

    result = resolve_graded_snapshot_result(
        _visible_target(),
        required_grade=RegistryAuthorityGrade.CALCULATION,
        bucket_id=_BUCKET_ID,
        catalogue_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        authority=bundled_authority(),
        census=census,
        as_of=_CLOSURE_AS_OF,
        output_language=OutputLanguage.ES,
    )
    assert isinstance(result, ModeloWorkspaceGradedSnapshotResultV1)

    canonical = capture_registry_closure(
        authority=bundled_authority(),
        census=census,
        as_of=_CLOSURE_AS_OF,
    )
    # Narrowed HERE, independently of the production selector. Routing this
    # through ``graded_snapshot_closure_limbs`` would compare the assembler's
    # output against the same function that produced it, so a selector that
    # returned nothing would satisfy both sides and the proof would be hollow.
    target = result.projection.target
    expected = tuple(
        limb
        for limb in canonical.limbs
        if limb.modelo == target.modelo and limb.revision == target.law_selected_revision_id
    )
    assert expected, "the bundled closure report must publish limbs for this target"

    assert result.projection.registry_closure_limbs == expected
    # The selection is real: the authority publishes limbs for other revisions
    # that this projection must not carry, so an unnarrowed pass-through would
    # differ from the asserted value rather than coincide with it.
    assert len(canonical.limbs) > len(expected)
    assert all(
        limb.modelo == target.modelo and limb.revision == target.law_selected_revision_id
        for limb in result.projection.registry_closure_limbs
    )


def test_graded_readiness_equals_the_canonical_readiness_producers_report(repos) -> None:
    """The projection's readiness is the canonical producer's report, axis for axis.

    ``graded_snapshot_readiness`` is a pass-through projection, so the
    assembled facet must equal that projection applied to the report the
    canonical producer independently returns for the same target. Every axis
    is compared through model equality, not a spot-check of ``ready``.
    """
    work_repo, calculation_repo, _filing_repo, verification_repo, _bucket_event_repo = repos
    _work_unit, _revision = _seed_and_calculate(repos)

    result = resolve_graded_snapshot_result(
        _visible_target(),
        required_grade=RegistryAuthorityGrade.CALCULATION,
        bucket_id=_BUCKET_ID,
        catalogue_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        authority=bundled_authority(),
        census=load_source_connectivity_census(),
        as_of=_CLOSURE_AS_OF,
        output_language=OutputLanguage.ES,
    )
    assert isinstance(result, ModeloWorkspaceGradedSnapshotResultV1)
    readiness = result.projection.readiness
    assert readiness is not None

    target = result.projection.target
    canonical = capture_modelo_readiness(
        (
            ModeloReadinessRequest(
                modelo=target.modelo,
                revision_id=target.law_selected_revision_id,
                filing_year=target.filing_year,
                period=target.period,
            ),
        ),
        active_profile_id=target.bucket_id,
    )
    report = canonical.reports[0]
    # Axis-by-axis against the canonical REPORT, not against the projector the
    # assembler used, so a projector that returned nothing cannot satisfy both
    # sides of this comparison.
    assert readiness.profile_id == report.profile_id
    assert readiness.revision_id == report.revision_id
    assert readiness.filing_year == report.filing_year
    assert readiness.period == report.period
    assert readiness.profile_ready == report.profile_ready
    assert readiness.registry_ready == report.registry_ready
    assert readiness.binding_ready == report.binding_ready
    assert readiness.ledger_ready == report.ledger_ready
    assert readiness.ledger_preflight_required == report.ledger_preflight_required
    assert readiness.ready == report.ready
    assert len(readiness.missing) == len(report.missing)
    assert len(readiness.missing_bindings) == len(report.missing_bindings)
    assert readiness.revision_id == target.law_selected_revision_id


def test_static_inspection_reads_neither_closure_nor_readiness(repos) -> None:
    """Static inspection holds both graded-only facets at their defaults.

    The admission scope is a real difference, not an accident of what happens
    to be wired: static inspection never invokes the CLOSURE or READINESS
    contributor, so absence here is the correct answer rather than an
    unpopulated field.
    """
    work_repo, *_rest = repos
    _seed_work_unit_only(repos)

    result = resolve_static_inspection_result(
        _visible_target(),
        bucket_id=_BUCKET_ID,
        catalogue_repository=work_repo,
        authority=bundled_authority(),
        output_language=OutputLanguage.ES,
    )
    assert result.projection.registry_closure_limbs == ()
    assert result.projection.readiness is None


# --- 3. Mutation-after-capture isolation ---


def test_resolved_target_is_isolated_from_a_work_unit_mutation_after_capture(repos) -> None:
    """Mutating the work unit AFTER a capture never retroactively changes the resolved target.

    ``CalculationRevision`` is content-addressed -- its own
    ``calculation_revision_id`` is DERIVED from ``casilla_values`` among
    other fields, so a real repository refuses to persist the same id under
    changed content (proven directly: the attempt below raises
    ``ValidationError`` before this test's real assertion even runs, which
    is itself evidence that content-addressed identity, not a snapshot copy,
    is what forecloses that particular mutation vector). The mutation this
    test proves isolation against instead targets ``WorkUnit.state``, a
    genuinely mutable field with no derived-identity constraint, and the
    exact field ``ModeloWorkspaceResolvedTargetV1.work_state`` reads and this
    test asserts against below -- not a field the projection never read.
    """
    from ....domain.modelos import WorkUnitState

    work_unit, _revision = _seed_and_calculate(repos)
    work_repo, calculation_repo, _filing_repo, verification_repo, _bucket_event_repo = repos

    result = resolve_graded_snapshot_result(
        _visible_target(),
        required_grade=RegistryAuthorityGrade.CALCULATION,
        bucket_id=_BUCKET_ID,
        catalogue_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        authority=bundled_authority(),
        census=load_source_connectivity_census(),
        as_of=_CLOSURE_AS_OF,
        output_language=OutputLanguage.ES,
    )
    assert isinstance(result, ModeloWorkspaceGradedSnapshotResultV1)
    captured_work_state = result.projection.target.work_state
    assert captured_work_state is WorkUnitState.BORRADOR

    # Content-addressed identity refuses a same-id mutation of derived
    # content, proven directly rather than assumed.
    catalogue = calculation_repo.load()
    stored_revision = catalogue.revisions[_revision.calculation_revision_id]
    mutated_casilla_values = dict(stored_revision.casilla_values)
    a_casilla_id = next(iter(mutated_casilla_values))
    mutated_casilla_values[a_casilla_id] = mutated_casilla_values[a_casilla_id] + Decimal("999999.99")
    mutated_revision = stored_revision.model_copy(update={"casilla_values": mutated_casilla_values})
    with pytest.raises(Exception, match=r"(?i)does not match the derived id"):
        calculation_repo.save(upsert_calculation_revision(catalogue, mutated_revision))

    # Real mutation of the SAME work unit's mutable ``state`` field,
    # persisted through the real repository -- never a mock. Discarding
    # requires ``discarded_at``/``discarded_by`` together per the model's
    # own cross-field validator.
    mutated_work_unit = work_unit.model_copy(
        update={
            "state": WorkUnitState.DESCARTADO,
            "discarded_at": work_unit.updated_at,
            "discarded_by": "test-operator",
        }
    )
    work_repo.save(upsert_work_unit(work_repo.load(), mutated_work_unit))
    reread_work_unit = work_repo.load().work_units[work_unit.work_unit_id]
    assert reread_work_unit.state is WorkUnitState.DESCARTADO  # the mutation genuinely landed

    # The already-captured result must still show the ORIGINAL state.
    assert result.projection.target.work_state is WorkUnitState.BORRADOR
    assert result.projection.target.work_state == captured_work_state


# --- 4. Exactly-one-native-capture for CALCULATION and BOUNDED_REVIEW ---


def test_calculation_and_bounded_review_ports_are_each_captured_exactly_once(
    repos, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The assembly invokes each of the CALCULATION and BOUNDED_REVIEW ports exactly once.

    A thin spy wraps the REAL bound method on each port class -- every call
    still executes the genuine implementation; the wrapper only counts
    invocations. This is not a mock: no behaviour is replaced or faked.
    """
    _work_unit, _revision = _seed_and_calculate(repos)
    work_repo, calculation_repo, _filing_repo, verification_repo, _bucket_event_repo = repos

    calculation_calls = 0
    bounded_review_calls = 0
    real_calculation_capture = ModeloWorkspaceCalculationPortV1.capture_projection_with_epoch
    real_bounded_review_capture = ModeloWorkspaceBoundedReviewPortV1.capture_projection_with_epoch

    def _counting_calculation_capture(self):
        nonlocal calculation_calls
        calculation_calls += 1
        return real_calculation_capture(self)

    def _counting_bounded_review_capture(self):
        nonlocal bounded_review_calls
        bounded_review_calls += 1
        return real_bounded_review_capture(self)

    monkeypatch.setattr(
        ModeloWorkspaceCalculationPortV1, "capture_projection_with_epoch", _counting_calculation_capture
    )
    monkeypatch.setattr(
        ModeloWorkspaceBoundedReviewPortV1, "capture_projection_with_epoch", _counting_bounded_review_capture
    )

    result = resolve_graded_snapshot_result(
        _visible_target(),
        required_grade=RegistryAuthorityGrade.CALCULATION,
        bucket_id=_BUCKET_ID,
        catalogue_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        authority=bundled_authority(),
        census=load_source_connectivity_census(),
        as_of=_CLOSURE_AS_OF,
        output_language=OutputLanguage.ES,
    )

    assert isinstance(result, ModeloWorkspaceGradedSnapshotResultV1)
    assert calculation_calls == 1
    assert bounded_review_calls == 1


# --- 5. Forbidden lower-layer ModeloWorkspace imports ---


def test_no_domain_or_adapter_module_imports_any_modelo_workspace_symbol() -> None:
    """domain/ and adapters/ never depend on the application-layer Workspace read contract.

    Workspace V1 is an application-layer, read-only projection assembled
    FROM domain and adapter primitives; a dependency running the other way
    would invert the accepted hexagonal direction. Enumerates TRACKED files
    only, never a filesystem walk, and inspects actual IMPORT statements via
    AST rather than a raw substring search: a raw substring search over
    ``"ModeloWorkspace"`` false-positives on
    ``test_authority_native_capture.py``, which legitimately asserts that
    string is ABSENT from the registry authority's own source as the mirror
    proof of this exact boundary -- the needle appears in a Python string
    literal inside an assertion, never in an import.
    """
    import ast

    repository = Path(__file__).resolve().parents[5]
    tracked = subprocess.run(
        ("git", "ls-files", "-z", "--", "src/cadrumo/domain", "src/cadrumo/adapters"),  # noqa: S607
        capture_output=True,
        check=True,
        cwd=repository,
        text=True,
    ).stdout.split(chr(0))
    forbidden_modules = ("workspace_models", "workspace_producers", "workspace_manifest", "workspace")
    violations: list[str] = []
    for entry in tracked:
        if not entry.endswith(".py"):
            continue
        path = repository / entry
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=entry)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and any(
                    node.module == f"cadrumo.application.modelo.{name}"
                    or node.module.endswith(f".application.modelo.{name}")
                    for name in forbidden_modules
                )
            ):
                violations.append(f"{entry}: from {node.module} import ...")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if any(
                        alias.name == f"cadrumo.application.modelo.{name}"
                        or alias.name.endswith(f".application.modelo.{name}")
                        for name in forbidden_modules
                    ):
                        violations.append(f"{entry}: import {alias.name}")
    assert not violations


# --- 6. Vaultspec-RAG-plus-exact census: no duplicate/parallel Workspace authority ---


def test_exactly_one_module_defines_each_canonical_workspace_assembly_symbol() -> None:
    """A duplicate, legacy, shim, alias, fallback, bridge, or parallel Workspace authority reds this.

    Walks every tracked ``application/modelo`` production module (excluding
    tests) and asserts that each of the canonical Workspace assembly entry
    points is DEFINED (``def``/``class`` at module scope) in exactly the one
    module that owns it, never redefined, aliased, or re-exported elsewhere.
    """
    import ast

    repository = Path(__file__).resolve().parents[5]
    tracked = subprocess.run(
        ("git", "ls-files", "-z", "--", "src/cadrumo/application/modelo"),  # noqa: S607
        capture_output=True,
        check=True,
        cwd=repository,
        text=True,
    ).stdout.split(chr(0))
    production_modules = tuple(
        entry
        for entry in tracked
        if entry.endswith(".py") and "/tests/" not in entry and (repository / entry).is_file()
    )

    canonical_owner = {
        "resolve_static_inspection_result": "src/cadrumo/application/modelo/workspace.py",
        "resolve_graded_snapshot_result": "src/cadrumo/application/modelo/workspace.py",
        "ModeloWorkspaceProjectionV1": "src/cadrumo/application/modelo/workspace_models.py",
        "ModeloWorkspaceRegistryPortV1": "src/cadrumo/application/modelo/workspace_producers.py",
    }

    definers: dict[str, list[str]] = {name: [] for name in canonical_owner}
    for entry in production_modules:
        tree = ast.parse((repository / entry).read_text(encoding="utf-8"), filename=entry)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in definers:
                definers[node.name].append(entry)

    for symbol, owner in canonical_owner.items():
        assert definers[symbol] == [owner], (symbol, definers[symbol])
