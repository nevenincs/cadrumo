"""Composition guard: every key-name redaction predicate carries the shared base.

:data:`cadrumo.core.redaction.ALWAYS_REDACT_KEY_TERMS` exists so a term that must
never diverge (a bearer token, a NIF, a credential) has exactly one declaration.
Each consuming key-name predicate is required to compose from it — this module
asserts the composition holds for the three production sites that declare one:
:data:`cadrumo.core.logging.SCRUB_FIELD_PATTERNS`, the two frozensets in
:mod:`cadrumo.application.live.remote_state_outcomes`, and the profile-overview
mask vocabulary in :mod:`cadrumo.application.user_profile`. A future edit that
drops the union (redeclaring one site's set as a bare literal again) reds this
gate; nothing else in the tree would catch that regression.

This said "the two production sites" while a third had never composed the base at
all — missing eight of its terms and independently redeclaring four. **The gate
was blind to the one site the invariant was actually violated at, while its own
prose asserted the enumeration was complete.** An enumeration stated in a
docstring is a claim about the tree that nothing re-derives, so adding a
consuming predicate means adding its assertion here in the same change.
"""

from __future__ import annotations

import pytest

from ....application.user_profile.overview import _MASK_KEYWORDS
from ....core.logging import SCRUB_FIELD_PATTERNS
from ....core.redaction.rules import ALWAYS_REDACT_KEY_TERMS
from ..remote_state_outcomes import (
    _SENSITIVE_FAILURE_CONTEXT_EXACT_KEYS,
    _SENSITIVE_FAILURE_CONTEXT_KEY_PARTS,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_shared_base_is_non_empty() -> None:
    """Anti-vacuity: an emptied base would make every subset check below pass trivially."""
    assert len(ALWAYS_REDACT_KEY_TERMS) >= 10


def test_logging_scrub_patterns_compose_the_shared_base() -> None:
    """``core.logging``'s key-name vocabulary must carry every shared base term."""
    assert set(SCRUB_FIELD_PATTERNS) >= ALWAYS_REDACT_KEY_TERMS


def test_remote_state_exact_keys_compose_the_shared_base() -> None:
    """The diagnostic-context exact-key set must carry every shared base term."""
    assert ALWAYS_REDACT_KEY_TERMS <= _SENSITIVE_FAILURE_CONTEXT_EXACT_KEYS


def test_remote_state_key_parts_compose_the_shared_base() -> None:
    """The diagnostic-context substring-key set must carry every shared base term."""
    assert ALWAYS_REDACT_KEY_TERMS <= _SENSITIVE_FAILURE_CONTEXT_KEY_PARTS


def test_remote_state_context_sets_keep_their_own_domain_specific_additions() -> None:
    """The AEAT/infra identifiers are real additions, not a full re-derivation of the base.

    Guards against a "fix" that collapses either set down to exactly the shared
    base, silently dropping the domain-scoped keys (``bucket_id``, ``profile_id``,
    ``num_soporte``, ...) that make this predicate narrower than the generic
    logging one in the first place.
    """
    assert _SENSITIVE_FAILURE_CONTEXT_EXACT_KEYS - ALWAYS_REDACT_KEY_TERMS
    assert _SENSITIVE_FAILURE_CONTEXT_KEY_PARTS - ALWAYS_REDACT_KEY_TERMS


def test_profile_overview_mask_keywords_compose_the_shared_base() -> None:
    """The profile-overview mask vocabulary must carry every shared base term.

    This is the site the gate could not see. It decides whether a fact the schema
    does NOT classify is masked before an operator reads it, so a base term missing
    here renders a NIF in the clear on the one surface built to show a taxpayer
    their own profile — while ``core.logging`` and the live diagnostics both
    already knew to redact it.
    """
    assert ALWAYS_REDACT_KEY_TERMS <= _MASK_KEYWORDS


def test_profile_overview_mask_keywords_keep_their_own_domain_specific_additions() -> None:
    """The Spanish stems and the bare ``key`` subsumption are real additions, not the base.

    Guards the collapse in the other direction: reducing this set to exactly the
    shared base would drop ``secreto`` / ``contraseña`` / ``clave`` — an undeclared
    fact's path may be authored in either language — and drop bare ``key``, whose
    subsumption of ``api_key`` / ``private_key`` is load-bearing here and
    deliberately NOT promoted to the base, where it would match ``header_key`` and
    ``producer_key`` across the whole tree.
    """
    assert _MASK_KEYWORDS - ALWAYS_REDACT_KEY_TERMS
    assert "key" in _MASK_KEYWORDS
    assert "key" not in ALWAYS_REDACT_KEY_TERMS


def test_logging_scrub_patterns_keep_their_own_domain_specific_additions() -> None:
    """``core.logging``'s own additions (cookies, passphrases, ...) must survive composition."""
    assert set(SCRUB_FIELD_PATTERNS) - ALWAYS_REDACT_KEY_TERMS
