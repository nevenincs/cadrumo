"""Typed registry of bootstrap-exempt CLI verb paths.

A bootstrap-exempt verb runs **without** an active
:class:`BucketSession`.
The CLI root callback skips the session open for these verbs; every other verb
is active-gated and refused with a translated
:class:`CliRefusedBoundaryError` when no active
profile resolves.

The exemption list is the seam between the CLI transport layer and
the application's lifecycle expectation. Each entry names the full
verb path as the operator would type it.

Membership criteria:

- The verb must function correctly on a fresh ``CADRUMO_LOCAL_STORAGE_ROOT``
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

# Bootstrap-exempt verb paths (Tuple[str, ...] — the leading 'cadrumo' is implicit).
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
    # Recovery from a sealed full-custody archive: same shape as
    # ``config profile import`` — BucketMaintenanceService.import_
    # provisions and opens its own session as part of the restore.
    "config profile archive import",
    # Read-only header inspection of a sealed archive file. Delegates
    # to the plaintext-header reader only (no decryption, no bucket
    # session); must stay reachable even when an unrelated profile is
    # already active and locked, or before any profile has ever been
    # created.
    "config profile archive inspect",
    # Custody verbs own their own session / recovery / rewrap flow. The
    # root callback must not pre-open the active bucket session before
    # these handlers can resolve passphrase or recovery material. The
    # profile-switch verb opens the target bucket session itself. Logout
    # must remain pointer-sourced so the root callback does not manufacture
    # an active-profile override that the application correctly refuses.
    "config switch",
    "config profile logout",
    "config rekey",
    "config recover",
    "config show-recovery",
    "config verify-recovery",
    # Diagnostic surface: must operate without a session so the
    # operator can recover from a torn workspace.
    "config repair",
    # Bundled-registry discovery: lists public modelo metadata and must stay
    # reachable before a profile has been unlocked.
    "app modelo list",
    # Engineer surface: lives under a separate module entrypoint
    # and is not bound by the session-gate either, but the
    # registry includes it explicitly so the active-gate check at
    # the root callback never refuses a diagnostics call.
    "diagnostics",
)


def is_bootstrap_exempt(verb_path: str | None) -> bool:
    """Return whether ``verb_path`` is exempt from the active-session gate.

    Matching is prefix-based against
    :data:`BOOTSTRAP_EXEMPT_VERB_PATHS`.
    The leading ``cadrumo`` is elided; ``verb_path`` is the dispatched subcommand
    chain as Typer reports it (e.g. ``"config profile create"`` for the full
    operator invocation ``aeat config profile create alice``).

    Args:
        verb_path: Space-separated verb path or ``None`` for the
            bare invocation. ``None`` is treated as exempt:
            bare invocation (no subcommand, only top-level flags
            like ``--language``, ``--format``, ``--help``,
            ``--version``) is a metadata-emitting introspection
            surface analogous to ``--help``, and does not require
            an active bucket session. The render layer's resolution
            chain handles ``--language`` from the explicit CLI flag
            without needing the profile envelope to be unlocked.

    Returns:
        ``True`` if ``verb_path`` is ``None`` (bare invocation) or
        matches a bootstrap-exempt prefix, ``False`` otherwise.
    """
    if verb_path is None:
        return True
    normalised = verb_path.strip()
    if not normalised:
        return True
    return any(normalised == exempt or normalised.startswith(f"{exempt} ") for exempt in BOOTSTRAP_EXEMPT_VERB_PATHS)


__all__ = ["BOOTSTRAP_EXEMPT_VERB_PATHS", "is_bootstrap_exempt"]
