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

from ....domain.categories.proportionality_catalogue import require_proportionality_kind
from ....domain.categories.spending_category import SpendingCategory
from .cli_fixture_worlds import invoke_joined_cli as invoke_cached_cli
from .profile_world_fixtures import (
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


def test_ledger_ratios_eligible_lists_the_registry_wording_in_the_chosen_language() -> None:
    """Each eligible category is printed with the registry's label, kind and notes,
    said in the language the invocation asked for rather than the worker's."""

    english = _invoke(["app", "ledger", "ratios", "eligible", "--output-language", "en"])
    spanish = _invoke(["app", "ledger", "ratios", "eligible", "--output-language", "es"])

    assert english.exit_code == 0, english.output
    assert spanish.exit_code == 0, spanish.output
    assert (
        "ibi_vivienda_afecto\tProperty tax (IBI) on home used for business\tusage_ratio_home_area\toverride=.\t"
        "Deductible in proportion to the home's floor area used for the business and to your ownership "
        "share in it; the 30% supplies factor does not apply (Ley 35/2006 art. 29.2, Reglamento IRPF "
        "art. 22.3, property tax on the home used for business)."
    ) in english.output.splitlines()
    assert (
        "ibi_vivienda_afecto\tIBI de la vivienda afecta\tusage_ratio_home_area\toverride=.\t"
        "Deducible en proporción a la superficie de la vivienda afecta a la actividad y a tu porcentaje "
        "de titularidad en ella; no se aplica el 30 % de los suministros (Ley 35/2006 art. 29.2, "
        "Reglamento IRPF art. 22.3, IBI de la vivienda afecta)."
    ) in spanish.output.splitlines()


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


@pytest.mark.usefixtures("authority_operation")
def test_ratio_keys_are_grounded_before_the_frontend_projects_bounded_worker_tokens() -> None:
    """The worker validates meaning; frontend rendering preserves its pinned tokens."""
    from pydantic import ValidationError

    from ....domain.calculations.registry.errors import RegistryValidationError
    from ....domain.calculations.registry.tests.fact_scope import outside_governed_fact_validation
    from ....domain.categories.spending_category_catalogue import require_spending_category
    from ..ledger_ratios_results import RatiosEligibleRowPayload, RatiosRowPayload

    with pytest.raises(RegistryValidationError, match="is not declared"):
        require_spending_category("unknown-category")

    with pytest.raises(RegistryValidationError, match="is not declared"):
        require_proportionality_kind("bogus")

    for category in ("", "x" * 97):
        with pytest.raises(ValidationError):
            RatiosRowPayload(category=category, ratio="0.5")
    for kind in ("", "x" * 97):
        with pytest.raises(ValidationError):
            RatiosEligibleRowPayload(
                category="worker-category",
                label="Worker category",
                notes="Worker notes.",
                proportionality_kind=kind,
                override_present=False,
            )

    with outside_governed_fact_validation():
        projected = RatiosEligibleRowPayload(
            category="worker-pinned-category",
            label="Worker pinned category",
            notes="Worker pinned notes.",
            proportionality_kind="worker-pinned-kind",
            override_present=False,
        )
        assert projected.model_dump(mode="json")["category"] == "worker-pinned-category"
        assert projected.model_dump(mode="json")["proportionality_kind"] == "worker-pinned-kind"

    # A canonical member is accepted and still serialises to its plain string.
    row = RatiosRowPayload(category=SpendingCategory.from_registry("suministros_home_office_luz"), ratio="0.5")
    assert row.model_dump(mode="json")["category"] == "suministros_home_office_luz"
    eligible = RatiosEligibleRowPayload(
        category=SpendingCategory.from_registry("suministros_home_office_luz"),
        label="Home-office electricity",
        notes="Deductible in proportion to the home's business-use floor area.",
        proportionality_kind=require_proportionality_kind("usage_ratio_home_area").value,
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

    from ..ledger_ratios_results import RatiosRowPayload

    for bad in ("-1", "2", "1.5", "not-a-decimal"):
        with pytest.raises(ValidationError):
            RatiosRowPayload(category=SpendingCategory.from_registry("suministros_home_office_luz"), ratio=bad)

    for good in ("0", "0.30", "1"):
        assert (
            RatiosRowPayload(
                category=SpendingCategory.from_registry("suministros_home_office_luz"),
                ratio=good,
            ).ratio
            == good
        )


def test_ratios_validate_finding_requires_kind_and_detail() -> None:
    """An empty finding is indistinguishable from no finding, so it is refused."""
    from pydantic import ValidationError

    from ..ledger_ratios_results import RatiosValidateFindingPayload

    with pytest.raises(ValidationError):
        RatiosValidateFindingPayload(
            category=SpendingCategory.from_registry("suministros_home_office_luz"),
            kind="missing_override",
            detail="",
        )

    with pytest.raises(ValidationError):
        RatiosValidateFindingPayload(
            category=SpendingCategory.from_registry("suministros_home_office_luz"),
            kind="",
            detail="no override persisted",
        )


def test_usage_ratio_bound_is_a_single_shared_authority() -> None:
    """The persisted profile and the transport edge share one range check."""
    from decimal import Decimal

    from ....domain.usage_ratios.errors import UsageRatioValidationError
    from ....domain.usage_ratios.model import validate_usage_ratio_bound

    assert validate_usage_ratio_bound(Decimal("0.3"), label="ratio") == Decimal("0.3")
    for bad in (Decimal("-0.01"), Decimal("1.01")):
        with pytest.raises(UsageRatioValidationError):
            validate_usage_ratio_bound(bad, label="ratio")
