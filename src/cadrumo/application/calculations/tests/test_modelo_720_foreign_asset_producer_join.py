"""The M720 foreign-asset PRODUCER writes the row shape the evidence projection joins on.

The re-declaration advisory reads its independent current-year valuation
evidence from ``CalculationRevision.row_binding_values``, joining the two
``foreign_asset`` row bindings it discovers from the registry revision by their
selector ``row_field``. Those rows are written by the enrolled
:class:`~application.aggregation.ForeignAssetsAggregationSourceResolver` on the
bucket-aggregation calculate path.

That single link had only ever been exercised from the CONSUMER side: the
existing end-to-end coverage hand-constructs ``row_binding_values`` and passes
them straight into the calculate call, which proves the join and leaves the
producer untested. A shape mismatch between the two — a different row-index key
type, a different binding id, a value the class lookup cannot resolve — would
yield an EMPTY join, no finding, and a result indistinguishable from a taxpayer
who genuinely has nothing to re-declare. The guard would be silent while its
presence read as coverage.

This module closes that gap from the producer side. It supplies typed
:class:`~application.aggregation.ForeignAssetIngestObservation` rows to the real
bucket-aggregation calculate path, lets the enrolled resolver write the row
bindings, and asserts the evidence projection joins them non-empty at the
per-bloque totals the observations imply — then follows the same revision into
the real verify gate.

Scenario, grounded in RD 1065/2007 arts. 42-bis.5 / 42-ter.5 (EUR 20,000
re-declaration delta over the last declared baseline, EUR 50,000 initial floor
of Orden HAP/72/2013 art. 2.1):

- Year N declares cuentas EUR 60,000 and valores EUR 55,000, persisted as a real
  observation and carried by the ``previous_filing`` baseline bindings.
- Year N+1 holds cuentas EUR 85,000 (+25,000 > delta) and valores EUR 65,000
  (+10,000 <= delta) as foreign-asset observations, and the operator omits the
  cuentas valuation from the declaration.

See Also:
    :func:`~application.calculations.modelo_720_evidence_observation`
        The consumer whose join shape this module measures from the producer side.
    :class:`~application.aggregation.ForeignAssetsAggregationSourceResolver`
        The enrolled producer under test.
    :mod:`~application.calculations.tests.test_modelo_720_prior_year_baseline_fidelity`
        Prior-year baseline continuity for the same scenario.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...tests import register_wizard_catalogue

__all__ = ["register_wizard_catalogue"]

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import BindingSourceKind, CasillaId, Modelo, Period, validated_casilla_id
from ....core.aggregation import ForeignAssetClass
from ....core.resources import resources
from ....domain.calculations.registry import ModeloRevision, selector_as_dict
from ....domain.deadlines import FiscalResidency, IVARegime, TaxpayerProfile
from ....domain.modelos import CalculationRevision, VerificationReport
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import ForeignAssetIngestObservation
from ...modelo import (
    calculate_modelo_revision_from_bucket_aggregation,
    create_work_unit,
    verify_modelo_revision,
)
from .._foreign_asset_redeclaration import modelo_720_evidence_observation
from .._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "4c7f1b90-6d2e-4a13-9f58-2b7c8e0a1d64"
_CLOCK_N = datetime(2024, 3, 15, 9, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(2025, 3, 15, 9, 0, 0, tzinfo=UTC)
_YEAR_N = 2023
_YEAR_N_PLUS_1 = 2024
_PERIOD = "0A"

_CUENTAS_VALORACION: CasillaId = validated_casilla_id("cuentas.valoracion", surface="_CUENTAS_VALORACION")
_VALORES_VALORACION: CasillaId = validated_casilla_id("valores.valoracion", surface="_VALORES_VALORACION")
_INMUEBLES_VALORACION: CasillaId = validated_casilla_id("inmuebles.valoracion", surface="_INMUEBLES_VALORACION")

_CUENTAS_N = Decimal("60000.00")
_VALORES_N = Decimal("55000.00")
_INMUEBLES_N = Decimal("0.00")

_CUENTAS_N1 = Decimal("85000.00")
_VALORES_N1 = Decimal("65000.00")

#: The two ``row_field`` selectors the evidence projection joins on. Named here
#: independently of the production constants so a rename on one side is a
#: divergence this module can see rather than one it silently follows.
_ASSET_CLASS_ROW_FIELD = "asset_class_code"
_VALUATION_ROW_FIELD = "valuation_amount"

_ADVISORY_LOCALE_KEY = "application.modelo.findings.foreign_asset_redeclaration"


@contextmanager
def _secure_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET_ID,
                facts=(
                    UserProfileFact(path="identity.tax_id", value="12345678Z"),
                    UserProfileFact(path="activities.description", value="Foreign asset holder"),
                    UserProfileFact(path="iva.regime", value="GENERAL"),
                    # The filing-grade readiness gate refuses a profile whose
                    # tax territory was never declared, and refuses it BEFORE
                    # the producer runs -- so without this the module measured
                    # a profile refusal rather than the join it exists to
                    # observe. Declared common-regime: the foral territories
                    # are explicitly unsupported, and a Modelo 720 filer under
                    # one of them is a different product question than the
                    # producer-to-projection shape under test here.
                    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                    # The IVA block below is likewise a readiness precondition
                    # rather than a fact this measurement turns on. It became
                    # mandatory after this module was written, so the profile
                    # here predates it and the gate refused before the producer
                    # ran. Declared as an ordinary general-regime filer in no
                    # special regime, which is the population a plain foreign
                    # asset holder belongs to.
                    UserProfileFact(path="iva.m303_regime_composition", value="general"),
                    UserProfileFact(path="iva.redeme_enrolled", value=False),
                    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                    UserProfileFact(
                        path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                        value=False,
                    ),
                ),
                created_at=_CLOCK_N,
                updated_at=_CLOCK_N,
            ),
        )
        yield


def _resident_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        iva_regime=IVARegime.GENERAL,
        fiscal_residency=FiscalResidency.RESIDENT_IRPF,
    )


def _foreign_asset_observations() -> tuple[ForeignAssetIngestObservation, ...]:
    """Year N+1 per-asset holdings, as the operator would supply them to the mesh.

    ``purchase_invoice_evidence`` carries an external identifier rather than a
    ledger transaction identity, so the rows exercise the producer without
    dragging a ledger fixture into a foreign-asset measurement.
    """
    return (
        ForeignAssetIngestObservation(
            source_kind=BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
            source_object_id="evidence-cuentas-lu-0001",
            asset_class=ForeignAssetClass.ACCOUNT,
            asset_external_id="LU280019400644750000",
            country="LU",
            issuer_or_institution="Banque Internationale a Luxembourg",
            valuation_eur=_CUENTAS_N1,
            acquisition_date="2019-04-01",
            held_at_year_end=True,
        ),
        ForeignAssetIngestObservation(
            source_kind=BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
            source_object_id="evidence-valores-de-0001",
            asset_class=ForeignAssetClass.SECURITY,
            asset_external_id="DE0007164600",
            country="DE",
            issuer_or_institution="SAP SE",
            valuation_eur=_VALORES_N1,
            acquisition_date="2020-09-15",
            held_at_year_end=True,
        ),
    )


def _row_binding_id(modelo_revision: ModeloRevision, *, row_field: str) -> str:
    """Discover a ``foreign_asset`` row binding id by selector, as the consumer does."""
    for binding in modelo_revision.bindings:
        if binding.source != BindingSourceKind.FOREIGN_ASSET:
            continue
        if selector_as_dict(binding).get("row_field") == row_field:
            return binding.id
    raise AssertionError(
        f"Modelo 720 declares no foreign_asset binding with row_field {row_field!r}; "
        "the evidence projection discovers its join keys by exactly this selector, "
        "so its absence would empty the join silently",
    )


def _calculate_through_the_mesh(
    *,
    tmp_path: Path,
    observations: tuple[ForeignAssetIngestObservation, ...],
    declare_cuentas: bool = False,
) -> tuple[CalculationRevision, ModeloRevision, VerificationReport]:
    """Run the real year-N+1 M720 bucket-aggregation calculate, then the real verify.

    The foreign-asset rows are produced by the enrolled resolver from
    *observations*; nothing in this helper hand-writes ``row_binding_values``.
    """
    with _secure_backend(tmp_path):
        observation_repository = CalculationObservationRepository()
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                registry_grounded_modelo_observation(
                    modelo=Modelo.M720.value,
                    filing_year=_YEAR_N,
                    period=_PERIOD,
                    casilla_values={
                        _CUENTAS_VALORACION: _CUENTAS_N,
                        _VALORES_VALORACION: _VALORES_N,
                        _INMUEBLES_VALORACION: _INMUEBLES_N,
                    },
                ),
                source_kind="app_filing",
                captured_at=_CLOCK_N,
            )
        )

        snapshot = resources().modelos.authority.snapshot(
            Modelo.M720.value,
            filing_year=_YEAR_N_PLUS_1,
            period=_PERIOD,
        )
        work_repository = WorkUnitCatalogueRepository()
        calculation_repository = CalculationRevisionCatalogueRepository()
        event_repository = BucketEventHistoryRepository()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo=Modelo.M720.value,
            filing_year=_YEAR_N_PLUS_1,
            period=Period.from_year_and_code(_YEAR_N_PLUS_1, _PERIOD),
            revision_id=snapshot.revision.id,
            repository=work_repository,
            clock=_CLOCK_N_PLUS_1,
        )

        casilla_inputs: dict[CasillaId, Decimal] = {
            _VALORES_VALORACION: _VALORES_N1,
            _INMUEBLES_VALORACION: _INMUEBLES_N,
        }
        if declare_cuentas:
            casilla_inputs[_CUENTAS_VALORACION] = _CUENTAS_N1

        revision = calculate_modelo_revision_from_bucket_aggregation(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs=casilla_inputs,
            foreign_asset_observations=observations,
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=event_repository,
            clock=_CLOCK_N_PLUS_1,
        )
        report = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="system",
            workflow_profile=_resident_profile(),
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            calculation_observation_repository=observation_repository,
            clock=_CLOCK_N_PLUS_1,
        )
        return revision, snapshot.revision, report


def test_the_enrolled_resolver_writes_row_bindings_keyed_as_the_evidence_join_reads_them(
    tmp_path: Path,
) -> None:
    """A real producer run populates both joined row bindings under a shared row index.

    This is the link the chain never exercised: the resolver writes, the
    projection reads, and nothing in between is hand-built. A divergence in the
    binding id, the row-index key, or the persisted value form empties the join
    without raising, so each half is asserted explicitly.
    """
    revision, modelo_revision, _report = _calculate_through_the_mesh(
        tmp_path=tmp_path,
        observations=_foreign_asset_observations(),
    )

    class_binding = _row_binding_id(modelo_revision, row_field=_ASSET_CLASS_ROW_FIELD)
    valuation_binding = _row_binding_id(modelo_revision, row_field=_VALUATION_ROW_FIELD)

    class_rows = revision.row_binding_values.get(class_binding, {})
    valuation_rows = revision.row_binding_values.get(valuation_binding, {})

    assert class_rows, (
        f"the foreign-asset resolver wrote no rows for {class_binding!r}; the evidence "
        "projection would join empty and the re-declaration guard would stay silent"
    )
    assert valuation_rows, (
        f"the foreign-asset resolver wrote no rows for {valuation_binding!r}; the evidence "
        "projection would join empty and the re-declaration guard would stay silent"
    )
    assert set(class_rows) == set(valuation_rows), (
        "the class and valuation row bindings must share their row-index key set; the "
        "projection pairs them by that index and drops any row present on one side only"
    )
    assert sorted(class_rows.values()) == ["C", "V"], (
        "the persisted asset-class claves must be the official Modelo 720 codes the "
        f"projection resolves back to a ForeignAssetClass; got {sorted(class_rows.values())!r}"
    )
    assert sorted(Decimal(value) for value in valuation_rows.values()) == sorted((_VALORES_N1, _CUENTAS_N1))


def test_the_evidence_projection_joins_the_produced_rows_at_their_bloque_totals(tmp_path: Path) -> None:
    """The projection turns the produced rows into per-bloque valuation observations."""
    revision, modelo_revision, _report = _calculate_through_the_mesh(
        tmp_path=tmp_path,
        observations=_foreign_asset_observations(),
    )

    evidence = modelo_720_evidence_observation(
        revision=revision,
        modelo_revision=modelo_revision,
        filing_year=_YEAR_N_PLUS_1,
        period=_PERIOD,
    )

    assert evidence.observations, (
        "the evidence projection joined empty against a revision the real producer "
        "populated — the producer and consumer shapes have diverged"
    )
    assert dict(evidence.casilla_values) == {
        _CUENTAS_VALORACION: _CUENTAS_N1,
        _VALORES_VALORACION: _VALORES_N1,
    }
    for observation in evidence.observations:
        assert observation.legal_refs, "evidence rows must carry the casilla's legal grounding"
        assert observation.source_refs, "evidence rows must carry the casilla's source grounding"


def test_the_evidence_projection_is_empty_when_the_producer_receives_no_observations(tmp_path: Path) -> None:
    """No supplied holdings means no rows and no evidence — the join is producer-driven.

    The control for the two assertions above: without it a projection that
    fabricated observations from any source, or an assertion insensitive to the
    row bindings, would pass unnoticed.
    """
    revision, modelo_revision, report = _calculate_through_the_mesh(tmp_path=tmp_path, observations=())

    class_binding = _row_binding_id(modelo_revision, row_field=_ASSET_CLASS_ROW_FIELD)
    valuation_binding = _row_binding_id(modelo_revision, row_field=_VALUATION_ROW_FIELD)

    assert revision.row_binding_values.get(class_binding, {}) == {}
    assert revision.row_binding_values.get(valuation_binding, {}) == {}

    evidence = modelo_720_evidence_observation(
        revision=revision,
        modelo_revision=modelo_revision,
        filing_year=_YEAR_N_PLUS_1,
        period=_PERIOD,
    )
    assert evidence.observations == ()
    assert [finding for finding in report.findings if finding.message_locale_key == _ADVISORY_LOCALE_KEY] == [], (
        "with no independent valuation evidence the advisory must stay silent rather "
        "than compare the declaration against a fabricated baseline"
    )


def test_producer_supplied_rows_reach_the_verify_time_redeclaration_advisory(tmp_path: Path) -> None:
    """The whole chain: typed holdings in, operator-visible advisory out.

    The cuentas bloque grew by EUR 25,000 over its declared baseline and is
    absent from the declaration, so the advisory must fire for cuentas and only
    cuentas — driven entirely by rows the enrolled resolver produced.
    """
    _revision, _modelo_revision, report = _calculate_through_the_mesh(
        tmp_path=tmp_path,
        observations=_foreign_asset_observations(),
    )

    findings = tuple(finding for finding in report.findings if finding.message_locale_key == _ADVISORY_LOCALE_KEY)
    assert len(findings) == 1, f"expected exactly one re-declaration advisory, got {findings}"
    finding = findings[0]
    assert dict(finding.message_facts) == {
        "modelo_code": "720",
        "filing_year": _YEAR_N_PLUS_1,
        "position_key": "cuentas",
        "group_code": "cuentas",
        "prior_value_eur": _CUENTAS_N,
        "current_value_eur": _CUENTAS_N1,
        "delta_value_eur": _CUENTAS_N1 - _CUENTAS_N,
        "redeclaration_increase_threshold_eur": Decimal("20000.00"),
    }
    assert "rd-1065-2007:art-42-bis" in finding.legal_refs


def test_declaring_the_grown_bloque_withdraws_the_producer_driven_advisory(tmp_path: Path) -> None:
    """Declaring the grown cuentas valuation silences the advisory the same rows raised.

    Pins that the advisory is decided by the declaration channel and not merely
    by the presence of producer rows.
    """
    _revision, _modelo_revision, report = _calculate_through_the_mesh(
        tmp_path=tmp_path,
        observations=_foreign_asset_observations(),
        declare_cuentas=True,
    )

    assert [finding for finding in report.findings if finding.message_locale_key == _ADVISORY_LOCALE_KEY] == []
