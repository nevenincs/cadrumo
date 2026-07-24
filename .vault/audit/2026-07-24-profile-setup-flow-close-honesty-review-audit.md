---
tags:
  - '#audit'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
  - "[[2026-07-23-profile-setup-flow-adr]]"
  - "[[2026-07-23-tui-wizard-substrate-adr]]"
  - "[[2026-07-23-profile-setup-flow-integration-shape-audit]]"
---

# `profile-setup-flow` audit: `Close honesty review`

## Scope

Fresh-context honesty review of two tightly-coupled plans that landed on `main`
today via PR #617 (`d742ceee7c`, paged TUI wizard epic) and PR #619
(`chore/s29-s30-roundtrip-hardening`): `profile-setup-flow` (the domain wizard
flow, cotejo censal, setup-incomplete lifecycle) and `tui-wizard-substrate`
(the renderer-agnostic FlowEngine, its three frontends, and the migration that
retired the prior one-shot wizard). Both plans declare a fresh-context honesty
review as their own closing verification criterion.

A prior-session memory (`profile-setup-flow-deferral-ledger`, dated today)
claims "Campaign COMPLETE on main... All 35 work steps closed with two-pass
reviews. OPEN fix-forward: S33 (this review) and S37 (a locale AST gate)." That
claim is background context from an unverified prior session, not evidence;
this review treats it as inventory to check, not as inventory that already
closed. Its 21-item deferral ledger (sections A-E) was used as a hunting list,
not trusted verbatim.

The review re-ran real gates against HEAD rather than reading plan checkboxes:
the prompter-singularity AST gate, the cross-frontend parity regression, the
S29/S30 roundtrip and anti-tautology suites, the portable-export schema
roundtrip, the full wizard and flows test packages, the TUI adapter package,
locale parity/honesty, the full `src/cadrumo` collect-only gate, and (partially
— see the findings) the nitpicky Sphinx docs build. Two gate runs turned up
transient red caused by concurrent unrelated peer edits to shared files
(locale catalogues, CLI package); both were confirmed clean on an isolated
re-run seconds later, consistent with the shared-worktree churn this project's
own rules warn about, and are recorded below as due-diligence, not findings.
The review is read-only; no production file was modified.

## Findings

### tui-wizard-substrate-s27-real-work-uncounted | medium | The frontend parity regression is real, substantial, and passing, but the plan still shows it open with no exec record

Plan step `W03.P09.S27` ("Land the parity regression proving the scripted,
line-mode, and full-screen paths produce identical answers and validation
verdicts for a shared definition") is unchecked in
`.vault/plan/2026-07-23-tui-wizard-substrate-plan.md`, and no exec record
exists for it (`.vault/exec/2026-07-23-tui-wizard-substrate/` has records for
every other step but none named `S27`). The work itself is done and good:
`src/cadrumo/application/flows/tests/test_frontend_parity.py` landed in commit
`5ea26c7b0d` ("test(flows): pin scripted, line, and full-screen frontend
parity") and drives all three real frontends — the scripted driver, the line
frontend over real `prompt_toolkit` pipe keystrokes, and the full-screen
`FlowTuiApp` under Textual's headless `Pilot` — with no mocks and no stubbed
engine transitions, asserting structural `FlowState` answers, review-projection
eligibility, and validation message *keys* (never localized prose). Re-run
directly: `2 passed in 21.73s`. This is exactly the class of gap
`plan-closure-requires-exec-records` exists to catch, just inverted from the
usual direction — not a step checked without proof, but real proof landed with
the step left unchecked and untracked, so the plan currently understates its
own progress and the deferral-ledger's "35 steps closed" count is off by at
least one uncounted-but-actually-done step.

### deferral-ledger-open-item-count-is-wrong | medium | The prior-session completion claim undercounts open steps by at least one

The `profile-setup-flow-deferral-ledger` memory states the only two open items
are S33 (this review) and S37 (the tr-constant naming AST gate). At HEAD,
`tui-wizard-substrate` alone has **two** unchecked steps, S27 (see above) and
S29 (see below) — S27 appears nowhere in the ledger's 21 items, sections A
through E. This is precisely the failure mode `aeat-campaign-close-honesty-review`
exists to catch: a self-reported "complete" while real remaining work is
uncounted. It does not indicate hidden functional breakage — S27's substance is
verified done and S29's substance is very likely done (next finding) — but the
STRUCTURAL claim ("all 35 closed except two named items") was inaccurate at the
moment it was written and remains inaccurate at HEAD.

### tui-wizard-substrate-s29-blocker-appears-cleared-but-unconfirmed | low | The docs-build gate could not be re-run to a clean finish inside this review's window, though its named blocker is independently confirmed fixed

S29's exec record documents a real, honestly-triaged peer-owned blocker: all
eight docs-build failures reduced to one signature, a `CadrumoError` subclass
(`cadrumo.application.auth._apoderado.ApoderadoRepresentedNifInvalidError`)
missing its `ErrorCode` registry entry, attributed to a different campaign's
uncommitted working-tree edits at the time, with the step deliberately left
open "until the docs build is re-run green after the peer lands." Grepping
`src/cadrumo/core/errors/registry/_domain_part1.py:649` now shows that exact
class registered, confirming the peer's commit landed. However, re-running
`dev/docs/tests/test_docs_build.py` in this review hit pytest-timeout's own
thread-dump watchdog on `test_sphinx_nitpicky_build_is_clean` (a live Sphinx
subprocess build under heavy concurrent host load from the other agents
active in this shared worktree) without producing a pass/fail verdict. The
step should very likely now be checkable, but this review did not obtain a
green run to confirm it structurally.

### confirmed-clean-under-reload | confirmed | Two gate runs redded from live peer WIP unrelated to this campaign, both confirmed green on isolated re-run

`src/cadrumo/tests/test_parity.py::test_codebase_to_locale_parity` failed
once ("ca/en/es/hu.yml missing 1 codebase key" each) while
`git status` showed all four locale catalogues as actively-modified working-tree
files; a re-run of the same test moments later passed clean. Separately,
`src/cadrumo/application/wizard/tests/test_wizard_translations_resolve.py::test_every_cli_translation_resolves_in_every_locale`
failed once on a missing `cli.ledger.check.link_inconsistency_notice` key
while a large, unrelated set of `src/cadrumo/entrypoints/cli/` files showed as
actively modified (ledger-campaign work, not this campaign's files); re-run in
isolation passed clean, `3 passed`. Neither failure traces to any file this
campaign touches. Recorded per the swarm-orchestration re-run discipline
rather than silently discarded.

### wizard-prompter-singularity-holds | confirmed | The historical third-prompter hazard has a real, non-tautological, passing structural gate

`src/cadrumo/tests/test_wizard_prompter_singularity.py` is exactly the
prevention the project's own `aeat-rag-discovery-mandatory` rule names as
historically defeated (a hand-copied `_QuestionaryTextPrompter` that caught
only `OSError` while the real Windows failure mode is not an `OSError`
subclass). It recomputes two AST-derived rules every run with no stored
baseline and no allowlist: only `application/flows/_line_frontend.py` and
`application/flows/_capability.py` may import `questionary`/`prompt_toolkit`
at runtime, and no class outside those two may declare an `ask`/`ask_text`
method in a module that carries either dependency. Both rules carry
discrimination tests proving they fire on synthetic copies of the exact
historical drift (a `_QuestionaryTextPrompter`, and a class that reaches
`questionary` through an indirect re-export rather than a direct import), plus
an anti-vacuity test pinning that the two canonical modules still exist. `rg`
confirms no `Prompter`-suffixed class and no second `questionary` import
survive in production outside those two files. Re-run: `8 passed in 53.29s`.

### s29-s30-roundtrip-and-portable-export-hold | confirmed | Real encrypted-adapter roundtrips with anti-tautology proofs, independently re-run and passing

`profile-setup-flow` steps S29 and S30 (`ac5b23e369`, `807a51aae2`, both
independently confirmed ancestors of HEAD) satisfy `aeat-roundtrip-discipline`:
divergence facts, the setup-incomplete lifecycle status, and the resume
projection are proven through genuine encrypted-store reloads with every
defaultable field populated non-default (a maximal descendant fixture
including the disabled grade-65/non-cohabiting branch), each paired with an
anti-tautology proof (clearing one persisted subfield, corrupting the manifest
status line, mangling a serialized fact byte) that forces the boundary to fail
when broken. The portable-export test proves no `bundle_schema_version` bump
is warranted under the `PRE_RELEASE` regime by actually round-tripping every
schema surface this campaign added, not by assertion. Re-run:
`test_cotejo_apply.py` + `test_profile_repository.py` +
`test_descendant_persistence.py` + `test_portable_export_schema.py` together,
`48 passed in 94.64s`, matching the exec record's own reported count exactly.

### structural-checks-pass | confirmed | Collection, TUI adapters, CENSO_APPLIED wiring, and both ADR statuses hold at HEAD

`uv run pytest src/cadrumo --collect-only -q`: `13831/17031 tests collected
(3200 deselected)` with zero collection errors, satisfying the plan's
full-tree gate criterion (the exec record's own figure of ~13732 five days
prior is consistent with ongoing peer landings, not regression).
`src/cadrumo/adapters/inbound/tui/tests/`: `45 passed in 48.74s`.
`BucketEventType.CENSO_APPLIED` has a real, singular production emission site
in `application/user_profile/_lifecycle.py` (not the "may be dormant" status
the pre-campaign integration-shape audit flagged as an open question — that
question is resolved). Both `2026-07-23-profile-setup-flow-adr` and
`2026-07-23-tui-wizard-substrate-adr` carry `status: accepted` (not the
`proposed`/"held non-final" state the same pre-campaign audit recorded before
the RAG-confirmation pass it called for).

### s37-and-windows-credential-gate-honestly-scoped | confirmed | S37 is genuinely unimplemented (correctly tracked open); the WinError 1312 environment fact does not apply to this campaign's surface

No AST gate enforcing "every `tr(CONSTANT)` call site's constant name carries
the locale-key naming convention" exists anywhere under
`src/cadrumo/locales/tests/`; S37 is honestly open, matching its unchecked
plan state — no discrepancy here, unlike S27. Separately: this review's
dispatch brief warned that this host's broken Windows credential store
(`WinError 1312`) blocks any test requiring a minted persisted session.
Grepping `application/wizard`, `application/flows`, `application/user_profile`,
and `adapters/inbound/tui` for persisted-session/keyring dependencies finds
exactly two hits, both belonging to the separate, unrelated `login-session`
campaign (`test_login_session.py`, `test_logout_strong_close.py`); the full
wizard and flows suites (`424 passed` outside the two transient peer-noise
reds already addressed above) contain no persisted-session dependency and were
not blocked by anything credential-store-related. Recorded explicitly per this
review's instruction to record non-applicable rules rather than skip silently.

## Recommendations

Check `W03.P09.S27` and author its exec record now — the work is done, tested,
and passing; only the bookkeeping is missing. Doing so also corrects the
deferral ledger's step count.

Re-run `dev/docs/tests/test_docs_build.py` once host load permits a full
Sphinx build to finish inside its timeout, and check `W03.P09.S29` on a
confirmed green — the named blocker is independently verified fixed, so this
is very likely a formality, not a real gap, but it should be observed green
before the checkbox flips.

Implement `W04.P09.S37` (the tr-constant naming AST gate) before declaring
either plan closed — it is the fourth concealment-layer class the deferral
ledger itself names as unresolved, and nothing in this review found it done
elsewhere.

Correct or annotate the `profile-setup-flow-deferral-ledger` memory: its "35
steps closed, only S33/S37 open" claim is inaccurate at HEAD given S27 (done,
uncounted) and S29 (probably done, unconfirmed). A prior-session memory that
asserts campaign completeness should not be treated as verified fact by a
future session without exactly the kind of independent re-check this review
performed.

**Verdict:** not yet structurally complete, but close and low-risk. No
functional defect was found in either plan's shipped surface — the
prompter-singularity, roundtrip, portable-export, collection, and TUI-adapter
gates all independently re-confirmed green, and the one real gap S27
represents is a bookkeeping omission on top of already-correct, already-tested
production code, not missing work. The plan should not be marked complete
until S27 is checked with its exec record, S29 is confirmed green and checked,
and S37 lands — all three are small, well-scoped, and none blocks on this
review's own closure.
