---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:44ca731d90081bc43ea97f492855972aec6fab1ac8e3c3f6513d5afdff529e25'
step_id: 'S44'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# THIS ROW IS NOW STARTABLE. ITS STATED BLOCKER WAS DISCHARGED ON 2026-08-12 AND THE ROW'S OWN not-startable HEADER IS SUPERSEDED BY THIS MEASUREMENT. The chain this row described bottom-up was that flipping the flags needs the automatic lane, the lane needs the fail-open FX door closed, closing the door needs the population a refusal would catch to be counted, counting it needs tests to reach the door, and reaching it needs the registry to LOAD, which needed the frozen producer-key migration landed by its author rather than by us. THE REGISTRY NOW LOADS. The registry verify verb exits 0 over 73 modelos, 565 application links and 82 verification expectations, so the bottom of the chain is discharged and it was discharged by its author exactly as the row required. THE DOOR IS CONFIRMED REACHABLE AND CONFIRMED FAIL-OPEN. At least ten test modules reference the ECB provider, spanning outbound fx, application aggregation, application invoices, application ledger, domain currency and domain invoices, and the provider carries NO live-call guard whatsoever, no live-tests-enabled check, no skip, no refusal and no offline branch, so nothing today prevents a test reaching the live European Central Bank Data Portal. WHAT REMAINS IS THE ROW'S ORIGINAL WORK IN ITS ORIGINAL ORDER, now unblocked at every step. Count the population a refusal would catch by instrumenting the provider to record rather than perform a live lookup, close the door on that evidence, add the new lane selecting integration while excluding serial and perf and external_tool and os_keychain and resident_service, and only then flip the four flags. THE ORDERING REMAINS NON-NEGOTIABLE and its middle state remains actively harmful for the reason the row already gives, that the live dependency is CONTAINED today by the lane being non-blocking and dispatch-only, so an automatically-triggered lane before the door is closed converts a contained dependency into a per-push external call, which is strictly worse than the state it fixes. THE MARKER FIX REMAINS UNAVAILABLE and the row already measured why, that all four gates genuinely cross architectural layers, so re-marking any of them unit would assert something false in exchange for routing convenience and the fix is the new lane rather than a re-marking. This row also gates S40, which is its flip half and must not be closed independently

## Scope

- `pyproject.toml and .github/workflows/ci.yml and the four named gate modules and src/cadrumo/adapters/outbound/fx`

## Description

- Confirm the registry-verify precondition is discharged at HEAD (73 modelos, 565 application links, 82 verification expectations, exit 0).
- Locate every production and test call site of the ECB provider by discovery, not assumption: the ten-plus modules the row names, plus a broader sweep for CLI composition roots that hardcode the default provider with no injection seam.
- Independently design and implement a live-call guard (refuse a pytest-driven lookup without an explicit opt-in) and measure the population it would catch, before discovering that a concurrent commit had already landed the identical fix.
- Confirm against HEAD, per the worktree-safety protocol, that the concurrent commit's code is byte-identical to the independently-derived fix, rather than assuming staleness or re-landing it.
- Re-run the measurement against the landed commit to corroborate its correctness as independent verification, not as authorship.
- Confirm the landed guard does not regress the modules that already inject a deterministic `RateFetch` stub.

## Outcome

**This row's code landed in `4b98e1dc09` ("fix(fx): refuse a pytest-driven live ECB lookup without explicit opt-in"), authored by a concurrent agent, not by this row's own work.** This record does not claim that commit and does not re-land any part of it. What follows is independent corroborating evidence: this row's own investigation, worked in parallel and unaware of the concurrent commit, arrived at code that `git diff HEAD` showed to be byte-identical once discovered, and the measurements below were taken against the landed commit to verify it is correct and complete, not to justify writing it again.

The landed guard lives in the ECB provider's default transport: a pytest-driven call refuses with a typed `ExchangeRateProviderError` unless `Settings.live_tests_enabled` opts in, mirroring the existing `AeatAccessGate` pytest-detection predicate (`PYTEST_CURRENT_TEST` env marker or `pytest` importable in-process) without reusing that AEAT-named class for a non-AEAT external service.

Independent discovery (before finding the concurrent commit) found thirteen modules reaching the live host transitively through the `revolut-multi.csv` multi-currency fixture via the real `aeat app ledger import` CLI, which has no injection seam and hardcodes the default (network) provider: six name the fixture directly, and seven more share one corpus-support fixture that imports it as part of the full four-file corpus. Every other consumer (application/aggregation, application/invoices, application/ledger, domain/currency, domain/invoices, the provider's own unit suite) already injected a deterministic stub and needed no change. The landed commit covers exactly this same set.

The population a refusal catches was measured against the landed commit's guard, not assumed: 59 failed / 32 passed across the thirteen modules before the opt-in was threaded through, all failing on the refusal message. The landed commit already includes that threading; re-running the same suite against it gives 91 passed / 0 failed, genuinely reaching the live ECB host (measured wall time rose from ~100 s to ~310 s, consistent with real network round-trips). The already-stubbed consumer modules (185 tests across fx, aggregation, invoices, ledger, currency, and the corpus-fidelity gate) stayed green throughout, confirming the guard changes nothing for a suite that was already deterministic.

This row also builds the ordering precondition for `S40`: closing the door before any automatically-triggered lane exists is what keeps a future per-push lane from silently escalating a contained, dispatch-only live dependency into a per-push external call. `S40` adds that lane, scoped narrowly enough that it never reaches the FX-dependent modules at all.

The `2026-08-10-ci-lane-deconflation-integration-lane-live-service-dependency-adr` names "hold the live call behind the same explicit opt-in every other external surface here uses" as its recommended-but-unevaluated option for the separate integration-parallel `continue-on-error` flag (`S09`, already closed by operator ruling to keep the flag on). That option is now implemented for the FX call itself, but it does not resolve that ADR's permanence question: the thirteen corpus-journey modules still self-opt into the live call, so the integration-parallel step in `ci-full.yml` still genuinely depends on the ECB host through them, unchanged from before this row. Flipping that flag remains an operator decision this row does not take.

## Verification

Independently, before finding `4b98e1dc09` (guard designed and implemented in isolation, opt-in not yet threaded):

    pytest -q -n 4 -m "unit or integration" <13 corpus-journey modules>
    59 failed, 32 passed in 100.61s

Against `4b98e1dc09` at HEAD, the same 13 modules (its guard plus its own opt-in threading):

    pytest -q -n 4 -m "unit or integration" <same 13 modules>
    91 passed in 309.92s

Already-stubbed consumers, unaffected by the guard, run against `4b98e1dc09` at HEAD:

    pytest -q -n 4 <fx/aggregation/invoices/ledger/currency/corpus-fidelity modules>
    185 passed in 56.51s

Lint, format and type gates against `4b98e1dc09` at HEAD: `ruff check`, `ruff format --check`, `ty check` all pass.

## Notes

**Authorship.** This row's code is `4b98e1dc09`, authored by a concurrent agent working the same row. This record's own investigation produced byte-identical code independently and in parallel, discovered only once `git diff HEAD` on the touched files returned empty. Re-confirmed against HEAD per the worktree-safety protocol before writing this record. Nothing here is claimed as this executor's authorship, and nothing was re-landed.

`P02.S41`'s dev-tooling backlog re-measurement was taken under invalid conditions (host at 90%+ CPU, five agents' uncommitted work in the tree, a registry mid-write) and is not recorded as evidence anywhere; it is held for a re-run against a quiet host. `P01.S01` and `P02.S10` remain parked on the offline Linux X64 self-hosted runner; `docs.yml` (run `31621401242`) and `ci-full.yml` (run `31624887976`) are dispatched and queued rather than fabricated as observed.
