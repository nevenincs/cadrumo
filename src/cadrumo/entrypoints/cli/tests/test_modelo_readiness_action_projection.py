"""Modelo readiness carries native facts, not locally selected action axes."""

from __future__ import annotations

import pytest

from ....application.ledger import LedgerPreflightIssue, LedgerPreflightIssueReason
from ....application.state_projection import (
    CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS,
    ProjectionModeloBindingRequirement,
    ProjectionModeloReadiness,
)
from ....application.user_profile import ProfilePreflightRequirement
from ....core import BindingSourceKind, Period
from ....core.i18n import tr
from .._modelo_readiness_cli import _readiness_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_readiness_locale_projection_is_total_over_native_binding_codes() -> None:
    assert set(CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS) == set(BindingSourceKind)


def test_binding_readiness_locale_projection_resolves_every_key_in_every_catalogue() -> None:
    sentinel = "__missing_binding_readiness_translation__"
    for key in set(CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS.values()):
        for locale in ("ca", "en", "es", "hu"):
            assert tr(key, locale=locale, default=sentinel) != sentinel

    with pytest.raises((AttributeError, TypeError)):
        setter = object.__getattribute__(
            CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS,
            "__setitem__",
        )
        assert callable(setter)
        setter(BindingSourceKind.PROFILE, "forbidden")


def test_readiness_payload_preserves_facts_without_selecting_actions() -> None:
    period = Period.from_year_and_code(2026, "1T")
    report = ProjectionModeloReadiness(
        profile_id="11111111-1111-4111-8111-111111111111",
        modelo="303",
        revision_id="2026-y-siguientes",
        filing_year=2026,
        period=period,
        missing=(
            ProfilePreflightRequirement(
                selector="tax_residence.jurisdiction_scope",
                section_key="tax_residence",
                field_key="jurisdiction_scope",
                label="Jurisdiction scope",
            ),
        ),
        profile_ready=False,
        per_operation_requirements_assessed=True,
        missing_bindings=(
            ProjectionModeloBindingRequirement(
                binding_id="m303-prior-period-result",
                source=BindingSourceKind.PREVIOUS_FILING,
                input_channel="decimal",
            ),
        ),
        binding_ready=False,
        ledger_preflight_required=True,
        ledger_ready=False,
        ledger_period=period,
        ledger_checked_transaction_count=1,
        ledger_issues=(
            LedgerPreflightIssue(
                transaction_id="a" * 64,
                reason=LedgerPreflightIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE,
                detail="counterparty identification state is required",
            ),
        ),
        ready=False,
    )

    payload = _readiness_result(
        report,
        modelo="303",
        revision_id="2026-y-siguientes",
        filing_year=2026,
    )

    assert payload.missing[0].selector == "tax_residence.jurisdiction_scope"
    assert payload.missing_bindings[0].source is BindingSourceKind.PREVIOUS_FILING
    assert payload.ledger_issues[0].reason == LedgerPreflightIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE.value
    assert "operator_action" not in payload.missing[0].model_dump()
    assert "operator_action" not in payload.missing_bindings[0].model_dump()
    assert "operator_action" not in payload.ledger_issues[0].model_dump()
