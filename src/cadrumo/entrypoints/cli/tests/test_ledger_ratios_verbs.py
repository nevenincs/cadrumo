"""CLI surface tests for ``aeat app ledger ratios``.

Pins the 5-verb ratios subgroup (list / set / unset / eligible /
validate) against the real ratios backend, plus exercises the help-text
surface so each verb's documentation reaches the operator. Companion
to the destructive-action safeguard tests; the ratios `unset` verb is
non-destructive of accounting state (clears one per-category override
that the operator can recompute) so it has no `--yes` requirement.

The bucket-maintenance verbs are not yet mounted, so
this file covers only the ratios half of contract; the bucket-maintenance
half lands when contract is closed.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from ._isolated_profile_storage_fixtures import (
    active_profile_isolated_backend as _isolated_backend,
)

__all__ = ["_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


@pytest.mark.parametrize("verb", ["list", "set", "unset", "eligible", "validate"])
def test_ledger_ratios_verb_help_renders(verb: str) -> None:
    """Every `aeat app ledger ratios <verb> --help` renders cleanly,
    confirming each verb is mounted and its help-text translation key
    resolves to a non-empty default."""

    result = _invoke(["app", "ledger", "ratios", verb, "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output or "Uso:" in result.output, result.output


def test_ledger_ratios_list_returns_envelope_on_empty_bucket() -> None:
    """`aeat app ledger ratios list` on an empty bucket emits a typed
    envelope (no exception, no missing-override error). The verb is
    read-only and informative — operators must always be able to query
    the override surface even when no overrides are persisted."""

    result = _invoke(["app", "ledger", "ratios", "list"])
    assert result.exit_code == 0, result.output


def test_ledger_ratios_eligible_returns_envelope_on_empty_bucket() -> None:
    """`aeat app ledger ratios eligible` lists the categories whose
    overrides the engine accepts; this surface is purely registry-driven
    and works against an empty bucket."""

    result = _invoke(["app", "ledger", "ratios", "eligible"])
    assert result.exit_code == 0, result.output


def test_ledger_ratios_validate_on_empty_bucket_succeeds() -> None:
    """`aeat app ledger ratios validate` runs the engine validation on
    the persisted override set (empty here). No errors surface when no
    overrides exist; the verb proves the validation path is reachable."""

    result = _invoke(["app", "ledger", "ratios", "validate"])
    assert result.exit_code == 0, result.output


def test_ledger_ratios_unset_refuses_when_no_override_exists() -> None:
    """`aeat app ledger ratios unset <category>` against a bucket with
    no persisted override for that category surfaces the
    ``no_override_error`` translation rather than silently succeeding,
    so the operator notices the override was never persisted."""

    result = _invoke(["app", "ledger", "ratios", "unset", "material_oficina"])
    assert result.exit_code != 0, result.output


def test_ratios_payloads_refuse_unknown_category_and_kind() -> None:
    """The ratios transport payloads reuse the canonical closed sets.

    ``category`` is a :class:`SpendingCategory` and ``proportionality_kind``
    a :class:`ProportionalityKind`. Before these fields were typed from the
    canonical enums the machine-facing payload accepted any string, so an
    unknown category or rule kind crossed the CLI boundary intact.
    """
    from pydantic import ValidationError

    from ....domain.categories.proportionality import ProportionalityKind
    from ....domain.categories.spending_category import SpendingCategory
    from .._ledger_ratios_payloads import RatiosEligibleRowPayload, RatiosRowPayload

    with pytest.raises(ValidationError):
        RatiosRowPayload(category="unknown-category", ratio="0.5")

    with pytest.raises(ValidationError):
        RatiosEligibleRowPayload(
            category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
            proportionality_kind="bogus",
            override_present=False,
        )

    # A canonical member is accepted and still serialises to its plain string.
    row = RatiosRowPayload(category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ, ratio="0.5")
    assert row.model_dump(mode="json")["category"] == "suministros_home_office_luz"
    eligible = RatiosEligibleRowPayload(
        category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
        proportionality_kind=ProportionalityKind.USAGE_RATIO_HOME_AREA,
        override_present=False,
    )
    assert eligible.model_dump(mode="json")["proportionality_kind"] == "usage_ratio_home_area"


def test_ratios_payload_ratio_is_bound_by_the_domain_authority() -> None:
    """A transport ratio outside ``[0, 1]`` is refused, using the domain's own band.

    The persisted :class:`UsageRatioProfile` enforces ``[0, 1]``; before this
    change the transport row accepted ``"-1"``, so a malformed ratio reached a
    machine consumer that the persisted profile would have rejected.
    """
    from pydantic import ValidationError

    from ....domain.categories.spending_category import SpendingCategory
    from .._ledger_ratios_payloads import RatiosRowPayload

    for bad in ("-1", "2", "1.5", "not-a-decimal"):
        with pytest.raises(ValidationError):
            RatiosRowPayload(category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ, ratio=bad)

    for good in ("0", "0.30", "1"):
        assert (
            RatiosRowPayload(
                category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
                ratio=good,
            ).ratio
            == good
        )


def test_ratios_validate_finding_requires_kind_and_detail() -> None:
    """An empty finding is indistinguishable from no finding, so it is refused."""
    from pydantic import ValidationError

    from ....domain.categories.spending_category import SpendingCategory
    from .._ledger_ratios_payloads import RatiosValidateFindingPayload

    with pytest.raises(ValidationError):
        RatiosValidateFindingPayload(
            category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
            kind="missing_override",
            detail="",
        )

    with pytest.raises(ValidationError):
        RatiosValidateFindingPayload(
            category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
            kind="",
            detail="no override persisted",
        )


def test_usage_ratio_bound_is_a_single_shared_authority() -> None:
    """The persisted profile and the transport edge share one range check."""
    from decimal import Decimal

    from ....domain.usage_ratios._model import validate_usage_ratio_bound
    from ....domain.usage_ratios.errors import UsageRatioValidationError

    assert validate_usage_ratio_bound(Decimal("0.3"), label="ratio") == Decimal("0.3")
    for bad in (Decimal("-0.01"), Decimal("1.01")):
        with pytest.raises(UsageRatioValidationError):
            validate_usage_ratio_bound(bad, label="ratio")
