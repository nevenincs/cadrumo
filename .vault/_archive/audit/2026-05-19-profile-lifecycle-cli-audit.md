---
tags:
  - '#audit'
  - '#profile-lifecycle-cli'
date: '2026-05-19'
related:
  - "[[2026-05-19-operator-blind-newcomer-testimony-audit]]"
  - "[[2026-05-19-operator-blind-returning-testimony-audit]]"
  - "[[2026-05-19-operator-blind-dual-testimony-audit]]"
  - "[[2026-05-19-operator-blind-fumbler-testimony-audit]]"
  - "[[2026-05-19-operator-testimonial-audit]]"
  - "[[2026-05-18-profile-lifecycle-cli-adr]]"
  - "[[2026-05-18-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` audit: operator testimony synthesis — pre-alpha disaster classification

## Scope

Five blind-operator persona tests executed against the
``chore/eliminate-shims`` branch on 2026-05-19. Each persona ran the
``aeat`` CLI in an isolated tmp ``AEAT_LOCAL_STORAGE_ROOT`` with
``AEAT_SECRET_STORE_BACKEND=unsecured`` and no source-code access.
Personas: newcomer, returning operator, dual-profile operator,
error-prone fumbler, curious investigator. This document triages
their pain points and reclassifies the feature.

## Verdict

**Pre-alpha. Non-functional from cold start.** The 2026-05-18
cascade-closure plan was reported complete (all phases closed in
the plan document) but every blind operator failed to complete
the most basic task — creating their first profile — without
seeing an 80-line SQLAlchemy traceback. The CLI surface compiles,
lints, audits clean, has full translation coverage, and ships
nine architectural commits' worth of structural work. None of it
matters because the production lifecycle never activates a
session, so every encrypted-column write fails the moment it is
attempted.

This is not a polish issue. This is the substrate not booting.

## Findings (severity 5 = data loss / total block)

### F1 — Cold-start session deadlock (severity 5)

Every CLI command that touches the SQLAlchemy engine crashes with
``NoActiveBucketSessionError`` on a fresh ``AEAT_LOCAL_STORAGE_ROOT``.
Reported by all five personas. The error message routes the
operator to ``aeat config profile switch NAME``, but ``switch``
raises the same error. The error message routes to
``aeat config repair``, but ``repair`` raises the same error
(F4 below). There is no operator-facing bootstrap path.

Root cause (inferred from the unanimous symptom): the
``EphemeralMasterKeyProvider.__enter__`` introduced in commit
``2232b68d`` and the ``activate_session`` contextmanager
introduced in commit ``49af100d`` are never invoked by any
production CLI code path. They are exercised by test fixtures.
The CLI root callback in ``entrypoints/cli/__init__.py`` never
opens a session, never calls ``activate_session(...)``, never
registers a session via ``ctx.with_resource(...)``. Plan Step
P01.S12 ("mount activate_session on the CLI root callback")
landed in some form in the plan but does not fire at runtime.

### F2 — Create / switch / read disagree about where profiles live (severity 5)

Reported by the dual-profile persona. ``profile create alice``
exits 0 and emits ``profile_id alice``. ``profile switch alice``
exits 0 and writes the active-profile pointer file.
``profile show alice`` immediately raises ``Unknown profile:
alice``. ``profile list`` returns at most one profile even when
two were created.

Root cause (inferred): the cascade-closure ADR retired
``WorkflowState.profiles`` in favour of a filesystem manifest
scan (``read_profile_bucket(name)`` checks for
``<root>/buckets/<name>/manifest.toml``). The setup-service
``_provision_bucket_directory_idempotent`` writes the manifest,
but the wizard-driven create path may not invoke setup-service —
it goes through ``register_active_profile`` in
``user_profile/_orchestration.py``, which writes the pointer
file but not the manifest. The read side disagrees with the
write side because they consult different sources of truth.

### F3 — `AEAT_DATABASE_URL` required but undocumented (severity 4)

Reported by the curious investigator. Bare ``aeat`` raises
``aeat_database_url is empty; set AEAT_DATABASE_URL`` and exits.
``AEAT_DATABASE_URL`` is not referenced in any ``--help`` text,
any setup guide, any error-suggestion field, or any env-example.
The Settings ``model_validator`` introduced in commit ``a5220f71``
was supposed to compute the URL from the active-profile pointer
chain, but on cold-start the chain returns empty and the field
stays empty. The engine path raises ``StorageError`` instead of
routing the operator to ``profile create``.

### F4 — Escape hatch welded shut (severity 5)

Reported by the fumbler. ``aeat config repair reset-state --yes``
is the documented recovery hint that every other error message
points to. The verb reads the encrypted ``secure_objects`` table
before deleting it — requiring the very session it is meant to
clear. The recovery path itself fails with
``NoActiveBucketSessionError``. The trap closes around the
operator.

### F5 — Help-text placeholders shipped to operators (severity 2-3)

Reported by the newcomer. ``aeat --help`` opens with literal
``Heading`` and ``Paragraph two roots`` tokens. ``aeat config
--help`` lists ``profile view`` but ``profile view`` raises "No
such command" (P03 deleted the verb, the help-card list was not
regenerated). The translation-key locale fallback emits the
dotted key path as the visible text when no value is set.

### F6 — Six UserWarning lines pollute every CLI invocation (severity 3)

Reported by the curious investigator. Even ``aeat --version``
prints six registry-validation ``UserWarning`` lines before
producing any verb output. Operator-trust erosion before the
operator has typed a single verb.

### F7 — Registry validation blocks silently for 10+ minutes on cold start (severity 3)

Reported by the fumbler. The first CLI invocation from a cold
process re-validates the full AEAT registry with zero progress
output. After 10+ minutes of testing the background subprocess
had produced zero bytes. An operator kills the process within
30 seconds, concludes the tool is broken, and uninstalls.

### F8 — `repair logs` MemoryError on normal-size log file (severity 4)

Reported by the fumbler. ``aeat config repair logs`` raises
``MemoryError`` on a log file that is not unusually large. The
diagnostic surface itself fails to be diagnostic.

### F9 — Destructive verbs lack double-confirm (severity 4)

Reported by the fumbler. ``aeat config profile delete NAME --yes``
does not ask the operator to type the profile name back, despite
the cascade-closure ADR section 1 mandating "double-confirm:
``--yes`` flag plus the operator types NAME back verbatim at a
second prompt". The contract written into the ADR is not enforced
at the verb.

### F10 — `delete` hangs indefinitely (severity 4)

Reported by the dual-profile persona. ``aeat config profile
delete`` without arguments hangs without printing anything.
Likely blocking on a stdin prompt for the double-confirm,
without flushing the prompt text first.

### F11 — Broken `aeat.domain.vat` import crashes every invocation (severity 5)

Reported by the fumbler. The branch contains a stale-rename
defect: ``aeat.application.aggregation._iva_ledger``,
``_oss_ioss``, ``_prorrata``, and ``test_iva_ledger`` all import
from ``aeat.domain.vat``, which does not exist on this branch.
The actual module is ``aeat.domain.iva`` (a recent rename from
the Spanish-stem terminology authority work). Every invocation
of the ``aeat`` console-script entry crashes with
``ModuleNotFoundError: No module named 'aeat.domain.vat'`` during
module import.

This is the root cause of F7. Operators see a 10-minute silent
hang because the registry validation runs first and prints
nothing; the import error then surfaces only after the registry
work completes. The ``CliRunner`` paths used by the unit tests
bypass the production console-script entry and therefore do not
exercise the broken import — the gate that should have caught
this regression does not fire.

Not introduced by the cascade-closure plan; introduced by a
parallel rename commit on ``chore/eliminate-shims`` that
retargeted ``domain.invoices._iva_classification`` to
``domain.iva._invoice_classification`` without updating the
upstream callers. Blast radius extends beyond profile-lifecycle.

## What works (preserve in the rewrite)

The fumbler called out concrete bright spots that should survive
the architectural rebuild:

- NIF checksum validation. Typing ``12345678X`` (wrong check
  letter) produces a clean structured error: ``"expected 'Z',
  got 'X'"``. No traceback. Exact guidance.
- Empty NIF rejection. Clean refusal, helpful suggestion.
- Non-TTY interactive prompter refusal. The wizard correctly
  declines to prompt when stdin is not a TTY and tells the
  operator how to provide values non-interactively.

These three behaviours are the only places the operator
experiences operator-grade quality. Catalogue them as the bar
the rebuild must clear everywhere else.

## Architectural pattern across the findings

All five severity-5 / severity-4 findings cluster around **two
architectural defects**, not ten surface bugs:

**Defect A — Production session lifecycle is unwired.**
The CLI root callback never activates a ``BucketSession``. The
``activate_session`` contextmanager and the
``EphemeralMasterKeyProvider.__enter__`` exist as test fixtures
only. Every column-level encrypt or decrypt operation in
production raises ``NoActiveBucketSessionError`` because no
production code has ever entered the session block.

**Defect B — Five competing sources of truth for "what
profile is active and where does its data live".**
``Settings.aeat_active_profile``, ``Settings.aeat_database_url``
(computed property), ``<root>/active-profile`` pointer file,
``<root>/buckets/*/manifest.toml``, ``WorkflowState`` encrypted
row, and ``_active_session: ContextVar[BucketSession]``. The
create / switch / read paths each consult a different subset and
the subsets disagree silently. The cascade-closure ADR was
supposed to collapse this to one chain (``profile create`` writes
all artefacts atomically; ``profile switch`` updates the pointer
file; ``profile show`` reads the manifest), but the wiring is
incomplete.

## Closure-rescission

The 2026-05-18 cascade-closure plan is hereby **reclassified as
shipped-but-non-functional**. Each phase's structural work
landed but the integration that would make it operate from cold
start did not. The plan stays in the vault for historical
context; the closure status is rescinded. The next document in
this feature's chain is a fresh ``vaultspec-research`` ground
that maps the two defects above to their exact code locations
and proposes the architectural rewrite that resolves them.

The rewrite scope is amplified: any of the five competing state
sources may retire, any production-lifecycle component may be
restructured, the wizard-vs-setup-service duality may collapse,
and ``EphemeralMasterKeyProvider`` may stop being a test fixture
and become the canonical production fallback for unsecured
mode. The CLI surface is not the layer to patch; the substrate
boot sequence is.

## Recommendations

- **Stop**: no further commits to ``chore/eliminate-shims`` that
  attempt to mask the lifecycle defect via CLI-surface mitigation.
  The CLI is downstream of the substrate; patching it absorbs
  bugs that belong elsewhere.
- **Research**: open ``profile-lifecycle-disaster`` research
  feature. Five axes per the coordinator proposal: session-
  activation lifecycle, create/read coherence, CLI bootstrap
  orchestration, state-model coherence, failure-mode operator
  experience. Each axis dispatched as its own sub-agent.
- **ADR**: synthesise research into a single architectural ADR
  that resolves both defects. Permission to retire, fold, or
  rewrite any pre-existing piece of the substrate that the
  research identifies as load-bearing for the defects.
- **Plan + execute**: implement the ADR. Tear out what has to go.
- **Re-test**: dispatch the same five operator personas blind
  against the rebuilt feature. Pass criterion: every persona
  scores ≤1 on every pain point.
