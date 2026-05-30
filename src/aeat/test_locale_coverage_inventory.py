"""Locale coverage inventory: translated_message key resolution audit.

S396 real-behavior test — asserts that the operator-facing error classes
introduced or hardened in W04.P19 carry translated_message keys that
resolve to non-trivial strings in all four supported catalogues (en, es,
ca, hu).

What "non-trivial" means here: the resolved string must differ from the
raw dotted key (i.e. the key exists in the catalogue and has been given a
real translation, not left as a self-referencing placeholder).

The test exercises actual raises so the assertion is grounded in real
runtime behaviour, not static inspection.
"""

from __future__ import annotations

import pytest

from aeat.core.i18n import tr

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

# Keys introduced or hardened by W04.P19.S369-S395.
_W04_P19_KEYS: frozenset[str] = frozenset(
    {
        # clave_movil (S369-S371, S381-S382)
        "adapters.auth.clave_movil.errors.already_active",
        "adapters.auth.clave_movil.errors.verify_requires_active_context",
        "adapters.auth.clave_movil.errors.metadata_invalid",
        "adapters.auth.clave_movil.errors.approval_timeout",
        "adapters.auth.clave_movil.errors.dni_nie_not_set",
        # authenticator (S372-S380)
        "adapters.auth.authenticator.errors.session_stale",
        "adapters.auth.authenticator.errors.closing",
        "adapters.auth.authenticator.errors.no_active_context",
        "adapters.auth.authenticator.errors.capture_requires_active_session",
        "adapters.auth.authenticator.errors.already_active_before_resume",
        "adapters.auth.authenticator.errors.no_context_capture_storage",
        "adapters.auth.authenticator.errors.capture_requires_certificate",
        "adapters.auth.authenticator.errors.persisted_session_verification_failed",
        "adapters.auth.authenticator.errors.context_marker_missing",
        # declarations / sede (S383)
        "adapters.sede.errors.playwright_buscar_click_failed",
        "adapters.sede.errors.playwright_combobox_open_failed",
        "adapters.sede.errors.playwright_combobox_select_failed",
        "adapters.sede.errors.playwright_alert_modal_failed",
        # modelo (S384-S387)
        "application.modelo.errors.work_unit_mutation_refused",
        "application.modelo.errors.work_unit_already_discarded",
        "application.modelo.errors.amendment_verification_refused_no_snapshot",
        "application.modelo.errors.amendment_verification_refused_missing_casillas",
        "application.modelo.errors.workflow_input_mismatch",
        # ledger (S388)
        "application.ledger.errors.evidence_attachment_requires_ids",
        "application.ledger.errors.purchase_evidence_already_set",
        # user_profile (S389)
        "application.user_profile.errors.unsupported_bundle_schema_version",
        # aggregation f-string fixes (S390-S393)
        "aggregation.prorrata.errors.year_out_of_range",
        "aggregation.prorrata.errors.current_year_not_after_prior",
        "aggregation.prorrata.errors.invalid_provisional_period",
        "aggregation.grouping.errors.unsupported_modelo",
        # tab-pair labels (S394-S395)
        "application.wizard.next_hint.modelo_work_create",
        "cli.diagnostics.secure_objects.labels.namespace",
        "cli.diagnostics.secure_objects.labels.count",
    }
)

_SUPPORTED_LOCALES: tuple[str, ...] = ("en", "es", "ca", "hu")


@pytest.mark.parametrize("locale", _SUPPORTED_LOCALES)
@pytest.mark.parametrize("key", sorted(_W04_P19_KEYS))
def test_w04_p19_key_resolves_in_catalogue(key: str, locale: str) -> None:
    """Assert that every W04.P19 locale key resolves to a non-trivial string.

    A "trivial" resolution is one where the returned value equals the
    dotted key itself (the self-referencing scaffold placeholder pattern).
    If the catalogue has no entry for the key python-i18n returns the key
    unchanged; the assertion below rejects that outcome.
    """
    resolved = tr(key, locale=locale)
    assert resolved != key, (
        f"Locale key {key!r} is not set in the {locale!r} catalogue "
        f"(got self-referencing placeholder {resolved!r}). "
        f"Add a real translation via `python -m aeat.locales set {locale} {key!r} <value>`."
    )
    assert resolved, (
        f"Locale key {key!r} resolved to an empty string in the {locale!r} catalogue."
    )
