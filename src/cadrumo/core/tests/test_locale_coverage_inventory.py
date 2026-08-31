"""Locale coverage inventory: translated_message key resolution audit.

Real-behavior test — asserts that operator-facing error classes across
the auth, sede, modelo, ledger, user_profile, aggregation, and wizard
surfaces carry translated_message keys that resolve to non-trivial
strings in all four supported catalogues (en, es, ca, hu).

What "non-trivial" means here: the resolved string must differ from the
raw dotted key (i.e. the key exists in the catalogue and has been given a
real translation, not left as a self-referencing placeholder).

The key set is the curated inventory of operator-facing error locale
keys whose translations must remain in lock-step across catalogues;
new operator-error keys should be added here as they are introduced.
"""

from __future__ import annotations

import pytest

from ..i18n import tr

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Operator-facing error and label locale keys whose catalogue
# resolution must be verified across en/es/ca/hu. Grouped by
# originating domain surface to make additions reviewable.
_OPERATOR_ERROR_LOCALE_KEYS: frozenset[str] = frozenset(
    {
        # adapters.auth.clave_movil
        "adapters.auth.clave_movil.errors.already_active",
        "adapters.auth.clave_movil.errors.verify_requires_active_context",
        "adapters.auth.clave_movil.errors.metadata_invalid",
        "adapters.auth.clave_movil.errors.approval_timeout",
        "adapters.auth.clave_movil.errors.dni_nie_not_set",
        # adapters.auth.authenticator
        "adapters.auth.authenticator.errors.session_stale",
        "adapters.auth.authenticator.errors.no_active_context",
        "adapters.auth.authenticator.errors.capture_requires_active_session",
        "adapters.auth.authenticator.errors.already_active_before_resume",
        "adapters.auth.authenticator.errors.no_context_capture_storage",
        "adapters.auth.authenticator.errors.capture_requires_certificate",
        "adapters.auth.authenticator.errors.persisted_session_verification_failed",
        # adapters.sede (declarations / playwright surface)
        "adapters.sede.errors.playwright_buscar_click_failed",
        "adapters.sede.errors.playwright_combobox_open_failed",
        "adapters.sede.errors.playwright_combobox_select_failed",
        "adapters.sede.errors.playwright_alert_modal_failed",
        # application.modelo
        "application.modelo.errors.work_unit_mutation_refused",
        "application.modelo.errors.work_unit_already_discarded",
        "application.modelo.errors.work_unit_discarded_cannot_calculate",
        "application.modelo.errors.work_unit_discarded_cannot_import",
        "application.modelo.errors.work_unit_filing_year_period_mismatch",
        "application.modelo.errors.amendment_verification_refused_no_snapshot",
        "application.modelo.errors.amendment_verification_refused_missing_casillas",
        "application.modelo.errors.profile_readiness_missing",
        "application.modelo.errors.profile_readiness_profile_missing",
        "application.modelo.errors.workflow_input_mismatch",
        # application.ledger
        "application.ledger.errors.evidence_attachment_requires_ids",
        "application.ledger.errors.purchase_evidence_already_set",
        # application.user_profile
        "application.user_profile.errors.unsupported_bundle_schema_version",
        # aggregation (prorrata / grouping)
        "aggregation.prorrata.errors.year_out_of_range",
        "aggregation.prorrata.errors.current_year_not_after_prior",
        "aggregation.prorrata.errors.invalid_provisional_period",
        "aggregation.grouping.errors.unsupported_modelo",
        # wizard labels
        "application.wizard.next_hint.modelo_work_create",
    },
)

_SUPPORTED_LOCALES: tuple[str, ...] = ("en", "es", "ca", "hu")


def test_operator_error_locale_keys_resolve_in_catalogues() -> None:
    """Assert that every operator-error locale key resolves to a non-trivial string.

    A "trivial" resolution is one where the returned value equals the
    dotted key itself (the self-referencing scaffold placeholder pattern).
    If the catalogue has no entry for the key python-i18n returns the key
    unchanged; the assertion below rejects that outcome.
    """
    assert _OPERATOR_ERROR_LOCALE_KEYS, (
        "the operator-error key inventory is empty; this gate would resolve nothing and pass"
    )
    failures: list[str] = []
    for key in sorted(_OPERATOR_ERROR_LOCALE_KEYS):
        for locale in _SUPPORTED_LOCALES:
            resolved = tr(key, locale=locale)
            if resolved == key:
                failures.append(
                    f"Locale key {key!r} is not set in the {locale!r} catalogue "
                    f"(got self-referencing placeholder {resolved!r}). "
                    f"Add a real translation for {key!r} in the {locale!r} catalogue."
                )
            if not resolved:
                failures.append(f"Locale key {key!r} resolved to an empty string in the {locale!r} catalogue.")

    assert not failures, "\n".join(failures)
