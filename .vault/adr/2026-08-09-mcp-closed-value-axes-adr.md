---
tags:
  - '#adr'
  - '#mcp-closed-value-axes'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:ac5fcfc14fd7e32cf997d5a37aa0908921b4ce3395f48b8ac9177d5addb41bd3'
related:
  - "[[2026-08-08-mcp-closed-value-axes-audit]]"
---

# `mcp-closed-value-axes` adr: `Closed-value CLI axes declare their enum; typed refusals remain programmatic backstops` | (**status:** `accepted`)

## Problem Statement

A CLI option over a closed value set can refuse a bad token in two places, and both mechanisms already ship here.

The **boundary** mechanism declares the enum as the Typer parameter type, so click renders a `Choice`, refuses at parse time listing the accepted values, and the MCP input-schema builder emits a JSON `enum` the agent-operator reads *before* calling.

The **handler** mechanism keeps the parameter as `str` and validates inside the command body, raising a typed, registry-bound error that carries its own `ErrorCode`, category and `default_suggestion`.

When both are available for the same axis, which wins? The question surfaced on `config auth diagnostics report --phone-state`, whose four accepted values are a static `StrEnum` while an unrecognised value raises the registry-bound `REFUSED_AUTH_DIAGNOSTIC_PHONE_STATE`. It is not specific to that verb: every closed-value axis on this CLI can be built either way, and roughly a hundred bare-string axes remain undecided.

## Considerations


The two mechanisms are not symmetric in *when* they inform the caller, and on this CLI that asymmetry is the whole decision. The operator is an autonomous agent that reads the MCP input schema before invoking; a boundary declaration puts the accepted set in that schema, while a handler-side refusal can only answer after a call has already been made with a guessed value.

The counter-consideration is that a typed, registry-bound error is a richer artefact than a parse failure -- it carries a category, a `retryable` flag, a `runbook_id` slot and a `default_suggestion`. Weighing the two honestly required measuring what a click refusal actually emits rather than assuming it degrades to a bare usage string, which is what the constraints section records.

A third consideration is blast radius. Roughly a hundred bare-string axes share this shape, so whichever way the decision goes it is a standing instruction applied many times by future authors, not a single edit. That argues for a rule with explicit, checkable preconditions rather than a bare preference.


## Considered options

**A. Boundary wins; the typed error stays as a programmatic backstop.** Declare the enum on the Typer parameter. The application-level guard keeps raising its typed error for callers that are not the CLI.

**B. Handler wins for any axis that already has a registry-bound error.** Leave the parameter `str` wherever a typed refusal exists, on the grounds that the richer error is the better operator experience.

**C. Case-by-case, no rule.** The status quo that produced the current mix.

## Constraints

The decisive constraint was measured rather than assumed, because option B rests entirely on a premise that turns out to be false.

**A click `Choice` refusal already flows through the shared error envelope.** Invoking a pinned axis with a bad token emits the full typed document -- `schema_version`, `command`, `status="error"`, `notices`, and a registry-bound `error.code` of `REFUSED_CLI_BOUNDARY` -- and exits 2, exactly as a handler-raised refusal does. Pinning therefore costs **no** envelope contract, no `status`/`ExitCode` lock-step, and no notice spine. The only difference is which error code is emitted, and whether a `default_suggestion` rides along.

Two further constraints bound the decision:

- The architecture rules already require an enum-typed Typer parameter for a closed set, and permit a late refusal only for axes whose accepted set depends on **dynamic registry data** -- and even then it must list that set. A statically-known `StrEnum` is not such an axis.
- The agent-operator reads the MCP input schema before calling. A handler-side refusal, however well-worded, arrives only after a guess has already been made.

## Implementation

For an axis whose accepted set is a statically-known `StrEnum`, declare that enum as the Typer parameter type. Delete the hand-rolled parse in the command body and any locale key that existed only to phrase its refusal.

**Do not delete the application-level guard.** It moves from being the CLI's validator to being the backstop for programmatic callers, and keeps its own tests. This mirrors the standing registry-binding treatment, where build-time validation is authoritative and resolve-time helpers remain as backstops.

Three checks gate every promotion, and the last two are properties of the code being deleted rather than of the type:

1. **Value containment** -- the enum covers every value accepted on the success path.
2. **No instructive out-of-set refusal** -- nothing downstream depends on receiving a value *outside* the set in order to answer well.
3. **No input normalisation** -- the deleted parser did not case-fold, strip, or rewrite separators. Where it did, pass `click_type=case_insensitive_choice(EnumClass)`, which preserves both the accepted spellings and the enum-typed parameter.

Check 2 carries a standing exception with real weight on this codebase: where the CLI deliberately accepts a wider set so it can explain what the application does not handle -- ceded autonomic modelos, foral tax regions, LIFO inventory valuation -- the axis stays open and is recorded as an `instructive-guard` exemption.

The worked example is `--phone-state`, now enum-typed; `AuthDiagnosticPhoneStateError` survives untouched in `record_auth_diagnostic_phone_state`.

## Rationale

Option B was the intuitive answer and the measurement killed it. The typed refusal appeared to buy a richer contract; it buys an error *code* and sometimes a suggestion, on top of an envelope both paths already produce. Set against that, the boundary declaration enumerates the accepted values in the refusal itself, and -- decisively -- publishes them in the schema the agent reads *before* it calls. On this CLI the operator is an autonomous agent, so information that arrives only after a wrong call is worth much less than information that prevents it.

Option C is what produced a surface where a hundred-odd equivalent axes are split between the two mechanisms for no recorded reason, and where the same concept is case-insensitive on one verb and case-sensitive on its sibling.

The backstop clause is what makes A safe rather than merely tidy. Nothing is deleted that another caller depends on: the typed error keeps its registry entry, its tests, and its role for every non-CLI path. The CLI simply refuses earlier and with more information.

## Consequences

An axis-specific error code stops being reachable *through the CLI* for pinned axes; a caller keying on `REFUSED_AUTH_DIAGNOSTIC_PHONE_STATE` from a CLI invocation now sees `REFUSED_CLI_BOUNDARY`. Both are registry-bound refusals in the same envelope with the same exit code, and no shipped surface keys on the narrower code.

The promotion is not mechanical, and this ADR should not be read as licence to sweep. Checks 2 and 3 are invisible at the declaration site -- the guard sits in the command body, often several frames away -- and this campaign shipped one regression by pinning an axis whose out-of-set values reached a legally-grounded redirect. The three checks are the deliverable as much as the decision is.

Enforcement is `entrypoints/mcp/tests/test_closed_value_axis_gate.py`, which detects the shape mechanically and requires each occurrence to be pinned or to carry an exemption naming which check exempts it. `unadjudicated` is a permitted, visible classification: it records that nobody has run the checks yet, and is explicitly not a claim that the site is correct.
