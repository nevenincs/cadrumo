"""Every profile key that can gate an obligation declares a named unset warning.

:func:`~cadrumo.application.overview.calendar_warnings._record_gating_field`
drops a key that
:data:`~cadrumo.application.overview.calendar_warnings.PROFILE_FIELD_WARNING_LOCALE_KEYS`
does not name, so an unnamed gating key costs the operator the whole report:
the obligation it gates cannot be scoped, and nothing says which answer is
missing. The mapping is hand-written while the gating keys come from the
registry, so completeness is not structural and this is what holds it.

The reachable set is derived from the registry under the caller's pinned
authority, never written down, across all three ways a profile fact decides
what the operator is shown:

- an applicability rule's ``gating_payer_facts``, which covers the fact a rule
  requires and the fact an exclusion reads;
- the residency and IVA-regime axes a rule names directly;
- a deadline window's ``applicability_conditions``, which decide whether one
  window of an applicable modelo opens;
- a filing schedule's ``profile_conditions``, which decide the cadence, and
  therefore produce no window at all when unanswered.
"""

from __future__ import annotations

import pytest

from ....core.config import override_settings
from ....core.i18n.render import tr
from ....domain.calculations.registry.applicability import iter_modelo_applicability_rules
from ....domain.calculations.registry.applicability_payer_facts import payer_fact_profile_keys
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..calendar_warnings import (
    PROFILE_FIELD_WARNING_LOCALE_KEYS,
    derive_gating_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("en", "es", "ca", "hu")


def _reachable_gating_keys(operation: PinnedAuthorityOperation) -> frozenset[str]:
    """Return every profile key the registry can gate an obligation on."""
    keys: set[str] = set()
    for rule in iter_modelo_applicability_rules(operation=operation):
        for fact in rule.gating_payer_facts:
            keys.update(payer_fact_profile_keys(fact))
        if rule.applicable_fiscal_residencies:
            keys.add("taxpayer.fiscal_residency")
        if rule.applicable_iva_regimes:
            keys.add("iva.regime")
    for modelo in operation.modelo_ids():
        for metadata in operation.modelo_directory(modelo).revisions:
            for window in metadata.deadline_windows:
                keys.update(condition.field for condition in window.applicability_conditions)
            for schedule in metadata.filing_schedules:
                keys.update(condition.field for condition in schedule.profile_conditions)
    return frozenset(keys)


def test_every_reachable_gating_key_declares_an_unset_warning(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    unnamed = _reachable_gating_keys(authority_operation) - frozenset(PROFILE_FIELD_WARNING_LOCALE_KEYS)

    assert not unnamed, f"gating keys with no unset warning: {sorted(unnamed)}"


def test_every_declared_unset_warning_names_a_reachable_gating_key(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The other direction: a mapping no registry key reaches is a sentence nothing can print."""
    unreachable = frozenset(PROFILE_FIELD_WARNING_LOCALE_KEYS) - _reachable_gating_keys(authority_operation)

    assert not unreachable, f"unset warnings no gating key reaches: {sorted(unreachable)}"


def test_the_derived_gating_fields_cover_every_reachable_key(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The mapping is only useful if the derivation actually records each key."""
    derived = derive_gating_fields(operation=authority_operation)

    assert frozenset(derived) == _reachable_gating_keys(authority_operation)
    for key, (modelos, message_key, action_id) in derived.items():
        assert modelos, f"{key} names no modelo"
        assert message_key == PROFILE_FIELD_WARNING_LOCALE_KEYS[key]
        assert action_id == "operator.profile.edit"


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_unset_warning_sentence_resolves_in_every_supported_locale(
    locale: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A named gap the operator cannot read in their own language is still an unnamed gap."""
    missing: list[str] = []
    with override_settings(cadrumo_output_language=locale):
        for key in sorted(set(PROFILE_FIELD_WARNING_LOCALE_KEYS.values())):
            rendered = tr(key)
            if not rendered.strip() or rendered == key:
                missing.append(key)
    assert not missing, f"unset warnings without a {locale} translation: {missing}"
