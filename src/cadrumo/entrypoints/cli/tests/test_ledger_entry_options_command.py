"""``aeat app ledger entry-options`` through the real CLI, registered operation and result schema."""

from __future__ import annotations

import pytest

from ....application.ledger.entry_limits import ledger_entry_limits
from ....core.external_constants import DEFAULT_CURRENCY
from ....domain.transactions.classification_effects import keeps_category, takes_usage_ratio
from ....domain.transactions.enums import (
    BusinessClassification,
    carries_business_figures,
    rule_names_category,
    split_part_requires_category,
    takes_business_share,
)
from ....tests.cli_envelope import unwrap_cli_result
from ..ledger_results import LedgerEntryOptionsResult
from .profile_world_fixtures import cli_surface_isolated_backend
from .scenario_support import create_cli_surface_profile, invoke

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

__all__ = ["cli_surface_isolated_backend"]


@pytest.mark.usefixtures("authority_operation")
def test_entry_options_serves_what_each_classification_takes_and_validates_against_its_schema() -> None:
    create_cli_surface_profile(log_in=False)

    result = invoke(["--format", "json", "app", "ledger", "entry-options"])

    assert result.exit_code == 0, result.output
    payload = unwrap_cli_result(result)
    served = LedgerEntryOptionsResult.model_validate(payload)
    assert [row.classification for row in served.classifications] == [item.value for item in BusinessClassification]
    for row in served.classifications:
        classification = BusinessClassification(row.classification)
        assert row.takes_business_share is takes_business_share(classification)
        assert row.takes_usage_ratio is takes_usage_ratio(classification)
        assert row.carries_business_figures is carries_business_figures(classification)
        assert row.keeps_category is keeps_category(classification)
        assert row.rule_may_name_category is rule_names_category(classification)
        assert row.split_part_requires_category is split_part_requires_category(classification)
    assert served.limits.payment_id_pattern == ledger_entry_limits().payment_id_pattern
    _assert_default_currency_is_served(served)


def _assert_default_currency_is_served(served: LedgerEntryOptionsResult) -> None:
    """The functional currency a new movement is offered is one the currency family serves."""
    assert served.default_currency == DEFAULT_CURRENCY
    currencies = next(family for family in served.families if family.family == "currency")
    assert served.default_currency in {option.value for option in currencies.options}


@pytest.mark.usefixtures("authority_operation")
def test_entry_options_text_output_lists_each_classification() -> None:
    create_cli_surface_profile(log_in=False)

    result = invoke(["app", "ledger", "entry-options"])

    assert result.exit_code == 0, result.output
    lines = [line for line in result.output.splitlines() if line.startswith("classification\t")]
    assert [line.split("\t")[1] for line in lines] == [item.value for item in BusinessClassification]
    mixed = next(line for line in lines if line.split("\t")[1] == BusinessClassification.MIXED.value)
    assert mixed.split("\t")[2:] == ["True", "True", "True", "True", "False", "False"]
    assert f"default_currency\t{DEFAULT_CURRENCY}" in result.output.splitlines()
