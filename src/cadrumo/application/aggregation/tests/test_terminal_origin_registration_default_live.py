"""The terminal-origin audit must work on a revision that authors no expectation.

Every existing test of this audit fabricates the expectation it then audits
against. That proves the comparison but not the DEFAULT: a binding authoring no
``terminal_origins`` falls back to the classes its provider registration says
the family can produce, and if that fallback were empty the audit would silently
pass every binding in the corpus -- an audit that never fires and a suite that
never notices.

Two live checks, both against shipped data and real resolver output:

* over a real revision whose bindings author no ``terminal_origins`` at all, the
  effective expectation is non-empty and registration-derived, and the audit
  runs over it rather than short-circuiting;
* a resolution produced by the real profile resolver over a synthetic profile
  emits no ``terminal_origin_mismatch``. A clean path that reported a mismatch
  would mean the default disagrees with what the enrolled resolvers actually
  produce, which is the failure the fallback exists to avoid.

The profile record is synthetic: an invented profile uuid, an invented NIF, and
one residence fact.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.binding_provider_registration import BINDING_PROVIDER_REGISTRATIONS
from ....domain.calculations.registry.binding_terminal_audit import (
    effective_terminal_origins,
    expected_terminal_origins,
)
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ...modelo.profile_binding import resolve_profile_sourced_bindings
from ..terminal_origin_audit import collect_terminal_origin_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC)
_PROFILE_ID = "20020020-0200-4200-8200-200200200200"


def _snapshot() -> RegistrySnapshot:
    return bundled_authority().snapshot("100", filing_year=2025, period="0A")


def _profile_record() -> UserProfileRecord:
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Ñ"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def test_unauthored_bindings_take_the_registration_derived_expectation() -> None:
    """A revision authoring no ``terminal_origins`` still has a live expectation.

    The assertion is on the fallback's identity, not merely its emptiness: it
    must be the provider registration's own answer, so a registration that
    narrowed its producible classes narrows the audit with it.
    """
    revision = _snapshot().revision
    unauthored = [binding for binding in revision.bindings if not binding.terminal_origins]
    assert unauthored, "the revision authors terminal_origins everywhere, so the default is untested here"

    with_expectation = 0
    for binding in unauthored:
        effective = effective_terminal_origins(binding)
        assert effective == expected_terminal_origins(binding.source)
        if effective:
            with_expectation += 1
            registration = BINDING_PROVIDER_REGISTRATIONS.get(binding.source)
            assert registration is not None
            assert {expectation.source_class for expectation in effective} <= set(
                registration.permitted_terminal_origins,
            )

    assert with_expectation, "no unauthored binding carries a registration-derived expectation"


def test_clean_profile_resolution_emits_no_terminal_origin_mismatch() -> None:
    """Real resolver output over a synthetic profile audits clean.

    The resolution comes from the production profile resolver, not a fabricated
    provenance tuple, so a default that disagreed with what the resolver
    actually stamps would surface here rather than in front of an operator.
    """
    snapshot = _snapshot()
    resolution = resolve_profile_sourced_bindings(
        snapshot,
        bucket_id=_PROFILE_ID,
        profile_record=_profile_record(),
    )
    assert resolution.provenance, "the profile resolver resolved nothing, so the audit has nothing to audit"

    diagnostics = collect_terminal_origin_diagnostics(snapshot.revision, resolution)

    assert [diagnostic.reason for diagnostic in diagnostics if diagnostic.reason == "terminal_origin_mismatch"] == []
