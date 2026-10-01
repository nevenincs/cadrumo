"""The activity inventory is reported missing only for a filer who declares an economic activity.

Modelo 100's Anexo D inventory rows (casillas 0177, 0181 and 0182) belong to an
economic activity. A filer whose profile declares only non-activity income holds
no activity ledger, so the calculation must not tell them a ledger is missing
or that those boxes could not be worked out. A filer who declares an activity,
or whose income categories are undeclared, still hears both when the ledger is
absent: that is a genuine gap.

Each case runs the real resolver against the published Modelo 100 2025
revision and then the calculation's own expected-missing pass, so the
diagnostics asserted are the ones a calculation persists.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.contribuyente.inventory.records import InventoryLedgerDocument
from ....domain.user_profile.values import UserProfileFact
from ...modelo._calculation_source_staging import add_expected_missing_binding_diagnostics
from ..inventory import InventorySourceResolver
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .test_inventory_source import inventory_ledger
from .withholding_filer_profile_support import withholding_work_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SALARIED = (UserProfileFact(path="taxpayer_type.irpf_income_categories", value="trabajo"),)
_ACTIVITY = (UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),)


class _LedgerStore:
    """An in-memory inventory ledger store that counts its reads."""

    def __init__(self, document: InventoryLedgerDocument) -> None:
        self.document = document
        self.loads = 0

    def load(self) -> InventoryLedgerDocument:
        self.loads += 1
        return self.document


def _revision() -> ModeloRevision:
    return published_snapshot("100", filing_year=2025, period="0A").revision


def _inventory_binding_ids(revision: ModeloRevision) -> tuple[str, ...]:
    ids = tuple(sorted(binding.id for binding in revision.bindings if binding.source is BindingSourceKind.INVENTORY))
    assert len(ids) == 3, "Modelo 100 2025 declares the three Anexo D inventory row bindings"
    return ids


def _calculate(
    operation: PinnedAuthorityOperation,
    *,
    facts: tuple[UserProfileFact, ...],
    store: _LedgerStore,
) -> tuple[CalculationSourceResolution, CalculationSourceResolution]:
    """Resolve the inventory source for one filer, then run the calculation's expected-missing pass."""
    revision = _revision()
    context = CalculationSourceContext(
        bucket_id="operator",
        modelo="100",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        revision=revision,
        profile=withholding_work_profile(operation, facts=facts),
    )
    resolved = InventorySourceResolver(inventory_repository=store).resolve(context)
    return resolved, add_expected_missing_binding_diagnostics(revision, resolved)


def _reasons(resolution: CalculationSourceResolution) -> list[tuple[str, str | None]]:
    return sorted((diagnostic.reason, diagnostic.binding_id) for diagnostic in resolution.diagnostics)


def test_a_salaried_filer_hears_nothing_about_an_activity_inventory(operation: PinnedAuthorityOperation) -> None:
    store = _LedgerStore(InventoryLedgerDocument(ledgers=()))
    inventory_ids = _inventory_binding_ids(_revision())

    resolved, calculated = _calculate(operation, facts=_SALARIED, store=store)

    assert store.loads == 0, "no activity means no activity ledger to read"
    assert resolved.inapplicable_binding_ids == inventory_ids
    assert calculated.diagnostics == ()
    # The boxes stay without a value: the engine reads them as absent, never as a worked-out zero.
    assert set(inventory_ids) <= set(calculated.unresolved_binding_ids)
    assert calculated.row_binding_values == {}


@pytest.mark.parametrize(
    "facts",
    [_ACTIVITY, ()],
    ids=["declares-an-activity", "income-categories-undeclared"],
)
def test_a_filer_who_may_carry_on_an_activity_still_hears_the_ledger_is_missing(
    operation: PinnedAuthorityOperation, facts: tuple[UserProfileFact, ...]
) -> None:
    """Teeth for the case above: the same absent ledger is reported when the activity is declared or unknown."""
    inventory_ids = _inventory_binding_ids(_revision())

    resolved, calculated = _calculate(operation, facts=facts, store=_LedgerStore(InventoryLedgerDocument(ledgers=())))

    assert resolved.inapplicable_binding_ids == ()
    assert [diagnostic.reason for diagnostic in resolved.diagnostics] == ["source_domain_not_ready"]
    assert _reasons(calculated) == sorted(
        [("source_domain_not_ready", None), *(("unresolved_binding", binding_id) for binding_id in inventory_ids)]
    )


def test_an_activity_ledger_fills_the_rows_and_leaves_no_note(operation: PinnedAuthorityOperation) -> None:
    store = _LedgerStore(InventoryLedgerDocument(ledgers=(inventory_ledger("alpha"),)))
    inventory_ids = _inventory_binding_ids(_revision())

    resolved, calculated = _calculate(operation, facts=_ACTIVITY, store=store)

    assert store.loads == 1
    assert {binding_id for binding_id, _row in resolved.row_binding_values} == set(inventory_ids)
    assert all(isinstance(value, Decimal) for value in resolved.row_binding_values.values())
    assert calculated.diagnostics == ()
