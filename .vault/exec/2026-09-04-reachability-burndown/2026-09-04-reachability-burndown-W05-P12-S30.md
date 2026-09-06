---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:c9ad2ae25b075bfc98aea46a3d31a620c47614f56706ed94086439635d4e8363'
step_id: 'S30'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Route the wiring backlog to its owners: of 457 gated findings only a small deletable fraction remains after the logger sweep, and the residue names capability that was built and never connected, including integrity checks nothing calls, a declared KDF warmup no measurement performs, and a locale-key convention whose scaffold gate does not exist

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --json` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.suite` -> `fail, 3 of 12, all peer-owned`
- `verify:` `uv run --no-sync pytest -q dev/audit/tests/test_classification_taxonomy_invariants.py` -> `pass`

## Notes

The routing this Step asks for is stated here rather than performed, because what
remains needs decisions the campaign cannot take.

Of 427 exact non-deferred symbol findings, 80 now carry an adjudication across 50
clusters: 61 orphaned, 35 should-be-live, 26 design-time-authority, 26 superseded,
12 staged-capability, 1 deferred-by-ownership. 347 are unexamined, split 263
functions, 61 constants, 23 classes, and concentrated in calculations (58),
application/modelo (35), entrypoints/cli (29) and adapters/persistence (26).

Every mechanically resolvable class is now closed, which is why the residue needs
people. Four instrument gaps were fixed rather than adjudicated, each removing
false findings: enum members bound by their declared VALUE in registry data; CLI
handlers whose names are assembled by f-string; handlers derived by an affix
stripper from a declared key; and classes named as a binding target in registry
TOML. Three deletable shapes were exhausted: unused module-level loggers, aliases
whose target production already uses, and superseded one-line wrappers. Five gates
now hold the shapes that recurred, so none of them can regrow.

What is left is not cruft. The classified population names capability that was
built and never connected, and the same reading applies to most of the 347: a
declared KDF warmup no measurement performs, a locale-key convention whose
scaffold gate does not exist, IVA evidence advisories nothing raises, an encrypted
asset-ledger persistence surface with no writer or reader, a tty and colour rule
set no command consults while Click's default decides instead. Each names
behaviour the product does not do, so deleting it would remove the record that it
was intended, and wiring it changes shipped behaviour. Both are owner calls.

The two ratchet blockers are unchanged and both peer-owned. One of them,
LEDGER_CLI_COMMAND_CENSUS, is correctly classified design-time-authority and
cannot be recorded as such: the symbol ratchet offers only a count baseline where
the module ratchet has an intentional entry, so a correctly-kept symbol can only
sit red or be baselined, and baselining is barred.

No threshold, exclusion, baseline, skip or allowlist was widened.
