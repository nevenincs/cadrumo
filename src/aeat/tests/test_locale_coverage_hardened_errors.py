"""Locale coverage audit for hardened workflow / auth / profile errors.

Asserts that every translated_message key carried by the hardened error
classes resolves to a non-trivial string in all four supported
catalogues (en, es, ca, hu).

"Non-trivial" means the resolved string differs from the raw dotted key
(i.e. the key exists and has a real translation, not a self-referencing
scaffold placeholder).
"""

from __future__ import annotations

import pytest

from ..core.i18n import tr

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Hardened error keys grouped by originating module.
_HARDENED_ERROR_KEYS: frozenset[str] = frozenset(
    {
        # state-unreadable regression fix (_persistence.py)
        "application.workflow.errors.state_unreadable",
        # SessionDeserializationError (_sessions.py)
        "application.auth.errors.session_field_not_datetime",
        # AuthProviderReservedError (_operator.py)
        "application.auth.errors.provider_reserved",
        # ProfileRegistrationError (core/profile.py)
        "core.profile.errors.registration_duplicate_callable",
        # ProfileLabelAmbiguousError (_profile_bucket_scan.py)
        "application.workflow.errors.profile_label_ambiguous",
        # WorkflowResumeRefusedError x 4 (_resume.py)
        "application.workflow.errors.resume_refused_not_aborted",
        "application.workflow.errors.resume_refused_no_aborted_reason",
        "application.workflow.errors.resume_refused_terminal_reason",
        "application.workflow.errors.resume_refused_no_obligation",
        # WorkflowResumeRunAmbiguousError (_resume.py)
        "application.workflow.errors.resume_run_ambiguous",
        # state-write-invalid-payload (_persistence.py)
        "application.workflow.errors.state_write_invalid_payload",
        # run-not-found (_persistence.py)
        "application.workflow.errors.run_not_found",
        # period-registry-year-unresolvable x 2 (_engine.py)
        "application.workflow.errors.period_registry_year_unresolvable",
        "application.workflow.errors.period_registry_unmappable",
        # no-run-for-period (_resume.py)
        "application.workflow.errors.no_run_for_period",
        # adapter-missing x 3 (_adapters.py)
        "application.workflow.errors.adapter_missing_deadline_engine",
        "application.workflow.errors.adapter_missing_filing_draft_builder",
        "application.workflow.errors.adapter_missing_inputs_provider",
        # run-id-invalid x 2 (_persistence.py)
        "application.workflow.errors.run_id_invalid_separators",
        "application.workflow.errors.run_id_invalid_blank",
    },
)

_SUPPORTED_LOCALES: tuple[str, ...] = ("en", "es", "ca", "hu")


@pytest.mark.parametrize("locale", _SUPPORTED_LOCALES)
@pytest.mark.parametrize("key", sorted(_HARDENED_ERROR_KEYS))
def test_hardened_error_key_resolves_in_catalogue(key: str, locale: str) -> None:
    """Assert that every hardened-error locale key resolves to a non-trivial string.

    A "trivial" resolution is one where the returned value equals the
    dotted key itself (the self-referencing scaffold placeholder pattern).
    If the catalogue has no entry for the key python-i18n returns the key
    unchanged; the assertion below rejects that outcome.
    """
    resolved = tr(key, locale=locale)
    assert resolved != key, (
        f"Locale key {key!r} is not set in the {locale!r} catalogue "
        f"(got self-referencing placeholder {resolved!r}). "
        f"Add a real translation via "
        f"`python -m aeat.locales set {locale} {key!r} <value>`."
    )
    assert resolved, f"Locale key {key!r} resolved to an empty string in the {locale!r} catalogue."
