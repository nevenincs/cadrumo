"""M210 inmobiliaria silent-zero advisory: end-to-end through the REAL calculate path.

Resolves deferral DFR-M210-INMOBILIARIA-E2E (feature ``modelo-verify-nonzero-guards``).
``test_verification_m210_advisory.py`` proves the
``modelo-210-2025-inmobiliaria-implica-base-imponible`` ADVISORY predicate against
hand-constructed ``casilla_values`` / ``text_values`` dicts fed directly to
``evaluate_verification_predicates``. This module proves the same advisory fires
through the REAL operator pipeline instead: :func:`calculate_modelo_revision` (real
registry formula engine, real persistence) followed by :func:`verify_modelo_revision`
(real Layer-2 predicate evaluation reading the PERSISTED
``CalculationRevision.input_values_by_casilla_id`` as ``text_values`` — see
``_verification_actions.py`` around the ``target.input_values_by_casilla_id`` comment).

Text-casilla input flow under test: ``text_casilla_inputs={"tipo_renta":
"inmobiliaria"}`` passed to :func:`calculate_modelo_revision` merges into
``CalculationRevision.input_values_by_casilla_id`` (see
``_calculation_actions.py``, ``{**replay_payloads.input_values_by_casilla_id,
**resolved_text_inputs}``), which the verify path's Layer-2 predicate gate then reads
back as ``text_values``.

The silent-zero scenario: for M210 2025 with ``tipo_renta = "inmobiliaria"``,
``base_imponible = valor_catastral * coeficiente_imputacion_inmobiliaria *
(dias_imputacion / days_in_filing_year)`` (``_evaluate_m210_resolve_base_imponible``
in ``cadrumo.domain.calculations.registry.formula_runtime``). The formula runtime
validates ``dias_imputacion`` to a strictly positive integer in
``[1, days_in_year]`` and the coefficient to equal one of the two
registry-authored LIRPF art. 85 rates — ``0.011`` (recent revision) or ``0.02``
(old/no revision), declared in
``src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/parameters/0003-m210-imputacion-inmobiliaria-2025.toml``
— so a zero ``dias_imputacion`` is refused outright rather than silently producing
a zero base. The genuine silent-zero this module exercises instead is a positive,
VALID ``dias_imputacion`` (1 day) applied against a small ``valor_catastral`` (EUR
100) so the imputed income rounds to ``0.00`` at the formula's declared
``money-2`` rounding: ``100 * 0.011 * (1/365) = EUR 0.00301...`` rounds to
``EUR 0.00`` — a real, positive one-day imputed-rent obligation that silently
vanishes through rounding, exactly the class of under-declaration the guard
exists to surface (per no-silent-under-declaration).

``rendimientos_integros`` (a MANUAL, ``required=true`` M210 casilla per the
registry, though unused by the inmobiliaria branch of the base-imponible formula)
is intentionally left unsupplied here so the revision resolves to
``granted_verificado_completo=False`` (a real, coexisting ``missing_required_casilla``
BLOCKING finding) — the post-grant workflow gate inside
:func:`verify_modelo_revision` runs the filing-draft builder only ``if granted``, and
that builder does not yet support ``data_type="text"`` casilla inputs like
``tipo_renta`` (a separate, pre-existing gap outside this module's scope). Leaving
this required casilla unsupplied keeps the test scoped to the inmobiliaria advisory
while still exercising the real calculate-then-verify pipeline end to end.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core import (
    CasillaId,
    Period,
    validated_casilla_id,
)
from ....core.resources import resources
from ....domain.deadlines import FiscalResidency, IVARegime, TaxpayerProfile
from ....domain.modelos import CalculationRevision, ModeloVerificationFindingKind, VerificationReport
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository
from ...tests import register_wizard_catalogue
from .._calculation_actions import calculate_modelo_revision
from .._verification_actions import verify_modelo_revision
from .._work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


__all__ = ["register_wizard_catalogue"]

_BUCKET_ID = "9a1c0e5e-2b1c-4f0e-8f7c-9d2f5b6a7c31"
_CLOCK = datetime(2026, 5, 21, 9, 0, 0, tzinfo=UTC)
_FILING_YEAR = 2025
_PERIOD_CODE = "EVENT-1"
_M210 = "210"

_TIPO_RENTA_CASILLA: CasillaId = validated_casilla_id("tipo_renta", surface="_TIPO_RENTA_CASILLA")
_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id("base_imponible", surface="_BASE_IMPONIBLE_CASILLA")

# The LIRPF art. 85 imputation-rate parameters declare exactly two valid
# coefficients for the inmobiliaria branch; 0.011 is the "recent revision"
# rate (m210-imputacion-rate-recent-revision-2025). Read from
# src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/parameters/0003-m210-imputacion-inmobiliaria-2025.toml.
_VALID_IMPUTACION_COEFFICIENT = Decimal("0.011")

# Grounds both the M210 inmobiliaria base-imponible formula and the
# ``modelo-210-2025-inmobiliaria-implica-base-imponible`` advisory predicate.
_INMOBILIARIA_LEGAL_REF = "trlirnr-rdleg-5-2004:art-13.1.h"


@contextmanager
def _secure_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        _seed_minimal_m210_profile(runtime.repository)
        yield


def _seed_minimal_m210_profile(objects: SecureObjectRepository) -> None:
    """Seed the minimal bucket profile that satisfies the M210 calculate/verify gates.

    M210 has no applicability seed rule in the registry
    (``derive_modelo_applicability`` returns ``INCOMPLETE``, which is not one of
    the blocking verdicts), so the local-work applicability gate never refuses
    this profile regardless of declared fiscal residency. The
    ``workflow_profile`` passed explicitly to :func:`verify_modelo_revision`
    (not this stored bucket profile) is what the representante-fiscal and
    inmobiliaria advisory predicates actually evaluate against.
    """
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="activities.description", value="Spanish-source rent"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    seed_test_profile_record(record)


def _irnr_gb_workflow_profile() -> TaxpayerProfile:
    """Non-resident IRNR profile with a fiscal representative (GB, non-EEA).

    Satisfies the ``m210-representante-fiscal-required`` BLOCKING predicate
    (TRLIRNR art. 10) so it does not fire alongside the inmobiliaria advisory
    under test.
    """
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
        country_of_fiscal_residence="GB",
        representante_fiscal_nif="12345678Z",
        representante_fiscal_nombre="Test Representative",
    )


def _repositories():
    return (
        WorkUnitCatalogueRepository(),
        CalculationRevisionCatalogueRepository(),
        BucketEventHistoryRepository(),
    )


def _calculate_and_verify_m210_inmobiliaria(
    *,
    valor_catastral: Decimal,
    dias_imputacion: Decimal,
    tmp_path: Path,
) -> tuple[CalculationRevision, VerificationReport]:
    """Run the REAL M210 calculate-then-verify pipeline with ``tipo_renta="inmobiliaria"``.

    Drives :func:`calculate_modelo_revision` directly (mirroring
    ``test_declaration_period_binding.py``) with a ``text_casilla_inputs`` entry
    for ``tipo_renta``, exercising the real registry formula engine rather than
    hand-constructed ``casilla_values``, then :func:`verify_modelo_revision` over
    the persisted revision. Both steps share one ``_secure_backend`` bucket
    session (mirroring ``test_modelo_200_first_year_cuota_e2e.py``'s
    ``secure_objects`` fixture pattern) rather than two separate
    ``isolated_runtime_profile`` provisioning passes over the same ``tmp_path``.
    """
    with _secure_backend(tmp_path):
        snapshot = resources().modelos.authority.snapshot(_M210, filing_year=_FILING_YEAR, period=_PERIOD_CODE)
        work_repo, calc_repo, event_repo = _repositories()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo=_M210,
            filing_year=_FILING_YEAR,
            period=Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_CLOCK,
        )
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={
                "valor_catastral": valor_catastral,
                "coeficiente_imputacion_inmobiliaria": _VALID_IMPUTACION_COEFFICIENT,
                "dias_imputacion": dias_imputacion,
            },
            text_casilla_inputs={_TIPO_RENTA_CASILLA: "inmobiliaria"},
            filing_period_date=date(_FILING_YEAR, 12, 31),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_CLOCK,
        )
        report = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="system",
            workflow_profile=_irnr_gb_workflow_profile(),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID),
            calculation_observation_repository=CalculationObservationRepository(),
            clock=_CLOCK,
        )
        return revision, report


def _inmobiliaria_advisory_findings(report: VerificationReport):
    return tuple(
        finding
        for finding in report.findings
        if finding.kind is ModeloVerificationFindingKind.ADVISORY and _INMOBILIARIA_LEGAL_REF in finding.legal_refs
    )


def test_m210_inmobiliaria_advisory_fires_through_real_calculate_and_verify(tmp_path: Path) -> None:
    """A real, valid, positive imputation that rounds to zero fires the advisory.

    ``valor_catastral=100`` EUR with the valid ``0.011`` coefficient and one
    valid imputation day (``100 * 0.011 * 1/365 = EUR 0.00301...``) rounds to
    ``EUR 0.00`` at the formula's declared ``money-2`` rounding — a real
    positive imputed-rent fact that silently vanishes through rounding.
    """
    revision, report = _calculate_and_verify_m210_inmobiliaria(
        valor_catastral=Decimal("100"),
        dias_imputacion=Decimal("1"),
        tmp_path=tmp_path,
    )

    # 1) PERSISTENCE: the text-casilla channel reached the persisted revision.
    assert revision.input_values_by_casilla_id[_TIPO_RENTA_CASILLA] == "inmobiliaria"
    assert revision.casilla_values[_BASE_IMPONIBLE_CASILLA] == Decimal("0.00")

    # 2) FIRES: the real verify gate's Layer-2 predicate evaluation, reading
    # the persisted ``input_values_by_casilla_id`` as ``text_values``, raises
    # the inmobiliaria silent-zero ADVISORY.
    advisories = _inmobiliaria_advisory_findings(report)
    assert len(advisories) == 1, (
        "expected exactly one modelo-210-2025-inmobiliaria-implica-base-imponible advisory finding; "
        f"got findings={report.findings!r}"
    )
    assert advisories[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert _INMOBILIARIA_LEGAL_REF in advisories[0].legal_refs


def test_m210_inmobiliaria_advisory_silent_when_base_computes_nonzero(tmp_path: Path) -> None:
    """A full-year imputation over a real cadastral value computes a nonzero base.

    ``valor_catastral=100000`` EUR with the valid ``0.011`` coefficient over
    the full filing year (``dias_imputacion=365``) computes
    ``EUR 1100.00`` — proving the previously-dead inmobiliaria base-imponible
    formula branch now COMPUTES through the real calculate path — and the
    advisory does not fire.
    """
    revision, report = _calculate_and_verify_m210_inmobiliaria(
        valor_catastral=Decimal("100000"),
        dias_imputacion=Decimal("365"),
        tmp_path=tmp_path,
    )

    assert revision.casilla_values[_BASE_IMPONIBLE_CASILLA] == Decimal("1100.00")
    assert revision.casilla_values[_BASE_IMPONIBLE_CASILLA] > Decimal("0")
    assert _inmobiliaria_advisory_findings(report) == ()
