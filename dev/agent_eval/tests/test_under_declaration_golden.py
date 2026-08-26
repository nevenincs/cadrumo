"""Under-declaration golden gate for the operator eval.

Guards against a missed under-declaration - the highest-severity, legal-soundness
failure class: an autonomous agent must not read a well-formed
``modelo work verify`` response as "safe to file" when a positive economic
input cascades to a zero dependent casilla with no offsetting reduction
declared: a positive resultado contable (140.000,00 EUR) with the fiscal-base
starting point left at manual zero must surface an ADVISORY finding, never a
silent zero-finding grant.

``DP200014:00552`` (base imponible) is COMPUTED from ``00501`` via the
``modelo-200-base-imponible`` formula
(``domain/calculations/registry/tests/test_modelo_200_base_determination.py::
test_positive_resultado_zero_correcciones_yields_nonzero_base``), so feeding ONLY
``00501`` no longer reproduces a silent zero at THAT link. The remaining, still-live
gap sits one link earlier: casilla ``00500`` (RESULTADO DE LA CUENTA DE PÉRDIDAS Y
GANANCIAS, after-tax) and casilla ``00501`` (resultado antes de IS, the fiscal-base
starting point) are BOTH free-standing manual inputs with no formula between them,
so an operator who enters a positive ``00500`` and leaves ``00501`` untouched still
cascades to a zero base and a zero cuota. The M200 2024 revision guards this EXACT
handoff with the ADVISORY predicate
``modelo-200-resultado-antes-impuesto-determinado-cuando-resultado-contable-positivo``
= ``implies_nonzero(["00500", "00501"])`` (declared in
``_data/registry/aeat/modelos/200/revisions/2024/verification_expectations/
0001-verification_predicates.toml``), confirmed live at HEAD by
``domain/calculations/registry/tests/test_modelo_200_registry.py::
test_modelo_200_carries_manual_handoff_under_declaration_advisory_predicates``.

This module dispatches the REAL CLI (``modelo work create`` -> ``calculate`` ->
``verify``) and proves the real dispatched response surfaces that ADVISORY finding -
not merely that the predicate exists in the registry.

No mocks: every seeded profile fact and every response value is what the real
registry engine plus the real CLI envelope serializer produced
(``aeat-quality-gates``, ``aeat-quality-gates``).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from cadrumo.domain.user_profile.loader import load_user_profile_schema
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from cadrumo.tests.cli_envelope import require_schema_envelope
from cadrumo.tests.cli_runner import invoke_cached_cli
from cadrumo.tests.modelo_cli import create_modelo_work_unit_via_cli
from cadrumo.tests.profile_capsule import seed_test_profile_record
from cadrumo.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile

from .. import UnderDeclarationScenario, check_under_declaration_scenario

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "0ac1e000-0000-4000-8000-0000000002bb"
_FILING_YEAR = 2024
_PERIOD = "0A"
_REVISION = "2024"
# legal_refs on the "modelo-200-resultado-antes-impuesto-determinado-cuando-
# resultado-contable-positivo" ADVISORY predicate (verification_predicates.toml).
_EXPECTED_LEGAL_REFS = ("ley-27-2014:art-10", "ley-27-2014:art-30")


@pytest.fixture
def runtime_profile(tmp_path: Any) -> Iterator[TestRuntimeProfile]:
    """Real-session backend (real KEK/DEK, real SQLite per active bucket)."""
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Under-declaration golden-eval test profile",
    ) as profile:
        yield profile


def _seed_legal_entity_profile(runtime_profile: TestRuntimeProfile) -> None:
    """Seed a resident sociedad (SL) legal-entity profile into the active bucket.

    Written directly (mirrors ``test_modelo_calculation_through_real_cli.py``'s
    ``_seed_legal_entity_profile``) to bypass ``config profile create``, which
    would re-provision the already-present bucket manifest. No ledger rows are
    seeded, so the M200 "refuses ledger-backed zero results without accounting-
    result input" guard
    (``application/modelo/tests/test_modelo_200_accounting_input_guard.py``)
    does not fire - this scenario reproduces the free-standing-manual-input
    under-declaration, not the ledger-aggregation one.
    """
    # Both identity fields come from the loaded schema rather than from
    # literals. The record pins each to exactly what the schema declares, so a
    # literal is a copy of the authority that goes stale the moment the schema
    # moves -- and reading them from one loaded object also keeps the pair
    # self-consistent, since two literals can drift into naming different
    # schemas.
    schema = load_user_profile_schema()
    record = UserProfileRecord(
        schema_id=schema.id,
        schema_version=schema.version,
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            UserProfileFact(path="identity.name", value="Under Declaration Operator"),
            UserProfileFact(path="identity.legal_name", value="Under Declaration Operator SL"),
            UserProfileFact(path="identity.tax_id", value="B12345674"),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value="500000.00"),
            UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
            UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value="100"),
            UserProfileFact(path="activities.description", value="software consultancy"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="provenance.source", value="manual_cli"),
        ),
    )
    seed_test_profile_record(
        record,
        root=runtime_profile.storage_root,
        label="Under-declaration golden-eval test profile",
    )


def _dispatch_m200_calculate_positive_resultado_zero_base(runtime_profile: TestRuntimeProfile) -> None:
    """Dispatch a REAL ``modelo.work.calculate`` for a positive-00500/zero-00501 draft.

    Casilla ``00500`` (RESULTADO DE LA CUENTA DE PÉRDIDAS Y GANANCIAS, after-tax)
    is set to a positive 140.000,00 EUR - the round-30 repro figure. Casilla
    ``00501`` (resultado antes de IS, the fiscal-base starting point) is
    deliberately left UNSET (defaults to manual zero), and no correcciones,
    reserva de capitalización, or compensación BIN casilla is supplied either -
    "no offsetting reduction is declared". The cascade this produces:
    ``00501 = 0`` -> ``00550 (base previa) = 0`` -> ``DP200014:00552 (base
    imponible) = 0`` -> ``DP200014:00562 (cuota íntegra) = 0``, exactly the
    round-30 silent-zero-tax shape on a EUR 140.000 profit company.

    The binding/relation set mirrors
    ``test_modelo_calculation_through_real_cli.py::
    test_modelo_200_micro_empresa_pyme_cuota_2024`` (a confirmed-passing real-CLI
    M200 dispatch), minus the base-chain casilla overrides that test supplies for
    ``00501``/correcciones/reserva/BIN - this scenario deliberately omits them.
    """
    _seed_legal_entity_profile(runtime_profile)
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="200",
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        revision=_REVISION,
    )

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "00500=140000.00",
            "--binding", "modelo-200-2024-profile-legal-entity-form=sl",
            "--binding", "modelo-200-2024-profile-new-entity-flag=0",
            "--binding", "modelo-200-2024-profile-incn-prior-12-months=500000",
            "--binding", "modelo-200-2024-profile-tributacion-estado-porcentaje=100",
            "--binding", "modelo-200-2024-bin-pendiente-ejercicios-anteriores=0",
            "--binding", "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores=0",
            "--binding", "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores=0",
            "--relation", "modelo-200-2024-rel-202-pagos-fraccionados=0",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    payload = require_schema_envelope(result.output)
    values = payload["casilla_values"]
    # Anti-tautology precondition: confirm the cascade actually reproduces the
    # silent-zero shape before asserting the verify-layer advisory over it - if
    # this precondition ever stops holding (e.g. a future formula change derives
    # 00501 from 00500), the scenario itself would be vacuous.
    assert values.get("00501") in (None, "0.00", "0"), (
        "precondition broken: 00501 must stay at manual zero (no formula derives "
        f"it from 00500 yet), got {values.get('00501')!r}"
    )
    assert values.get("DP200014:00552") in (None, "0.00", "0"), (
        f"precondition broken: base imponible DP200014:00552 must cascade to zero, got {values.get('DP200014:00552')!r}"
    )


def _dispatch_m200_verify() -> tuple[dict[str, Any], ...]:
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "verify",
            "--modelo", "200", "--year", str(_FILING_YEAR), "--period", _PERIOD,
        ],
    )  # fmt: skip
    payload = require_schema_envelope(result.output)
    return tuple(payload["findings"])


def test_m200_positive_resultado_zero_base_verify_surfaces_advisory(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """A real M200 verify over a positive-00500/zero-00501 draft is not silently clean.

    Dispatches the real CLI create -> calculate -> verify sequence and asserts the
    ``UnderDeclarationVerdict`` holds against the decoded JSON ``findings`` rows the
    operator actually reads: the response carries at least one finding (not a
    silent zero-finding grant), at least one of them is ADVISORY-kind, and it
    cites the exact legal grounding the registry predicate declares.
    """
    _dispatch_m200_calculate_positive_resultado_zero_base(runtime_profile)
    findings = _dispatch_m200_verify()

    scenario = UnderDeclarationScenario(
        name="m200-resultado-positivo-base-cero-advisory",
        command="modelo.work.verify",
        expected_legal_refs=_EXPECTED_LEGAL_REFS,
    )
    result = check_under_declaration_scenario(scenario, findings=findings)

    assert result.passed, result.failures
    assert result.not_silently_clean
    assert result.advisory_finding_present
    assert result.legal_refs_grounded
    assert findings, "real verify response must not be silently finding-free"
    advisory_kinds = {f["kind"] for f in findings if f["kind"] == "advisory"}
    assert advisory_kinds == {"advisory"}


def test_runner_rejects_a_clean_verify_claim_for_the_same_case(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Anti-tautology: claiming a clean (zero-finding) verify for this draft MUST fail.

    Reproduces the exact round-30 silent-under-declaration defect this dimension
    closes: a positive-input/zero-base draft whose verify response is asserted to
    carry zero findings (the pre-remediation behaviour: ``granted_verificado_completo =
    true, finding_count = 0`` on a EUR 140.000-profit company). Takes the SAME
    real dispatch context (the same draft the passing test above verifies) but
    hands the checker an EMPTY findings tuple, and proves
    ``check_under_declaration_scenario`` rejects it. Without this proof the
    dimension could pass vacuously regardless of what the CLI actually emitted.
    """
    _dispatch_m200_calculate_positive_resultado_zero_base(runtime_profile)

    scenario = UnderDeclarationScenario(
        name="m200-resultado-positivo-base-cero-advisory",
        command="modelo.work.verify",
        expected_legal_refs=_EXPECTED_LEGAL_REFS,
    )
    result = check_under_declaration_scenario(scenario, findings=())

    assert not result.passed
    assert not result.not_silently_clean
    assert not result.advisory_finding_present
    assert not result.legal_refs_grounded
    assert any("silent under-declaration grant" in failure for failure in result.failures)


def test_runner_rejects_a_response_with_the_advisory_stripped(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Anti-tautology: a response with only the ADVISORY finding removed MUST fail.

    Takes the SAME real dispatched findings and filters out every ``advisory``-
    kind row (keeping any other real finding present, e.g. a missing-required-
    casilla row) - reproducing a regression where the specific under-declaration
    guard silently stopped firing while the rest of the verify report stayed
    populated. Proves ``advisory_finding_present``/``legal_refs_grounded`` catch
    the absence of the SPECIFIC advisory, not just an empty findings list.
    """
    _dispatch_m200_calculate_positive_resultado_zero_base(runtime_profile)
    findings = _dispatch_m200_verify()
    assert any(f["kind"] == "advisory" for f in findings), "precondition: a real advisory must have fired"
    stripped = tuple(f for f in findings if f["kind"] != "advisory")

    scenario = UnderDeclarationScenario(
        name="m200-resultado-positivo-base-cero-advisory",
        command="modelo.work.verify",
        expected_legal_refs=_EXPECTED_LEGAL_REFS,
    )
    result = check_under_declaration_scenario(scenario, findings=stripped)

    assert not result.passed
    assert not result.advisory_finding_present
    assert not result.legal_refs_grounded
    assert any("no ADVISORY-kind finding" in failure for failure in result.failures)


def test_runner_rejects_a_mismatched_legal_grounding() -> None:
    """Anti-tautology: an advisory finding with the WRONG legal grounding MUST fail.

    A synthetic finding carries ``kind == "advisory"`` (so
    ``advisory_finding_present`` alone would pass) but cites unrelated
    ``legal_refs`` - proving ``legal_refs_grounded`` is a real containment check
    against the scenario's declared grounding, not a vacuous "any advisory will
    do" pass.
    """
    scenario = UnderDeclarationScenario(
        name="m200-resultado-positivo-base-cero-advisory",
        command="modelo.work.verify",
        expected_legal_refs=_EXPECTED_LEGAL_REFS,
    )
    mismatched_finding = {
        "kind": "advisory",
        "severity": "warning",
        "message": "unrelated advisory",
        "legal_refs": ["ley-27-2014:art-26"],
    }
    result = check_under_declaration_scenario(scenario, findings=(mismatched_finding,))

    assert not result.passed
    assert result.not_silently_clean
    assert result.advisory_finding_present
    assert not result.legal_refs_grounded
    assert any("not the one this scenario declares" in failure for failure in result.failures)
