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
    # The profile-session doors. ``login`` IS the authentication gate: it
    # must run with no session at all, and it is the one verb allowed to
    # prompt, so the root callback must not resume or refuse ahead of it.
    # ``logout`` must stay reachable precisely when the session is absent
    # or expired — refusing it with "run `aeat config login`" would strand
    # the operator in a loop — and its idempotent no-op needs no session.
    "config login",
    "config logout",
    # Custody verbs own their own session / recovery / rewrap flow. The
    # root callback must not pre-open the active bucket session before
    # these handlers can resolve passphrase or recovery material.
    # Durable reset owns the pointer transaction, target locks, target-scoped
    # auth sessions, and external journal itself. Root bootstrap must not open
    # an active bucket session or manufacture an active-profile override before
    # start/resume; status reads only the external journal.
    "config reset",
    "config passphrase change",
    "config recover",
    "config recovery",
    # Diagnostic surface: must operate without a session so the
    # operator can recover from a torn workspace.
    "config repair",
    # Profile discovery: enumerating which profiles exist is how an operator
    # learns the label ``config login`` needs, so gating it behind that login
    # is a deadlock — the answer is only reachable once you already know it.
    # ``list_profile_buckets`` reads the plaintext per-bucket ``manifest.toml``
    # files and never unlocks a bucket, so the verb decrypts nothing and needs
    # no session; the same plaintext-only grounds as ``profile archive
    # inspect`` above. Locked profiles still list — status is a manifest field.
    "config profile list",
    # Tombstoning a profile opens its OWN session scoped to the target, the
    # same shape as ``config login`` and the custody verbs above:
    # ``delete_profile_with_lifecycle_span`` wraps the mutation in
    # ``profile_storage_session(profile_id)``. The root callback's session is
    # therefore redundant, and gating on it refused the verb before the body
    # that already knew how to open the right one could run — so an operator
    # could not retire a profile without first logging into it. The label is
    # resolved by a plaintext manifest scan, so an unknown name still refuses
    # as "unknown profile" rather than as a session diagnostic, and ``--yes``
    # remains mandatory.
    "config profile delete",
    # Bundled-registry discovery: lists public modelo metadata and must stay
    # reachable before a profile has been unlocked.
    "app modelo list",
    # Catalogue discovery. Each of these answers "what can this tool do", not
    # "what is in my profile": the ledger pair reads a hardcoded IRPF category
    # catalogue and PATH/localhost probes for optional LLM providers, the
    # portal pair reads the in-memory AEAT portal registry, and the auth pair
    # reads the bundled provider and apoderado-scope catalogues. None resolves
    # a bucket or touches the secure store, so none can answer differently for
    # a logged-in operator — refusing them taught the operator to log in to
    # read a constant.
    "app ledger providers",
    "app ledger categories",
    "app live portals list",
    "app live portals view",
    "config auth providers",
    "config auth apoderado scopes list",
    # The rest of the bundled-registry read surface, on the same grounds as
    # ``app modelo list`` above: these project the compiled registry snapshot
    # and the bundled corpus, never a taxpayer's records. The whole ``app
    # registry`` family is declared read-only in the operator-surface contract
    # and reads only the bundled registry/corpus tree or an operator-supplied
    # plaintext file, so the prefix is exempt as a unit; the ``app modelo``
    # entries are named leaf by leaf because that group also carries the
    # profile-bound ``work`` / ``export`` / ``reconcile`` verbs, which must
    # stay gated. ``review-package verify*`` is deliberately included: it
    # exists for a third-party reviewer who has no Cadrumo profile at all.
    "app registry",
    "app modelo describe",
    "app modelo casilla",
    "app modelo casillas",
    "app modelo formulas",
    "app modelo support-matrix",
    "app modelo review-package verify",
    "app modelo review-package verify-signature",
    "app modelo review-package verify-receipt",
    # Telemetry STATUS reads Settings fields only. Its sibling ``flush`` does
    # decrypt, hence the leaf entry rather than the ``telemetry`` prefix.
    "app diagnostics telemetry status",
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
