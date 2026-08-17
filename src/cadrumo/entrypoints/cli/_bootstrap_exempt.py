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
  (``config profile create``), a state-free diagnostic (``--version``,
  ``--help``, ``config repair`` family), or a verb that explicitly
  operates on plaintext fingerprints rather than decrypted payloads.

The registry is referenced from the CLI root callback at active-gate
time. The matching is full-path-prefix: a request to
``aeat config profile create alice`` matches the exempt entry
``config profile create``.

Why the justifications are DATA rather than prose
-------------------------------------------------

Every entry once carried a free-prose comment stating why it belonged. Prose
here rots silently and is then *inherited* rather than re-derived, which is
worse than no comment at all: a reader who would have checked accepts a stated
reason. Three failures of exactly that shape are on record --- a justification
citing a test that had been deleted out from under it, a justification asserting
a plaintext manifest read that had stopped happening, and a justification
describing a "pair" of catalogue verbs after one of the two had been deleted.
All three were true when written; none failed anything when it stopped being
true, because none of it was executable.

So each exemption is now a :class:`BootstrapExemption` record whose checkable
claims are fields a gate reads:

- ``criterion`` names WHICH membership rule above the entry satisfies. It is a
  closed enum, so an entry cannot belong for an unnamed reason.
- ``cites_verbs`` and ``cites_tests`` carry every other verb and test the
  justification leans on. A cited verb that stops resolving, and a cited test
  that is deleted, both red the gate. This is the class that failed three times.
- ``subtree`` declares, for a PREFIX entry, exactly which descendant leaves the
  exemption carries today. A verb added under an exempt prefix changes the live
  subtree and reds the gate, so it cannot inherit the exemption silently ---
  the failure mode prefix matching invites.
- ``asserts_family_read_only`` mechanises the one structural claim some entries
  make about the operator-surface contract.

``note`` is the residue: the part of the reasoning that is judgement, not fact.
**It is not verified by anything and must not be read as if it were.** Keep it
to the criterion --- "needs no session", "decrypts nothing", "gating it would
deadlock the operator" --- which stays true across refactors of how the verb
achieves it. Where a mechanism genuinely matters, cite it in ``cites_verbs`` /
``cites_tests`` so it is gated, rather than asserting it here where it is not.

The first membership criterion is behavioural and so is executable in principle
--- drive the verb against a pristine storage root and require it to answer.
``config repair`` is covered that way. Generalising it to the read-only classes
needs a signal that separates "refused for want of a session" from "failed for
an unrelated reason", which the current CLI surface does not expose distinctly
enough to gate on; until it does, that criterion is carried by review.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExemptionCriterion(StrEnum):
    """Which membership rule an exemption satisfies.

    Closed by construction: an entry cannot be admitted for an unnamed reason,
    and a reader can group the registry by why its entries belong rather than
    by trusting each one's prose separately.
    """

    FIRST_RUN_DEADLOCK = "first_run_deadlock"
    """No profile exists yet, so demanding an active one is a deadlock."""

    SESSION_DOOR = "session_door"
    """The verb IS the session boundary; the gate cannot run ahead of it."""

    TORN_STATE_RECOVERY = "torn_state_recovery"
    """The verb is reached precisely when the profile will not open."""

    DISCOVERY_DEADLOCK = "discovery_deadlock"
    """It answers the question the operator must answer BEFORE logging in."""

    BUNDLED_CATALOGUE = "bundled_catalogue"
    """It projects bundled or compiled data, never a taxpayer's records."""

    CONFIGURATION_ONLY = "configuration_only"
    """It answers from deployment configuration, not from the secure store."""

    OPERATOR_SUPPLIED_ARTEFACT = "operator_supplied_artefact"
    """It reads only files and keys the caller passes on the command line."""


@dataclass(frozen=True, slots=True)
class BootstrapExemption:
    """One exemption from the active-profile session gate.

    Attributes:
        verb_path: The full verb path as the operator types it, minus the
            ``aeat`` executable token. Prefix-matched at dispatch.
        criterion: The membership rule this entry satisfies.
        note: Unverified prose. Judgement, not fact; nothing checks it.
        subtree: For a PREFIX entry, the descendant leaf paths relative to
            ``verb_path`` that the exemption carries. Empty for a leaf entry.
        cites_verbs: Other verb paths the justification leans on. Each must
            resolve against the live command tree.
        cites_tests: Test function names the justification leans on. Each must
            exist in the test tree.
        asserts_family_read_only: The entry claims its operator-surface command
            family is declared read-only. Checked against the live contract.
    """

    verb_path: str
    criterion: ExemptionCriterion
    note: str
    subtree: tuple[str, ...] = ()
    cites_verbs: tuple[str, ...] = ()
    cites_tests: tuple[str, ...] = ()
    asserts_family_read_only: bool = False


@dataclass(frozen=True, slots=True)
class LoginGatedVerb:
    """A verb that MUST NEVER be granted a bootstrap exemption.

    The registry's negative space. An exemption list records what is let
    through; without a companion record of what is deliberately held back, a
    later sweep that re-derives the admission rule readmits the exception,
    because the exception was never expressible in that rule.

    Attributes:
        verb_path: The full verb path this refusal binds to. It may name a verb
            the tree does not register yet: the refusal is what governs the
            surface when it lands.
        reason: Why the mechanical admission rule must not be allowed to
            readmit it.
    """

    verb_path: str
    reason: str


#: Verbs the exemption rule must never readmit, with the grounds for refusing.
#:
#: **A verb whose OUTPUT leaves the encrypted store must stay login-gated,
#: because a target-scoped unlock does not establish recency.** The login gate
#: demands a session whose idle and absolute deadlines have not elapsed. A verb
#: that names its own target and unlocks that bucket itself satisfies every
#: mechanical test the target-scoped exemptions are admitted on, and still
#: establishes nothing about how recently the operator authenticated. What
#: distinguishes these verbs is their OUTPUT, not their plumbing.
#:
#: This principle was carried once by a source comment that justified itself by
#: citing a test. The test was deleted in an unrelated sweep, then the comment
#: was deleted with the surrounding block, and the principle survived nowhere.
#: It is data now, and ``test_login_gated_verbs_never_exempt.py`` enforces it.
#:
#: The profile restore, export and import surface is being rebuilt. The first
#: two paths below are the ones the operator-surface contract declares for it;
#: a rename of the declared command reds the gate rather than silently retiring
#: the refusal.
#:
#: The list is NOT limited to that surface, and the third entry says why in its
#: own reason: a verb can need a currently-valid login for a reason other than
#: its output leaving the encrypted store. Each entry states the ground it
#: stands on, because a single shared justification would silently extend to a
#: verb it does not actually fit.
LOGIN_GATED_VERB_PATHS: tuple[LoginGatedVerb, ...] = (
    LoginGatedVerb(
        verb_path="config profile archive export",
        reason=(
            "Emits a portable copy of the profile's financial records. It qualifies for a "
            "target-scoped exemption on the mechanical reading, exactly as its rename and "
            "duplicate siblings do, which is why the refusal has to be recorded rather than "
            "merely observed: the reasoning that frees those siblings readmits this verb "
            "unless something says otherwise. Operator directive, 2026-08-03."
        ),
    ),
    LoginGatedVerb(
        verb_path="config profile export",
        reason=(
            "Same class as the archive export: its output is a copy of profile state leaving "
            "the encrypted store, so it needs a currently-valid login and not merely the "
            "ability to unlock the named target."
        ),
    ),
    LoginGatedVerb(
        verb_path="config profile delete",
        reason=(
            "Recorded for a DIFFERENT reason from its two siblings above, and the difference "
            "matters because the output-leaves-the-store reasoning that gates them does not "
            "reach this verb: nothing leaves the store, the capsule is destroyed in place. "
            "What gates it is that it is irreversible and needs no target unlock at all - the "
            "custody primitives destroy a capsule without opening it - so the mechanical "
            "reading that frees a target-scoped verb frees this one most easily of the three, "
            "and it is the one where a wrongly-granted exemption costs a taxpayer their "
            "encrypted financial history rather than a redundant copy of it. The absence of an "
            "exemption is the whole protection; this entry is what keeps the absence deliberate."
        ),
    ),
)


#: Every bootstrap exemption, with its criterion and its checkable citations.
BOOTSTRAP_EXEMPTIONS: tuple[BootstrapExemption, ...] = (
    BootstrapExemption(
        verb_path="config profile create",
        criterion=ExemptionCriterion.FIRST_RUN_DEADLOCK,
        note=(
            "The operator has no profile yet and must be able to create one, so demanding "
            "an active profile first is a deadlock. The root callback must not open a "
            "session ahead of the verb that brings the first bucket into existence."
        ),
    ),
    BootstrapExemption(
        verb_path="config profile restore",
        criterion=ExemptionCriterion.TORN_STATE_RECOVERY,
        note=(
            "Republishes a capsule the operator holds on disk after a disk failure or an "
            "interrupted publication. The profile an active-session gate would demand is the "
            "one being restored, so gating it is a deadlock in the literal sense. It grants "
            "nothing either: the caller must already hold both the capsule bytes and a "
            "credential that opens them, so the session it skips would prove something it "
            "already had to prove to get this far."
        ),
    ),
    BootstrapExemption(
        verb_path="config login",
        criterion=ExemptionCriterion.SESSION_DOOR,
        note=(
            "This IS the authentication gate. It must run with no session at all, and it is "
            "the one verb allowed to prompt, so the root callback must neither resume nor "
            "refuse ahead of it."
        ),
    ),
    BootstrapExemption(
        verb_path="config logout",
        criterion=ExemptionCriterion.SESSION_DOOR,
        note=(
            "Must stay reachable precisely when the session is absent or expired. Refusing "
            "it with 'run `aeat config login`' would strand the operator in a loop, and its "
            "idempotent no-op needs no session."
        ),
        cites_verbs=("config login",),
    ),
    BootstrapExemption(
        verb_path="config reset",
        criterion=ExemptionCriterion.TORN_STATE_RECOVERY,
        note=(
            "Durable reset owns the pointer transaction, the target locks, the target-scoped "
            "auth sessions and the external journal itself. Root bootstrap must not open an "
            "active bucket session or manufacture an active-profile override before "
            "start/resume; status reads one journal without resuming it."
        ),
        subtree=("resume", "start", "status"),
    ),
    BootstrapExemption(
        verb_path="config repair",
        criterion=ExemptionCriterion.TORN_STATE_RECOVERY,
        note=(
            "The diagnostic surface an operator reaches when the workspace is torn. Gating "
            "it behind the session it exists to repair welds the escape hatch shut, which "
            "is the disaster the sessionless-on-a-fresh-root probe was written against."
        ),
        subtree=(
            "connectivity",
            "integrity objects",
            "integrity registry",
            "logs",
            "profile",
            "quarantine",
            "reset-progress",
        ),
        cites_tests=("test_repair_verb_runs_clean_without_session_on_fresh_root",),
    ),
    BootstrapExemption(
        verb_path="config profile list",
        criterion=ExemptionCriterion.DISCOVERY_DEADLOCK,
        note=(
            "Enumerating which profiles exist is how an operator learns the label "
            "`config login` needs, so gating it behind that login is a deadlock: the answer "
            "is only reachable once you already know it. The listing decrypts nothing and "
            "needs no session, so a locked profile still lists."
        ),
        cites_verbs=("config login",),
    ),
    BootstrapExemption(
        verb_path="config storage",
        criterion=ExemptionCriterion.TORN_STATE_RECOVERY,
        note=(
            "The storage tree is the container every profile sits inside, so the whole "
            "family answers questions that exist before any profile does. Gating it behind "
            "a login is the same deadlock: an operator whose profile will not open is "
            "exactly the one who needs to be told where their data is. `reclaim` is a "
            "mutation and is exempt on the same grounds -- the areas holding durable state "
            "are refused outright by its own guard, so what it can reach is root-level "
            "regenerable material, never a bucket's encrypted state."
        ),
        subtree=("check", "init", "list", "reclaim", "show"),
        cites_verbs=("config profile list",),
    ),
    BootstrapExemption(
        verb_path="app ledger categories",
        criterion=ExemptionCriterion.BUNDLED_CATALOGUE,
        note=(
            "Answers 'what can this tool do', not 'what is in my profile': the spending and "
            "IRPF category catalogue is compiled in. It resolves no bucket and touches no "
            "secure store, so it cannot answer differently for a logged-in operator, and "
            "refusing it taught the operator to log in to read a constant."
        ),
    ),
    BootstrapExemption(
        verb_path="app live portals list",
        criterion=ExemptionCriterion.BUNDLED_CATALOGUE,
        note="Projects the in-memory AEAT portal registry. No bucket, no secure store.",
    ),
    BootstrapExemption(
        verb_path="app live portals view",
        criterion=ExemptionCriterion.BUNDLED_CATALOGUE,
        note="Resolves one portal from the same in-memory registry as the list verb.",
        cites_verbs=("app live portals list",),
    ),
    BootstrapExemption(
        verb_path="config auth providers",
        criterion=ExemptionCriterion.BUNDLED_CATALOGUE,
        note="Lists the bundled authentication-provider catalogue. Resolves no bucket.",
    ),
    BootstrapExemption(
        verb_path="config auth apoderado scopes list",
        criterion=ExemptionCriterion.BUNDLED_CATALOGUE,
        note="Lists the bundled apoderado-scope vocabulary. Resolves no bucket.",
    ),
    BootstrapExemption(
        verb_path="app registry",
        criterion=ExemptionCriterion.BUNDLED_CATALOGUE,
        note=(
            "Projects the compiled registry snapshot and the bundled corpus, never a "
            "taxpayer's records. The prefix is exempt as a unit because the whole family is "
            "declared read-only in the operator-surface contract."
        ),
        subtree=(
            "citations list",
            "citations verify",
            "citations view",
            "diff-revisions",
            "inspect",
            "manuals list",
            "manuals rules",
            "manuals verify",
            "manuals view",
            "verify",
            "verify-filed-state",
        ),
        asserts_family_read_only=True,
    ),
    BootstrapExemption(
        verb_path="app modelo list",
        criterion=ExemptionCriterion.BUNDLED_CATALOGUE,
        note=(
            "Bundled-registry discovery: public modelo metadata, reachable before a profile "
            "has been unlocked. The `app modelo` group is named leaf by leaf rather than by "
            "prefix because it also carries the profile-bound work, export and reconcile "
            "verbs, which must stay gated."
        ),
    ),
    BootstrapExemption(
        verb_path="app modelo describe",
        criterion=ExemptionCriterion.BUNDLED_CATALOGUE,
        note="Registry-snapshot projection, on the same grounds as `app modelo list`.",
        cites_verbs=("app modelo list",),
    ),
    BootstrapExemption(
        verb_path="app modelo casilla",
        criterion=ExemptionCriterion.BUNDLED_CATALOGUE,
        note="Registry-snapshot projection, on the same grounds as `app modelo list`.",
        cites_verbs=("app modelo list",),
    ),
    BootstrapExemption(
        verb_path="app modelo casillas",
        criterion=ExemptionCriterion.BUNDLED_CATALOGUE,
        note="Registry-snapshot projection, on the same grounds as `app modelo list`.",
        cites_verbs=("app modelo list",),
    ),
    BootstrapExemption(
        verb_path="app modelo formulas",
        criterion=ExemptionCriterion.BUNDLED_CATALOGUE,
        note="Registry-snapshot projection, on the same grounds as `app modelo list`.",
        cites_verbs=("app modelo list",),
    ),
    BootstrapExemption(
        verb_path="app modelo support-matrix",
        criterion=ExemptionCriterion.BUNDLED_CATALOGUE,
        note="Registry-snapshot projection, on the same grounds as `app modelo list`.",
        cites_verbs=("app modelo list",),
    ),
    BootstrapExemption(
        verb_path="app modelo review-package verify",
        criterion=ExemptionCriterion.OPERATOR_SUPPLIED_ARTEFACT,
        note=(
            "Deliberately exempt: it exists for a third-party reviewer who has no Cadrumo "
            "profile at all. An integrity check over a package the caller passes by path."
        ),
    ),
    BootstrapExemption(
        verb_path="app modelo review-package verify-signature",
        criterion=ExemptionCriterion.OPERATOR_SUPPLIED_ARTEFACT,
        note=(
            "Authenticity check over an operator-supplied package, signature envelope and "
            "public key. Only the signing verbs mint or read keypairs from the secure store."
        ),
        cites_verbs=("app modelo review-package verify",),
    ),
    BootstrapExemption(
        verb_path="app modelo review-package verify-receipt",
        criterion=ExemptionCriterion.OPERATOR_SUPPLIED_ARTEFACT,
        note="Counter-signature check over the same operator-supplied inputs.",
        cites_verbs=("app modelo review-package verify-signature",),
    ),
    BootstrapExemption(
        verb_path="app diagnostics telemetry status",
        criterion=ExemptionCriterion.CONFIGURATION_ONLY,
        note=(
            "Answers from deployment configuration and needs no session. The entry is a LEAF "
            "rather than the `app diagnostics telemetry` prefix on purpose, so its sibling "
            "stays gated: exempting the prefix would carry that sibling with it silently, "
            "which is the failure mode prefix matching invites."
        ),
        cites_tests=("test_matching_stays_prefix_based_so_a_leaf_entry_does_not_carry_its_siblings",),
    ),
)


#: Bootstrap-exempt verb paths, derived from the records above so the data the
#: root callback matches on and the data the gates check can never diverge.
BOOTSTRAP_EXEMPT_VERB_PATHS: tuple[str, ...] = tuple(exemption.verb_path for exemption in BOOTSTRAP_EXEMPTIONS)


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


__all__ = [
    "BOOTSTRAP_EXEMPTIONS",
    "BOOTSTRAP_EXEMPT_VERB_PATHS",
    "LOGIN_GATED_VERB_PATHS",
    "BootstrapExemption",
    "ExemptionCriterion",
    "LoginGatedVerb",
    "is_bootstrap_exempt",
]
