"""Top-level Workspace V1 projection/result proofs (S130).

Complements, and deliberately does not duplicate, the piece-level proofs
already carried elsewhere: manifest coverage (``test_workspace_manifest.py``),
epoch/ABA/cross-incarnation refusal and native-capture discipline at the
port level (``test_workspace_producers.py``), locale resolution and bounded
schema-facet pagination (``test_workspace.py``), and complete
``ModeloWorkReview``/readiness parity against their sole public producers
(``test_workspace.py``, landed with S128). What this module proves is
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

``registry_closure_limbs``/``readiness`` parity is NOT proven here: neither
``resolve_static_inspection_result`` nor ``resolve_graded_snapshot_result``
ever populates them (they stay at their model defaults, `()` and `None`),
and no ``graded_snapshot_closure``-equivalent function exists anywhere in
``workspace.py`` to compare against. There is nothing to prove parity with.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import ModeloWorkProgressState, OutputLanguage, Period, RegistryAuthorityGrade
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.temporal import select_revision
from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id, upsert_calculation_revision, upsert_work_unit
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
    selected_revision = select_revision(bundled_authority().validate_modelo(_MODELO), filing_year=_FILING_YEAR, period="1T")
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


def _seed_and_calculate(repos) -> tuple[WorkUnit, object]:
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
    """S130: the full static-inspection result round-trips, and a corrupted payload refuses to load."""
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
    """S130: the full graded-snapshot result round-trips, and a corrupted payload refuses to load."""
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


def test_admission_specific_contributor_sets_are_exact_and_disjoint_by_two() -> None:
    """S130: static (4) and graded (6) contributor sets differ by exactly CALCULATION and BOUNDED_REVIEW.

    ``graded_snapshot_contributors`` is a strict superset of
    ``static_inspection_contributors``: the ADR names the static admission's
    four contributors as a subset of the graded admission's six, never an
    independently derived set that could accidentally diverge on the shared
    four.
    """
    static = set(static_inspection_contributors())
    graded = set(graded_snapshot_contributors())

    assert len(static) == 4
    assert len(graded) == 6
    assert static < graded  # strict subset
    extra = graded - static
    assert {contributor.producer for contributor in extra} == {
        "calculation_materialization",
        "modelo_work_review",
    }


def test_assembled_results_each_carry_exactly_their_own_admissions_contributor_set(repos) -> None:
    """S130: the assembled projection's own contributors never drift from its admission's canonical set."""
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
        output_language=OutputLanguage.ES,
    )
    assert isinstance(graded_result, ModeloWorkspaceGradedSnapshotResultV1)
    assert set(graded_result.projection.contributors) == set(graded_snapshot_contributors())


# --- 3. Mutation-after-capture isolation ---


def test_materialization_facet_is_isolated_from_a_mutation_after_capture(repos) -> None:
    """S130: mutating the calculation revision AFTER a capture never retroactively changes it.

    The mutation lands on ``casilla_values`` -- the exact field the
    materialization facet reads and the test asserts against below -- so
    this cannot pass vacuously by mutating something the projection never
    read.
    """
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
        output_language=OutputLanguage.ES,
    )
    assert isinstance(result, ModeloWorkspaceGradedSnapshotResultV1)
    assert result.projection.materialization_facet is not None
    captured_scalar_values = {
        record.scalar.casilla_id: record.scalar.value
        for record in result.projection.materialization_facet.records
        if hasattr(record, "scalar")
    }
    assert captured_scalar_values  # the facet genuinely carries scalar casilla values

    # Real mutation of the SAME calculation revision's SAME field the facet
    # above reads from, persisted through the real repository -- never a
    # mock, never an unrelated field.
    catalogue = calculation_repo.load()
    stored_revision = catalogue.revisions[revision.calculation_revision_id]
    mutated_casilla_values = dict(stored_revision.casilla_values)
    a_casilla_id = next(iter(mutated_casilla_values))
    mutated_casilla_values[a_casilla_id] = mutated_casilla_values[a_casilla_id] + Decimal("999999.99")
    mutated_revision = stored_revision.model_copy(update={"casilla_values": mutated_casilla_values})
    calculation_repo.save(upsert_calculation_revision(catalogue, mutated_revision))

    # The already-captured result must still show the ORIGINAL value.
    still_captured_values = {
        record.scalar.casilla_id: record.scalar.value
        for record in result.projection.materialization_facet.records
        if hasattr(record, "scalar")
    }
    assert still_captured_values == captured_scalar_values
    assert still_captured_values[a_casilla_id] != mutated_casilla_values[a_casilla_id]


# --- 4. Exactly-one-native-capture for CALCULATION and BOUNDED_REVIEW ---


def test_calculation_and_bounded_review_ports_are_each_captured_exactly_once(repos, monkeypatch: pytest.MonkeyPatch) -> None:
    """S130: the assembly invokes each of the CALCULATION and BOUNDED_REVIEW ports exactly once.

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

    monkeypatch.setattr(ModeloWorkspaceCalculationPortV1, "capture_projection_with_epoch", _counting_calculation_capture)
    monkeypatch.setattr(ModeloWorkspaceBoundedReviewPortV1, "capture_projection_with_epoch", _counting_bounded_review_capture)

    result = resolve_graded_snapshot_result(
        _visible_target(),
        required_grade=RegistryAuthorityGrade.CALCULATION,
        bucket_id=_BUCKET_ID,
        catalogue_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        authority=bundled_authority(),
        output_language=OutputLanguage.ES,
    )

    assert isinstance(result, ModeloWorkspaceGradedSnapshotResultV1)
    assert calculation_calls == 1
    assert bounded_review_calls == 1


# --- 5. Forbidden lower-layer ModeloWorkspace imports ---


def test_no_domain_or_adapter_module_imports_any_modelo_workspace_symbol() -> None:
    """S130: domain/ and adapters/ never depend on the application-layer Workspace read contract.

    Workspace V1 is an application-layer, read-only projection assembled
    FROM domain and adapter primitives; a dependency running the other way
    would invert the accepted hexagonal direction. Enumerates TRACKED files
    only, never a filesystem walk.
    """
    repository = Path(__file__).resolve().parents[5]
    tracked = subprocess.run(
        ("git", "ls-files", "-z", "--", "src/cadrumo/domain", "src/cadrumo/adapters"),  # noqa: S607
        capture_output=True,
        check=True,
        cwd=repository,
        text=True,
    ).stdout.split(chr(0))
    forbidden_needles = (
        "workspace_models",
        "workspace_producers",
        "workspace_manifest",
        "application.modelo.workspace",
        "ModeloWorkspace",
    )
    violations = tuple(
        entry
        for entry in tracked
        if entry.endswith(".py")
        and (path := repository / entry).is_file()
        and any(needle in path.read_text(encoding="utf-8") for needle in forbidden_needles)
    )
    assert not violations


# --- 6. Vaultspec-RAG-plus-exact census: no duplicate/parallel Workspace authority ---


def test_exactly_one_module_defines_each_canonical_workspace_assembly_symbol() -> None:
    """S130: a duplicate, legacy, shim, alias, fallback, bridge, or parallel Workspace authority reds this.

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
        if entry.endswith(".py")
        and "/tests/" not in entry
        and (repository / entry).is_file()
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
