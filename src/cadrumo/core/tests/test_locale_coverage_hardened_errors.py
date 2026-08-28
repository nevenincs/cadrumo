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

from ..i18n import tr

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
        # ProjectAnswersRegistrationError (core/setup_answers.py)
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
        # adapter-missing x 4 (_adapters.py)
        "application.workflow.errors.adapter_missing_submission_engine",
        "application.workflow.errors.adapter_missing_deadline_engine",
        "application.workflow.errors.adapter_missing_filing_draft_builder",
        "application.workflow.errors.adapter_missing_inputs_provider",
        # run-id-invalid x 2 (_persistence.py)
        "application.workflow.errors.run_id_invalid_separators",
        "application.workflow.errors.run_id_invalid_blank",
        # ModeloProfileReadinessError (_profile_readiness_gate.py)
        "application.modelo.errors.profile_readiness_missing",
        "application.modelo.errors.profile_readiness_profile_missing",
    },
)

_SUPPORTED_LOCALES: tuple[str, ...] = ("en", "es", "ca", "hu")


def test_hardened_error_keys_resolve_in_catalogues() -> None:
    """Assert that every hardened-error locale key resolves to a non-trivial string.

    A "trivial" resolution is one where the returned value equals the
    dotted key itself (the self-referencing scaffold placeholder pattern).
    If the catalogue has no entry for the key python-i18n returns the key
    unchanged; the assertion below rejects that outcome.
    """
    assert _HARDENED_ERROR_KEYS, "the hardened-error key inventory is empty; this gate would resolve nothing and pass"
    failures: list[str] = []
    for key in sorted(_HARDENED_ERROR_KEYS):
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
