"""Composition guard: every key-name redaction predicate carries the shared base.

:data:`cadrumo.core.redaction.ALWAYS_REDACT_KEY_TERMS` exists so a term that must
never diverge (a bearer token, a NIF, a credential) has exactly one declaration.
Each consuming key-name predicate is required to compose from it — this module
asserts the composition holds for the two production sites that declare one:
:data:`cadrumo.core.logging.SCRUB_FIELD_PATTERNS` and the two frozensets in
:mod:`cadrumo.application.live._remote_state_outcomes`. A future edit that
drops the union (redeclaring one site's set as a bare literal again) reds this
gate; nothing else in the tree would catch that regression.
"""

from __future__ import annotations

import pytest

from ....core.logging import SCRUB_FIELD_PATTERNS
from ....core.redaction import ALWAYS_REDACT_KEY_TERMS
from .._remote_state_outcomes import (
    _SENSITIVE_FAILURE_CONTEXT_EXACT_KEYS,
    _SENSITIVE_FAILURE_CONTEXT_KEY_PARTS,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_shared_base_is_non_empty() -> None:
    """Anti-vacuity: an emptied base would make every subset check below pass trivially."""
    assert len(ALWAYS_REDACT_KEY_TERMS) >= 10


def test_logging_scrub_patterns_compose_the_shared_base() -> None:
    """``core.logging``'s key-name vocabulary must carry every shared base term."""
    assert ALWAYS_REDACT_KEY_TERMS <= set(SCRUB_FIELD_PATTERNS)


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


def test_logging_scrub_patterns_keep_their_own_domain_specific_additions() -> None:
    """``core.logging``'s own additions (cookies, passphrases, ...) must survive composition."""
    assert set(SCRUB_FIELD_PATTERNS) - ALWAYS_REDACT_KEY_TERMS
