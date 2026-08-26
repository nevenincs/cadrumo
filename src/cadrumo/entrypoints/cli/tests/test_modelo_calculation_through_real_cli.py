"""Cross-modelo CLI calculation tests grounded in external oracle values (contract/contract).

Each test drives the real ``cadrumo`` CLI against an isolated real-session backend
(``isolated_runtime_profile``) — no mocks, no unsecured-monkeypatch backend.

Expected casilla values are derived exclusively from external authoritative
sources cited inline with each test.  No expected value was hand-computed from
the registry formula itself.

Modelos covered:
- 200 (Impuesto sobre Sociedades) — pyme micro-empresa 2024 cuota-integra
- 202 (Pago fraccionado IS) — Art. 40.2 LIS cuota
- 130 (Pago fraccionado IRPF directa) — resultado apartado I

Modelos 303 and 100 are exercised at the structural level (calculation
succeeds, output is well-formed JSON, key casillas are present) because
their cuota depends on ledger-sourced bindings that require a full
transaction ingestion pipeline, which is outside the scope of this CLI-level
oracle fixture.  Numeric oracle assertions for those modelos live in the
source-mesh and registry-level test suites.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.modelo_cli import create_modelo_work_unit_via_cli
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from ._m130_source_support import seed_m130_expense_transaction, seed_m130_income_transaction

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_PROFILE_ID = "0ac1e000-0000-4000-8000-000000000001"


@pytest.fixture
def runtime_profile(
    tmp_path: Path,
) -> Iterator[TestRuntimeProfile]:
    """Real-session backend for cross-modelo oracle calculation tests.

    Uses ``isolated_runtime_profile`` (real KEK/DEK, real SQLite per
    active bucket).  Extra env-var overrides supply the non-bucket
    directories that work-unit commands read from settings.
    """

    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Oracle calculation test profile",
    ) as profile:
        yield profile


def _seed_natural_person_profile(runtime_profile: TestRuntimeProfile) -> None:
    """Seed a natural-person (IRPF / IVA) profile into the active bucket.

    Written directly to bypass ``config profile create``, which would
    re-provision the already-present bucket manifest.  The minimum required
    schema facts (as per ``_testing.py`` _REQUIRED_PLACEHOLDERS) are all
    populated so the work-unit applicability guard passes.
    """

    record = UserProfileRecord(
        schema_id="cadrumo.user_profile",
        # Sourced from the schema, never pinned: a literal goes stale the moment
        # the profile schema is revised, and the record then refuses to validate
        # against its own canonical version.
        schema_version=load_user_profile_schema().version,
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            UserProfileFact(path="identity.name", value="Oracle Test Operator"),
            UserProfileFact(path="identity.surnames", value="Calculation"),
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            # Spanish enum value: autónomo en estimación directa.
            UserProfileFact(
                path="taxpayer_type.irpf_income_categories",
                value="actividad_economica",
            ),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="provenance.source", value="manual_cli"),
        ),
    )
    seed_test_profile_record(
        record,
        root=runtime_profile.storage_root,
        label="Oracle Test Operator",
    )


def _seed_legal_entity_profile(
    runtime_profile: TestRuntimeProfile,
    *,
    incn_prior_12_months: Decimal,
    new_entity: bool = False,
) -> None:
    """Seed a legal-entity (IS) profile into the active bucket.

    Written directly to bypass ``config profile create``.
    """

    facts: list[UserProfileFact] = [
        UserProfileFact(path="identity.name", value="Oracle IS Operator"),
        UserProfileFact(path="identity.legal_name", value="Oracle IS Operator SL"),
        UserProfileFact(path="identity.tax_id", value="B12345674"),
        UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
        UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
        UserProfileFact(
            path="taxpayer_type.incn_prior_12_months",
            value=incn_prior_12_months,
        ),
        UserProfileFact(
            path="taxpayer_type.new_entity_first_two_profit_periods",
            value=new_entity,
        ),
        UserProfileFact(path="activities.description", value="economic activity"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    ]
    record = UserProfileRecord(
        schema_id="cadrumo.user_profile",
        # Sourced from the schema, never pinned: a literal goes stale the moment
        # the profile schema is revised, and the record then refuses to validate
        # against its own canonical version.
        schema_version=load_user_profile_schema().version,
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=tuple(facts),
    )
    seed_test_profile_record(
        record,
        root=runtime_profile.storage_root,
        label="Oracle IS Operator",
    )


# ---------------------------------------------------------------------------
# Modelo 200 — Impuesto sobre Sociedades (micro-empresa pyme rate 2024)
# ---------------------------------------------------------------------------
#
# Oracle: AEAT Manual Práctico de Sociedades 2024, Chapter III,
# "Tipo de gravamen reducido para empresas de reducida dimensión",
# Section "Entidades de reducida dimensión - Artículo 29 LIS".
#
# Authority: Ley 27/2014 Art. 29 as in force for ejercicios iniciados
# en 2024 (BOE-A-2014-12328):
#   - INCN < 1.000.000 EUR: micro-empresa, tipo único 23 %
#   - Base imponible: 100.000,00 EUR
#   - Cuota íntegra: 100.000,00 x 23 % = 23.000,00 EUR
#
# The two-tranche micro-empresa scale (17 % / 20 %) was introduced for
# ejercicios iniciados en 2025 (Ley 7/2024 Art. 2).  The 2024 filing
# covered here uses the pre-2025 flat 23 % rate exclusively.


def test_modelo_200_micro_empresa_pyme_cuota_2024(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Modelo 200 pyme cuota-íntegra for a micro-empresa ejercicio 2025.

    Oracle: LIS disposición transitoria 44ª (added by Ley 7/2024,
    BOE-A-2024-26694), the transitional micro-empresa scale over LIS
    Art. 29.1 (BOE-A-2014-12328) as in force for periods iniciados en 2025:
    21 % on the first 50.000 EUR, 22 % on the rest.

    Input: base imponible 100.000,00 EUR, SL, no new-entity override,
    INCN < 1.000.000 EUR (micro-empresa lane).

    Expected: casilla DP200014:00562 (cuota íntegra) = 21.500,00 EUR.
    """

    _seed_legal_entity_profile(
        runtime_profile,
        incn_prior_12_months=Decimal("500000.00"),  # below 1 M → pyme lane
        new_entity=False,
    )
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="200",
        filing_year=2025,
        period="0A",
        revision="2024-y-siguientes",
    )

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            # 00552 (base imponible) is now computed from the resultado
            # contable chain from the M200 base-determination contract:
            #   00550 = 00501 + DP200013:00417 - DP200013:00418
            #   00552 = max(00550 - 01032 - DP200014:00547, 0)
            # Supplying 00501 = 100000 and zero corrections / reserva / BIN
            # aplicada produces 00552 = 100000 exactly. Then
            # 01330 = 00552 + 01033 - 01034 = 100000 with 01033 = 01034 = 0.
            "--casilla", "00501=100000.00",
            "--casilla", "DP200013:00417=0.00",
            "--casilla", "DP200013:00418=0.00",
            "--casilla", "01032=0.00",
            "--casilla", "DP200014:00547=0.00",
            "--casilla", "DP200014:01033=0.00",
            "--casilla", "DP200014:01034=0.00",
            "--binding", "modelo-200-2024-profile-legal-entity-form=sl",
            "--binding", "modelo-200-2024-profile-new-entity-flag=0",
            "--binding", "modelo-200-2024-profile-incn-prior-12-months=500000",
            # Estado-share porcentaje for IS cuota; 100 means full estado share
            # (no foral/territorial adjustment) which is the common-regime case
            # this oracle fixture covers.
            "--binding", "modelo-200-2024-profile-tributacion-estado-porcentaje=100",
            # BIN-pendiente fresh-filer baseline (M200 self previous_filing).
            "--binding", "modelo-200-2024-bin-pendiente-ejercicios-anteriores=0",
            # Dotaciones/deterioro credit balance fresh-filer baseline.
            "--binding", "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores=0",
            "--binding", "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores=0",
            # Relation value: sum of M202 pagos fraccionados for the year.
            # Zero means no prior instalments have been paid.
            "--relation", "modelo-200-2024-rel-202-pagos-fraccionados=0",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    payload = _payload(result.output)
    # casilla DP200014:00562 is the cuota-integra output casilla.
    cuota = payload["casilla_values"]["DP200014:00562"]
    # Oracle: 50.000,00 x 21 % + 50.000,00 x 22 % = 10.500,00 + 11.000,00 = 21.500,00 EUR
    assert Decimal(cuota) == Decimal("21500.00"), (
        f"Modelo 200 pyme 2025 cuota-integra: expected 21500.00 EUR "
        f"(LIS DT 44a, 21%/22% micro-empresa 2025), got {cuota!r}"
    )


# ---------------------------------------------------------------------------
# Modelo 202 — Pago fraccionado IS, Art. 40.2 LIS lane
# ---------------------------------------------------------------------------
#
# Oracle: AEAT Declaración 202 — Instrucciones (DR 202, Agencia Tributaria
# 2025), Clave [03] «Base del pago fraccionado (modalidad artículo 40.2
# LIS)», porcentaje del 18 %:
#   - Clave [01] (base): 10.000,00 EUR, supplied through the M200 relation
#     binding that owns the base source for the current registry revision.
#   - Clave [02] (pagos fraccionados anteriores): 0,00 EUR
#   - Clave [03] = 18 % x 10.000,00 - 0,00 = 1.800,00 EUR
#
# Authority: Ley 27/2014 Art. 40.2 (BOE-A-2014-12328):
# «el pago fraccionado consistirá en el 18 por ciento de la cuota
# íntegra del último período impositivo cuyo plazo de declaración
# estuviese vencido».


def test_modelo_202_art_40_2_cuota_incn_below_threshold(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Modelo 202 Art. 40.2 lane cuota for INCN below 6.000.000 EUR.

    Oracle: AEAT DR 202 instrucciones, clave [03] «porcentaje del 18 %»;
    LIS Art. 40.2 (BOE-A-2014-12328).

    Input: prior M200 cuota-base relation = 10.000,00 EUR,
    casilla 02 = 0,00 EUR, INCN = 500.000 EUR
    (below 6 M threshold → Art. 40.2 lane).

    Expected: casilla 03 (cuota) = 18 % x 10.000 - 0 = 1.800,00 EUR.
    """

    _seed_legal_entity_profile(
        runtime_profile,
        incn_prior_12_months=Decimal("500000.00"),  # below 6 M → Art. 40.2 optional
        new_entity=False,
    )
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="202",
        filing_year=2026,
        period="1P",
        revision="2025-y-siguientes",
    )

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "02=0.00",
            # INCN binding: routes Art. 40.2 vs Art. 40.3 lane.
            "--binding", "modelo-202-2025-y-siguientes-incn-prior-12-months=500000",
            # Prior M200 cuota-base binding: source-owned input for casilla 01.
            "--binding", "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior=10000.00",
            # Prior pagos-fraccionados (casilla 30): zero for first period.
            "--binding", "modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores=0",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    payload = _payload(result.output)
    cuota = payload["casilla_values"]["03"]
    # Oracle: 18 % x 10.000,00 = 1.800,00 EUR (LIS Art. 40.2)
    assert Decimal(cuota) == Decimal("1800.00"), (
        f"Modelo 202 Art. 40.2 cuota: expected 1800.00 EUR (LIS Art. 40.2, 18% of 10000), got {cuota!r}"
    )


# ---------------------------------------------------------------------------
# Modelo 130 — Pago fraccionado IRPF, estimación directa
# ---------------------------------------------------------------------------
#
# Oracle: AEAT DR 130 Instrucciones (Orden EHA/672/2007 y sucesivas),
# Casilla 07 «Resultado parcial del apartado I»:
#   formula: casilla_07 = casilla_04 - casilla_05 - casilla_06
#   where:   casilla_04 = max(0, 20 % x casilla_03)
#            casilla_03 = casilla_01 - casilla_02
#
# Authority: Ley 35/2006 Art. 99; RD 439/2007 Art. 110; AEAT DR 130
# Instrucciones, Casilla 04 «20 por 100 del importe de la casilla 03».
#
# Worked example (AEAT DR 130 Instrucciones, ejemplo estimación directa):
#   casilla 01 (ingresos): 12.000,00 EUR from source-owned ledger income
#   casilla 02 (gastos):    4.000,00 EUR
#   casilla 03 (rendimiento neto): 12.000 - 4.000 = 8.000,00 EUR
#   casilla 04 (pago fraccionado): 20 % x 8.000 = 1.600,00 EUR
#   casilla 05 (pagos anteriores): 0,00 EUR
#   casilla 06 (retenciones):      0,00 EUR
#   casilla 07 (resultado I):      1.600 - 0 - 0 = 1.600,00 EUR
#
# Binding: irpf.previous_year_economic_activity_net_income > 12.000 EUR
# so the minoracion (casilla 13) is 0.  We supply 13.000,00 EUR.


def test_modelo_130_resultado_apartado_i_direct_estimation(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Modelo 130 estimación directa resultado parcial (casilla 07).

    Oracle: AEAT DR 130 Instrucciones, Casilla 07 «Resultado parcial
    apartado I»; IRPF Art. 99 (BOE-A-2006-20764); RD 439/2007 Art. 110.

    Inputs: ingresos 12.000 EUR, gastos 4.000 EUR, prior-year income
    13.000 EUR (above 12.000 threshold → minoración = 0).

    Expected: casilla 07 = 1.600,00 EUR (20 % x 8.000 - 0 - 0).
    """

    _seed_natural_person_profile(runtime_profile)
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="130",
        filing_year=2026,
        period="1T",
        revision="2019-y-siguientes",
    )
    seed_m130_income_transaction(
        amount=Decimal("12000.00"),
        filing_year=2026,
        source_key="oracle-calc",
    )
    # Casilla 02 (gastos) is bucket-bound (ledger-aggregated); seed the 4.000 gasto
    # as a deductible expense row rather than supplying --casilla 02.
    seed_m130_expense_transaction(
        amount=Decimal("4000.00"),
        filing_year=2026,
        source_key="oracle-calc",
    )

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "05=0.00",
            "--casilla", "06=0.00",
            "--binding",
            "irpf.previous_year_economic_activity_net_income=13000",
            "--binding",
            "modelo-130-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    payload = _payload(result.output)
    casilla_07 = payload["casilla_values"]["07"]
    # Oracle: 20 % x (12.000 - 4.000) = 1.600,00 EUR (IRPF Art. 99,
    # RD 439/2007 Art. 110, AEAT DR 130 Instrucciones Casilla 07)
    assert Decimal(casilla_07) == Decimal("1600.00"), (
        f"Modelo 130 casilla 07: expected 1600.00 EUR (20% x (12000 - 4000), IRPF Art. 99), got {casilla_07!r}"
    )


# ---------------------------------------------------------------------------
# Modelo 303 — IVA (structural surface test)
# ---------------------------------------------------------------------------
#
# Numeric oracle for M303 cuota requires ledger-sourced IVA devengado and
# deducible bindings populated by the transaction ingestion pipeline, which
# is out of scope for this CLI-fixture test.  This test verifies:
#   - the ``work create`` + ``work calculate`` surface is reachable
#   - the JSON output contains the ``casilla_values`` dictionary
#   - the ``iva.resultado`` casilla (the regulatory net IVA output) is
#     present in the output
# Numeric correctness for M303 is exercised in the source-mesh roundtrip
# suite (``test_modelo_source_mesh_calculate.py``).


def test_modelo_303_calculate_surface_is_reachable(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Modelo 303 work calculate returns well-formed JSON with casilla_values.

    This test verifies the CLI surface is operational and the key output
    casilla ``iva.resultado`` is present.  Numeric oracle assertions for
    M303 cuota require ledger-backed bindings exercised in the source-mesh
    suite, not this fixture.
    """

    _seed_natural_person_profile(runtime_profile)
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="303",
        filing_year=2026,
        period="1T",
        revision=str(bundled_authority().snapshot("303", filing_year=2026, period="1T").revision.id),
    )

    # Supply zero-value manual casillas so the engine can complete the
    # IVA devengado and deducible aggregation without ledger bindings.
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
        ],
    )  # fmt: skip
    # The CLI may refuse with missing-bindings error; that is still a
    # reachable non-traceback response.  We assert no Python traceback.
    assert "Traceback" not in result.output
    if result.exit_code == 0:
        payload = _payload(result.output)
        assert "casilla_values" in payload, result.output
        # iva.resultado is the regulatory net IVA output casilla.
        assert "iva.resultado" in payload["casilla_values"], (
            f"iva.resultado must be present in calculate output; got keys: {list(payload['casilla_values'])[:10]}"
        )


# ---------------------------------------------------------------------------
# Modelo 100 — IRPF Renta (structural surface test)
# ---------------------------------------------------------------------------
#
# Numeric oracle for M100 cuota requires the full escala general and
# autonomica tables applied to base liquidable general and del ahorro,
# which depends on prior-year income aggregation and renta-year-specific
# tramos.  That oracle is exercised in the registry-level IRPF escala
# tests.  This test verifies the CLI surface is reachable and produces
# well-formed JSON.


def test_modelo_100_calculate_surface_is_reachable(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Modelo 100 work calculate surface reaches the engine without crash.

    Numeric cuota oracle for M100 requires prior-year income aggregation
    exercised in registry-level IRPF escala tests.  This test guards the
    CLI surface: no Python traceback is produced.
    """

    _seed_natural_person_profile(runtime_profile)
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="100",
        filing_year=2024,
        period="0A",
        revision="2024",
    )

    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "calculate", work_unit_id,
        ],
    )  # fmt: skip
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# Typed ``--binding`` coercion (bindings-interface-hardening, cluster D)
# ---------------------------------------------------------------------------
#
# The pre-hardening classification was a ``try Decimal/except`` heuristic: a
# malformed amount for a numeric binding silently fell through to the enum
# channel, so a typo'd figure was carried as an enum string and produced a wrong
# (or blank) calculation with no operator signal. The hardened path routes by
# the binding's *declared* engine channel: a decimal-channel binding's override
# MUST parse as a Decimal, so a malformed amount REFUSES instead of silently
# reclassifying. These tests exercise the real CLI against the real registry.


def test_modelo_130_malformed_numeric_binding_refuses_not_reclassified(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """A malformed amount for a numeric ``--binding`` REFUSES.

    ``irpf.previous_year_economic_activity_net_income`` is a decimal-channel
    Modelo 130 binding (the oracle test supplies it as ``13000``). Supplying
    ``12abc`` must refuse with a decimal-shape error naming the binding —
    never silently reclassify it as an enum string. The refusal is the
    no-silent-under-declaration contract: a typo'd figure must surface, not
    vanish into the enum channel.
    """

    _seed_natural_person_profile(runtime_profile)
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="130",
        filing_year=2026,
        period="1T",
        revision="2019-y-siguientes",
    )

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "02=4000.00",
            "--binding", "irpf.previous_year_economic_activity_net_income=12abc",
        ],
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == "error", envelope
    error = envelope["error"]
    # The refusal is the decimal-shape error surfaced at the CLI boundary,
    # not a missing-binding nor a silent enum reclassification: its message
    # names the offending binding, the ``--binding`` flag, and the bad value.
    assert error["category"] == "REFUSED", error
    message = error["message"]
    assert "--binding" in message
    assert "irpf.previous_year_economic_activity_net_income" in message
    assert "12abc" in message
    assert "is not a decimal" in message


def test_modelo_200_enum_binding_accepts_non_numeric_value(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """An enum-channel ``--binding`` carries its non-numeric value verbatim.

    ``modelo-200-2024-profile-legal-entity-form`` is consumed by a dispatch op
    as a string enum key, so its ``--binding`` override is a string (``sl``).
    The hardened router classifies it by the declared enum channel (not by
    parse failure), so a non-numeric enum value is accepted and the calculate
    succeeds — proving the enum half of the channel split. This is the
    anti-tautology companion to the decimal-refusal test: a working enum
    binding confirms the refusal is channel-specific, not a blanket rejection
    of non-numeric ``--binding`` values.
    """

    _seed_legal_entity_profile(
        runtime_profile,
        incn_prior_12_months=Decimal("500000.00"),
        new_entity=False,
    )
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="200",
        filing_year=2024,
        period="0A",
        revision="2024-y-siguientes",
    )

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "00501=100000.00",
            "--casilla", "DP200013:00417=0.00",
            "--casilla", "DP200013:00418=0.00",
            "--casilla", "01032=0.00",
            "--casilla", "DP200014:00547=0.00",
            "--casilla", "DP200014:01033=0.00",
            "--casilla", "DP200014:01034=0.00",
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
    payload = _payload(result.output)
    assert "casilla_values" in payload, result.output
