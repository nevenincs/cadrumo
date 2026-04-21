---
tags:
  - "#adr"
  - "#live-submit-excision"
date: 2026-04-18
title: ADR — excise the live-submit CLI surface (charter #197)
status: accepted
issue: wgergely/aeat#116
related:
  - "[[2026-04-18-aeat-filing-detail-fetch-adr]]"
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-12-submission-engine-adr]]"
  - "[[2026-04-16-live-write-test-audit-research]]"
---

# adr — excise the live-submit CLI surface

## context

Charter #197 (produce-verify-export, live submission deferred to
1.0.0) and the live-AEAT-write safety charter (#116) jointly mandate
that the codebase carry **no reachable mechanism** to file a live
return at this point in the roadmap. Audit during the #227 PR
(2026-04-18) found three live-write reachability gaps:

1. **`aeat submission submit` is registered at the default CLI**
   surface — `src/aeat/cli/submission/__init__.py:35-38`. This
   directly violates `.claude/rules/aeat-project-mandates.md`:
   > DO NOT register `aeat submission submit` in the default CLI;
   > it lives in a hidden `aeat live-submit` group gated behind env
   > vars.
2. **`SubmissionEngine.live_transport_supported` defaults to True**
   (`src/aeat/submission/_engine.py:72`), so any caller who omits
   the flag inherits the unsafe default. Only `cli/submission/_helpers.py:189-200`
   explicitly opts to `False`; every other production / test caller
   gets the unsafe default.
3. **`Modelo130Submitter.submit` carries a real
   `await session.click("button#firmar-y-enviar")`**
   (`src/aeat/submission/_submitters/modelo130.py:190`). This is
   the literal "sign and send" click that would file a return.

Multi-layer runtime gates exist (CLI flag, env var, pytest refusal,
typed-phrase confirmation, cert health), so the path is not
one-keystroke away from execution. But the *code path exists and is
discoverable*, which contradicts the "no reachable mechanism"
posture.

This ADR pins the **B-level** remediation (per the user's
2026-04-18 decision): unregister the CLI surface and flip the engine
default to inert. The submitter-level click (#3 above) remains in
place as a future-Option-C target tracked under a follow-up issue —
this ADR does not touch it but adds structural guardrails so it
cannot be reintroduced into the reachable graph without an explicit
opt-in.

## decisions

### D1 — remove `aeat submission submit` from the CLI

Concretely:

- Drop `from .submit import submit_cmd` and the
  `app.command(name="submit", ...)(submit_cmd)` registration from
  `src/aeat/cli/submission/__init__.py`.
- Delete `src/aeat/cli/submission/submit.py`.
- Delete `TestSubmitCommand` from
  `src/aeat/cli/submission/test_cli.py` and replace with a new
  `TestSubmitCommandRemoved` that asserts the CLI no longer exposes
  `submit`.
- Update the package docstring (`cli/submission/__init__.py:1-15`)
  to drop the `submit` listing and explain why (link to this ADR).
- Update the stale comment in `src/aeat/auth/certificate.py:75`
  that references `aeat submission submit --force-expiring-cert`.

**Rationale.** The mandate is explicit and non-negotiable. The
fastest, most defensible remediation is to make the command
genuinely unreachable from the CLI. Programmatic callers that *want*
the live path can still construct the engine with explicit
`live_transport_supported=True` (gated by D2 below) — but no Kent,
no operator, no curious explorer typing `aeat submission --help`
sees a `submit` option.

### D2 — flip `SubmissionEngine.live_transport_supported` default to False

Concretely:

- `src/aeat/submission/_engine.py:72`: change
  `live_transport_supported: bool = True` to
  `live_transport_supported: bool = False`. Update the docstring
  to call out that the default is now safe-by-default (opt-in) and
  that explicit `True` is required to reach the
  per-modelo `submit()` transport.
- `src/aeat/cli/submission/_helpers.py:189-200`: drop the now-
  redundant `live_transport_supported=False` arg from `build_engine`
  (default is False).
- `src/aeat/submission/test_safety_helpers.py:220`: explicitly pass
  `live_transport_supported=True` because the test exercises the
  post-bypass live path.
- Other test sites (`test_engine.py`, `test_live_submission.py`,
  `cli/workflow/test_cli.py`, `workflow/test_engine.py`) already pass
  the param explicitly or use a fake engine — no change required.

**Rationale.** Opt-in defaults are the correct posture for any
irreversible side-effect. Production code that genuinely needs live
transport must say so loudly; default construction yields an inert
engine that raises `AeatLiveTransportUnavailableError` on
`dry_run=False`. Defense in depth without breaking the ability to
exercise the live-safety paths via test bypass.

### D3 — structural guardrails

Concretely:

- New static test
  `src/aeat/cli/submission/test_no_submit_command.py` asserts:
  - `"submit"` is NOT in the registered Typer command names of the
    `aeat submission` sub-app.
  - The string `"button#firmar-y-enviar"` does not appear anywhere
    under `src/aeat/cli/` (the click is a submitter-internal
    detail; it must never leak into the CLI tree).
- New behavioural test in `src/aeat/submission/test_engine.py`
  asserts that a default-constructed `SubmissionEngine` (no
  `live_transport_supported` arg) raises
  `AeatLiveTransportUnavailableError` on
  `submit_draft(..., dry_run=False)`.

**Rationale.** Mechanical enforcement so the violation cannot
quietly reappear in a future PR. The static + behavioural pair
covers both "someone re-adds the registration" and "someone flips
the default back".

### D4 — engine-level live click (`Modelo130Submitter.submit`) is OUT OF SCOPE

The `await session.click("button#firmar-y-enviar")` line at
`src/aeat/submission/_submitters/modelo130.py:190` stays in this
ADR's scope as **inert reachable-by-opt-in only**. After D2 it can
only execute if a caller explicitly passes
`live_transport_supported=True` AND `dry_run=False` AND the env
gate is true AND not under pytest AND the typed-phrase confirmation
succeeds.

The complete excision (delete the click, collapse the engine to
preflight + dry-run) is **Option C** — tracked as a follow-up
issue. Option C requires its own ADR + plan because it permanently
removes the v0.x scaffolding that 1.0.0 will need to reintroduce.

**Rationale.** Scope discipline. Option B closes the reachable-
without-explicit-opt-in surface; Option C is a separate
architectural decision about whether the v1.0 reintroduction
work pays off the cost of re-writing the Playwright walk versus
keeping it dormant.

### D5 — mandate strengthening

Concretely:

- Update `.vaultspec/rules/rules/aeat-project-mandates.md` to
  reference this ADR alongside #116.
- Add an explicit line: "DO NOT add `live_transport_supported=True`
  as a default to any new SubmissionEngine factory; opt-in only."
- Update `docs/coverage/kent-capabilities.md`: the "Live-submit
  (opt-in)" row gets a footnote noting the CLI command is removed
  pending 1.0.0.

**Rationale.** Keeps the mandate file the single source of truth
for what new contributors must respect.

## consequences

- `aeat submission --help` no longer lists `submit`.
- Default `SubmissionEngine()` is inert against live writes; opt-in
  is explicit and grep-able.
- The CLI surface still exposes `preflight`, `dry-run`, `show`,
  `list` — all read-only or local-state operations.
- `Modelo130Submitter.submit` and `_engine._submit_with_transport`
  non-dry-run branch survive as opt-in scaffolding for 1.0.0.
- Static + behavioural tests prevent regression.
- `.vault/audit/` and coverage matrix reflect the strengthened
  posture.
- Out of scope: full Option C removal of the engine live branch,
  the Modelo130 click, and the per-modelo submitter live path.
  Tracked in a separate issue.

## enforcement / review checklist

- [ ] `aeat submission --help` does not list `submit`.
- [ ] `import aeat.cli.submission.submit` raises `ModuleNotFoundError`.
- [ ] `SubmissionEngine()` default-constructed + `submit_draft(dry_run=False)`
      raises `AeatLiveTransportUnavailableError`.
- [ ] `rg -n 'live_transport_supported' src/aeat/` shows no
      production-default True (only test opt-ins).
- [ ] `rg -n 'submit_cmd|aeat submission submit' src/aeat/` shows
      zero hits (only docs / vault references).
- [ ] `cli/submission/test_no_submit_command.py` passes.
- [ ] All previous CLI submission tests (`preflight`, `dry-run`,
      `show`, `list`) still pass.
- [ ] `aeat-project-mandates.md` updated with the new opt-in rule.
- [ ] Coverage matrix reflects the CLI removal.

## out of scope

- Option C — full removal of live-write scaffolding from
  `SubmissionEngine` and `Modelo130Submitter`. Separate issue.
- Reintroduction work for 1.0.0. Will need its own ADR.
- The 4-factor live-submit gate (`AEAT_ALLOW_LIVE_SUBMIT_OPT_IN`,
  `AEAT_LIVE_SUBMIT_ENABLED`, `--i-understand-this-is-real`,
  per-submission prompt) — preserved as defense-in-depth.
