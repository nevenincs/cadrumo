"""A filer states the pagos fraccionados a Modelo 100 credits when the Modelo 130 quarters were filed outside the application.

Casilla 0604 of the annual Renta credits the pagos fraccionados paid, which the product folds from the
four quarterly Modelo 130 returns of the same year. When the application holds none of those returns the
filer states the total: the operator layer keeps the figure apart from one merely typed and names every
quarter it stands in for, and verification reports it as stated. The statement is admitted only while none
of the quarters is held, because the relation follows its sources.

Real behaviour throughout: an isolated encrypted profile, the bundled authority, the production admission,
edit executor and verification, with every year taken from the published support envelope.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.inventory import InventoryLedgerRepository
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....application.aggregation.tests.test_inventory_source import inventory_ledger
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditDomainRefusalV1,
    ModeloEditRefusalCode,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
)
from ....application.modelo.edit_services import validate_binding_intent
from ....application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ....domain.calculations.registry.tests.modelo_100_registry_support import M100_NO_PENDING_SAVINGS_BALANCES
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from ....domain.contribuyente.inventory.records import InventoryLedgerDocument
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from .observation_seeding_support import save_stamped_observation
from .verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The carry the annual Renta reads from the year's Modelo 130 quarters.
_BINDING = "renta-modelo-130-pagos-fraccionados"
#: The same carry read from the year's Modelo 131 quarters.
_BINDING_131 = "renta-modelo-131-pagos-fraccionados"
_QUARTERS = ("1T", "2T", "3T", "4T")
_ATTESTED_KEY = "application.modelo.findings.cross_period_dependency_operator_attested"
_CONFLICT_KEY = "application.modelo.findings.cross_period_dependency_attestation_conflict"
#: The negative general bases and savings balances pending from earlier ejercicios, which a Modelo 100 refuses
#: to calculate without a statement.
_PENDING_CARRIES = (
    *M100_NO_PENDING_SAVINGS_BALANCES,
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
)
_FACTS = (UserProfileFact(path="tax_residence.ccaa", value="madrid"), *RENTA_UNMARRIED_TAXPAYER_FACTS)
_STATED = Decimal("2400.50")
_STATED_CANONICAL = "2400.5"


def _year() -> int:
    support = published_supported_filing_years()
    assert support is not None
    return support.floor


@contextmanager
def _annual_work(tmp_path: Path) -> Generator[SeededOperatorWork]:
    """Seed the support floor's Modelo 100 for a filer whose activity keeps a complete inventory book.

    The economic activity's Anexo D inventory rows feed the general base, so without the
    year's book they stay unresolved and the calculation refuses before any carry is read.
    """
    year = _year()
    with seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as work:
        InventoryLedgerRepository().save(InventoryLedgerDocument(ledgers=(inventory_ledger("actividad", year=year),)))
        yield work


def _intent(binding_id: str, kind: ModeloEditBindingIntentKind, value: Decimal | None) -> ModeloBindingEditIntentV1:
    return ModeloBindingEditIntentV1(address=ModeloEditBindingAddressV1(binding_id=binding_id), kind=kind, value=value)


def _state_nothing_pending(binding_id: str) -> ModeloBindingEditIntentV1:
    return _intent(binding_id, ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT, None)


_PENDING_CARRIES_STATED = tuple(_state_nothing_pending(binding_id) for binding_id in _PENDING_CARRIES)


def _attest(binding_id: str = _BINDING, value: Decimal = _STATED) -> ModeloBindingEditIntentV1:
    return _intent(binding_id, ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE, value)


def _offered_intents(work: SeededOperatorWork, binding_id: str = _BINDING) -> tuple[ModeloEditBindingIntentKind, ...]:
    (entry,) = (
        entry
        for entry in work.baseline().permitted_surface
        if isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1) and entry.binding_id == binding_id
    )
    return tuple(entry.allowed_intents)


def _verify(work: SeededOperatorWork) -> tuple[ModeloVerificationFinding, ...]:
    """Verify the work unit's current revision through the production gate; its findings."""
    result = verify_modelo_revision_with_preconditions(
        work.require_head().calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_test_verification_repository_bundle(),
        actor="operator-test",
        workflow_profile=TaxpayerProfile(tax_id="X0001500M", iva_regime=IVARegime("GENERAL")),
        operator_scope_ports=build_operator_scope_ports(),
        operation=work.operation,
    )
    return tuple(result.report.findings)


def _quarter_findings(
    findings: tuple[ModeloVerificationFinding, ...], kind: ModeloVerificationFindingKind, source_modelo: str = "130"
) -> list[ModeloVerificationFinding]:
    return [
        finding
        for finding in findings
        if finding.kind is kind and finding.message_facts.get("source_modelo") == source_modelo
    ]


def _hold_a_quarter(period: str, *, value: Decimal = Decimal("100")) -> None:
    """Capture one Modelo 130 quarter of the year, so the application holds a source of the carry."""
    save_stamped_observation(
        CalculationObservationRepository(),
        registry_grounded_modelo_observation(
            modelo="130",
            filing_year=_year(),
            period=period,
            casilla_values={"19": value, "18": Decimal(0)},
        ),
        source_kind="app_filing",
    )


def test_the_statement_is_offered_while_none_of_the_quarters_is_held(tmp_path: Path) -> None:
    with (
        profile_adapter_composition(),
        _annual_work(tmp_path) as work,
    ):
        offered = _offered_intents(work)

    assert ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE in offered
    assert ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE in offered


@pytest.mark.parametrize("held", _QUARTERS)
def test_the_statement_is_refused_once_any_one_quarter_is_held(tmp_path: Path, held: str) -> None:
    with (
        profile_adapter_composition(),
        _annual_work(tmp_path) as work,
    ):
        _hold_a_quarter(held)
        offered = _offered_intents(work)
        refusal = validate_binding_intent(
            work.baseline(),
            ModeloEditBindingAddressV1(binding_id=_BINDING),
            ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
        )
        applied = work.apply(binding=(*_PENDING_CARRIES_STATED, _attest()))

    assert ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE not in offered
    assert ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE in offered
    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    assert refusal.code is ModeloEditRefusalCode.DISALLOWED_INTENT
    assert applied.refusal is not None
    assert applied.calculation_revision_id is None


def test_a_statement_names_every_quarter_and_clears_each_as_stated(tmp_path: Path) -> None:
    year = _year()
    with (
        profile_adapter_composition(),
        _annual_work(tmp_path) as work,
    ):
        assert work.apply(binding=(*_PENDING_CARRIES_STATED, _attest())).refusal is None
        layer = work.require_head().operator_layer
        assert layer is not None
        assert layer.binding_overrides[_BINDING] == _STATED_CANONICAL
        attestation = layer.value_attestations[_BINDING]
        assert {
            (source.source_modelo, source.source_filing_year, source.source_period) for source in attestation.sources
        } == {("130", year, quarter) for quarter in _QUARTERS}

        # Calculating again keeps the statement as the filer made it.
        recalculated = work.recalculate().operator_layer
        assert recalculated is not None
        assert recalculated.value_attestations == layer.value_attestations

        findings = _verify(work)

    assert not _quarter_findings(findings, ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN)
    reported = [finding for finding in findings if finding.message_locale_key == _ATTESTED_KEY]
    assert {finding.message_facts["source_period"] for finding in reported} == set(_QUARTERS)
    for finding in reported:
        assert finding.kind is ModeloVerificationFindingKind.ADVISORY
        assert finding.severity is ModeloVerificationFindingSeverity.WARNING
        assert finding.message_facts["source_modelo"] == "130"
        assert finding.message_facts["source_filing_year"] == year
        assert finding.message_facts["binding_id"] == _BINDING
        assert finding.message_facts["value"] == _STATED_CANONICAL
        assert finding.message_facts["target_modelo"] == "100"


def test_a_figure_merely_typed_over_the_relation_does_not_clear_the_quarters(tmp_path: Path) -> None:
    with (
        profile_adapter_composition(),
        _annual_work(tmp_path) as work,
    ):
        typed = _intent(_BINDING, ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE, _STATED)
        assert work.apply(binding=(*_PENDING_CARRIES_STATED, typed)).refusal is None
        layer = work.require_head().operator_layer
        assert layer is not None
        assert layer.value_attestations == {}

        findings = _verify(work)

    assert _quarter_findings(findings, ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN)
    assert not [finding for finding in findings if finding.message_locale_key == _ATTESTED_KEY]


def test_a_statement_for_one_relation_leaves_the_sibling_relation_to_its_own_sources(tmp_path: Path) -> None:
    with (
        profile_adapter_composition(),
        _annual_work(tmp_path) as work,
    ):
        assert work.apply(binding=(*_PENDING_CARRIES_STATED, _attest(_BINDING))).refusal is None
        layer = work.require_head().operator_layer
        assert layer is not None
        findings = _verify(work)

    assert set(layer.value_attestations) == {_BINDING}
    assert _BINDING_131 not in layer.binding_overrides
    stated = [finding for finding in findings if finding.message_locale_key == _ATTESTED_KEY]
    assert {finding.message_facts["source_modelo"] for finding in stated} == {"130"}


def test_a_quarter_that_appears_after_the_statement_is_a_blocking_conflict(tmp_path: Path) -> None:
    with (
        profile_adapter_composition(),
        _annual_work(tmp_path) as work,
    ):
        assert work.apply(binding=(*_PENDING_CARRIES_STATED, _attest())).refusal is None
        _hold_a_quarter("2T")
        findings = _verify(work)

    conflicts = [finding for finding in findings if finding.message_locale_key == _CONFLICT_KEY]
    assert [finding.severity for finding in conflicts] == [ModeloVerificationFindingSeverity.BLOCKING]
    assert conflicts[0].message_facts["source_period"] == "2T"
    # The quarters still absent keep reading as stated; only the held one follows its source.
    stated = [finding for finding in findings if finding.message_locale_key == _ATTESTED_KEY]
    assert {finding.message_facts["source_period"] for finding in stated} == {"1T", "3T", "4T"}
