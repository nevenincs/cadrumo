"""Typed registry of bootstrap-exempt CLI verb paths.

A bootstrap-exempt verb runs **without** an active
:class:`BucketSession`. The CLI root callback skips the session
open for these verbs; every other verb is active-gated and refused
with a translated :class:`CliRefusedBoundaryError` when no active
profile resolves.

The exemption list is the seam between the CLI transport layer and
the application's lifecycle expectation. Each entry names the full
verb path as the operator would type it.

Membership criteria:

- The verb must function correctly on a fresh ``AEAT_LOCAL_STORAGE_ROOT``
  with no active profile pointer and no encrypted state.
- The verb must not perform any column-level encrypt or decrypt
  operation as a side effect of its own work.
- The verb is either the operator's first-run on-ramp
  (``profile create``, ``profile import``), a state-free diagnostic
  (``--version``, ``--help``, ``config repair`` family), or a verb
  that explicitly operates on plaintext fingerprints rather than
  decrypted payloads.

The registry is referenced from the CLI root callback at active-gate
time. The matching is full-path-prefix: a request to
``aeat config profile create alice`` matches the exempt entry
``config profile create``.
"""

from __future__ import annotations

# Bootstrap-exempt verb paths (Tuple[str, ...] — the leading 'aeat' is implicit).
# Each entry is a space-separated path; matching is prefix-based.
BOOTSTRAP_EXEMPT_VERB_PATHS: tuple[str, ...] = (
    # First-run on-ramp: the operator has no profile yet and must
    # be able to create one. The wizard itself opens a transient
    # session against the new bucket as part of its atomic
    # provisioner; the root callback must not open a session that
    # would block this path.
    "config profile create",
    # Recovery from a backup archive: same shape as create — the
    # imported bucket establishes its own session as part of the
    # import flow.
    "config profile import",
    # Diagnostic surface: must operate without a session so the
    # operator can recover from a torn workspace.
    "config repair",
    # Engineer surface: lives under a separate module entrypoint
    # and is not bound by the session-gate either, but the
    # registry includes it explicitly so the active-gate check at
    # the root callback never refuses a diagnostics call.
    "diagnostics",
)


def is_bootstrap_exempt(verb_path: str | None) -> bool:
    """Return whether ``verb_path`` is exempt from the active-session gate.

    Matching is prefix-based against
    :data:`BOOTSTRAP_EXEMPT_VERB_PATHS`. The leading ``aeat`` is
    elided; ``verb_path`` is the dispatched subcommand chain as
    Typer reports it (e.g. ``"config profile create"`` for the
    full operator invocation ``aeat config profile create alice``).

    Args:
        verb_path: Space-separated verb path or ``None`` for the
            bare invocation. ``None`` is treated as non-exempt
            because the bare-invocation landing page reads the
            workflow state and therefore requires a session when
            an active profile resolves.
    """

    if verb_path is None:
        return False
    normalised = verb_path.strip()
    if not normalised:
        return False
    for exempt in BOOTSTRAP_EXEMPT_VERB_PATHS:
        if normalised == exempt or normalised.startswith(f"{exempt} "):
            return True
    return False


__all__ = ["BOOTSTRAP_EXEMPT_VERB_PATHS", "is_bootstrap_exempt"]
