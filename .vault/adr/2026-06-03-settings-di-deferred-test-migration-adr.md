---
tags:
  - '#adr'
  - '#settings-di-deferred'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-06-03-plan-triage-approach-adr]]'
  - '[[2026-06-04-settings-di-deferred-research]]'
---

# `settings-di-deferred` deferred test-migration scope archive ADR

## Context

The `2026-05-14-settings-di-plan` landed every production-code Step
(P01-P05 all `[x]`) under the `settings-di` ADR. The plan body
explicitly carved out one scope item as out-of-scope: "Test-suite
mechanical migration of 223 `monkeypatch.setenv` sites is deferred to
a follow-up sprint." No `settings-di` follow-up sprint plan was ever
authored. The plan therefore sits in a state where the body declares
a deferral that has no successor plan to receive it — exactly the
inert-with-deferral shape that the
`2026-06-03-plan-triage-approach-adr` Bucket 3 designates as
requiring an explicit defer-ADR before archive, rather than silent
archival that would lose the deferral contract.

The plan-triage classification pass on 2026-06-03 surfaced this
plan as one of two Bucket 3 entries (alongside
`2026-05-18-profile-lifecycle-cli-plan`). This ADR records the
deferral state, names the campaigns that have de-facto absorbed the
deferred work, and authorises the plan's archive.

## Decision

The deferred test-suite migration of 223 `monkeypatch.setenv`
sites to `override_settings(...)` is **not** revived as a dedicated
follow-up sprint. The work has been absorbed incrementally by two
campaigns that touch the same call sites for adjacent reasons, and
the standing test-hygiene discipline carries the remainder.

The `2026-05-14-settings-di-plan` is approved for archive under
this defer-ADR. The plan body is preserved verbatim under
`.vault/archived/plan/` per the
`vaultspec-core vault feature archive` workflow.

## Inheritors

The deferred `monkeypatch.setenv` → `override_settings` migration
work is absorbed by:

1. **`codebase-solidification` recurring hardening epic
   (`2026-05-28-codebase-solidification-plan`, L4).** The epic's
   `SETTINGS_LEAK` discovery axis (task #96) and the
   `bare-Settings()` module-import sweep enumerate every site that
   reads configuration through a non-`get_settings()` path, including
   the test sites whose `monkeypatch.setenv` is the test-time
   equivalent of the production leak. The epic's rolling cadence
   absorbs the remaining sites as they are touched by adjacent edits.

2. **`secure-storage-production-hardening` (L3, 299 Steps).** The
   secure-storage campaign's Category-B fail-closed migration
   (S273 + the seven follow-up files) rewrote a substantial
   fraction of the `monkeypatch.setenv` sites that touched the
   master-key passphrase and log-dir Settings fields — the very
   fields the original `settings-di-plan` P03 added. The campaign's
   ongoing W12 wave continues to displace setenv-style overrides as
   tests are revisited for fail-closed coverage.

3. **The standing `aeat-quality-gates` rule.** New tests are
   required to use real-behavior overrides rather than `monkeypatch`
   on environment variables; the test-quality discovery sweep
   (task #119) operationalises the rule. Migration of legacy sites
   happens on touch, not as a one-shot sprint.

No standalone `settings-di-followup` plan is necessary; the
three inheritors collectively cover the deferred scope on a
better-distributed cadence than a single mechanical sprint would.

## Why no successor sprint

A dedicated 223-site mechanical migration sprint would:

- Touch every test module in the suite simultaneously, creating an
  enormous merge surface against the many concurrent campaign
  branches active on this worktree.
- Provide no incremental verification gate — the conversion is
  trivially mechanical, but the verification (each test still
  exercises the right precedence chain) is not, and is better
  performed per-site by the agent who already understands that
  test's intent.
- Compete for the same files that the secure-storage and
  codebase-solidification campaigns are continuously editing under
  different intents, producing rebase churn that costs more than
  the migration saves.

The incremental absorption pattern is also consistent with the
operator directive that "every persona-flagged issue is explicitly
in-scope" (process gate task #246) — test-migration debt surfaces
through persona testimonials and is fixed in the same commit that
addresses the surrounding issue.

## Consequences

- The `2026-05-14-settings-di-plan` archives cleanly with a
  recorded deferral contract; no information is lost.
- Future agents looking for "where did the 223 `monkeypatch.setenv`
  sweep go" find this ADR via the archived plan's `related:` graph
  and the three inheritor links above.
- The `codebase-solidification` epic carries the standing obligation
  to surface remaining `monkeypatch.setenv` clusters in its rolling
  audit findings, classifying each as in-scope-on-touch rather than
  requiring a dedicated sprint.
- If a future regression demonstrates that incremental absorption is
  not sufficient (e.g. a `Settings` field whose `monkeypatch.setenv`
  sites systematically bypass the override seam), a new ADR may
  re-open the dedicated-sprint approach for that specific field.

## Status

Accepted. Archive of `2026-05-14-settings-di-plan` authorised on
landing of this ADR. The PM dispatches
`vaultspec-core vault feature archive settings-di` after the
incoming-references discovery pass mandated by
`vaultspec-archive-discipline.builtin.md`.
