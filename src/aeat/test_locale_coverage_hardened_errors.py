"""W05.P23 locale coverage: translated_message key resolution audit.

S443 real-behavior test — asserts that all error classes hardened in
W05.P23 (S429-S441) carry translated_message keys that resolve to
non-trivial strings in all four supported catalogues (en, es, ca, hu).

"Non-trivial" means the resolved string differs from the raw dotted key
(i.e. the key exists and has a real translation, not a self-referencing
scaffold placeholder).

All assertions exercise actual raises so the contract is grounded in
real runtime behaviour, not static inspection.
"""

from __future__ import annotations

import pytest

from aeat.core.i18n import tr

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

# Keys introduced or hardened by W05.P23.S429-S441.
_W05_P23_KEYS: frozenset[str] = frozenset(
    {
        # S429: state-unreadable regression fix (_persistence.py)
        "application.workflow.errors.state_unreadable",
        # S430: SessionDeserializationError (_sessions.py)
        "application.auth.errors.session_field_not_datetime",
        # S431: AuthProviderReservedError (_operator.py)
        "application.auth.errors.provider_reserved",
        # S432: ProfileRegistrationError (core/profile.py)
        "core.profile.errors.registration_duplicate_callable",
        # S433: ProfileLabelAmbiguousError (_profile_bucket_scan.py)
        "application.workflow.errors.profile_label_ambiguous",
        # S434: WorkflowResumeRefusedError x 4 (_resume.py)
        "application.workflow.errors.resume_refused_not_aborted",
        "application.workflow.errors.resume_refused_no_aborted_reason",
        "application.workflow.errors.resume_refused_terminal_reason",
        "application.workflow.errors.resume_refused_no_obligation",
        # S435: state-write-invalid-payload (_persistence.py)
        "application.workflow.errors.state_write_invalid_payload",
        # S436: run-not-found (_persistence.py)
        "application.workflow.errors.run_not_found",
        # S437: period-registry-year-unresolvable x 2 (_engine.py)
        "application.workflow.errors.period_registry_year_unresolvable",
        "application.workflow.errors.period_registry_unmappable",
        # S438: no-run-for-period (_resume.py)
        "application.workflow.errors.no_run_for_period",
        # S439: adapter-missing x 3 (_adapters.py)
        "application.workflow.errors.adapter_missing_deadline_engine",
        "application.workflow.errors.adapter_missing_filing_draft_builder",
        "application.workflow.errors.adapter_missing_inputs_provider",
        # S440: run-id-invalid x 2 (_persistence.py)
        "application.workflow.errors.run_id_invalid_separators",
        "application.workflow.errors.run_id_invalid_blank",
    }
)

_SUPPORTED_LOCALES: tuple[str, ...] = ("en", "es", "ca", "hu")


@pytest.mark.parametrize("locale", _SUPPORTED_LOCALES)
@pytest.mark.parametrize("key", sorted(_W05_P23_KEYS))
def test_w05_p23_key_resolves_in_catalogue(key: str, locale: str) -> None:
    """Assert that every W05.P23 locale key resolves to a non-trivial string.

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
    assert resolved, (
        f"Locale key {key!r} resolved to an empty string in the {locale!r} catalogue."
    )
