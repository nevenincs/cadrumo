---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:48269f0e4cdba9acd0446378cdc09b7ab0b2908bf20e70251dbda373b3617d45'
related:
  - "[[2026-08-04-canonical-storage-management-collapse-predictor-verification-audit]]"
---

# `canonical-storage-management` audit: `constrained detector sweep diagnosis`

## Scope

The `--scope tests` "injected-but-constrained" detector (`WriteSite.constrained`,
`dev/write_site_census.py`) was built to catch a literal that reads as free
(`temporary`/`pass_through`) but secretly agrees with a value a sibling fixture or
a spawned process independently derives from the real taxonomy accessor. Before
trusting it as a triage instrument, it was run against the full test tree and
checked against three oracles stated in advance: the three known `secrets`
positives MUST fire; the 54 hand-classified `registry` sites and the ~34 `llm-*` +
10 `manifest.toml` hand-classified sites were expected to fire zero. This document
diagnoses why the sweep missed two of three positives and over-fired roughly
thirty-fold, rather than tuning the detector to the oracles after the fact.

## Findings

### sweep-misses-two-of-three-known-positives-and-over-fires-30x | high | The detector fails its own oracle set on both axes

Run at `64c9fe6d6e`, `--scope tests`: 4557 file-producing sites, 1% unresolved
(34), 114 flagged `constrained`. Against the oracles: `test_bundle_export_recovery.py`
fired correctly; `_registry_cli_fixtures.py` and `test_m145_communication_cli.py`
— the other two known `secrets` positives — did not fire. `registry` produced 3
hits against an expected 0; `llm-*` produced roughly 9 hits (`test_cache.py`,
`test_run_telemetry_retention.py`) against an expected 0. Independently
reproduced at a different pin from a parallel run at `53f80f0830` (110 hits, the
same two misses, the same over-firing shape), so the result is not an artefact of
one revision.

### over-firing-has-three-distinct-mechanisms-all-rooted-in-crude-vocabulary-reuse | high | CONSTRAINT_RISK_SIGNALS answers "is this identifier present" not "is this a real accessor call"

Read a sample of the 114 flags rather than trusting the count. Three distinct,
independently-confirmed causes, none of them the intended signal:

1. **Self-referential accessor tests.** `test_keystore_paths.py` imports and
   calls `keystore_path()` directly, then asserts its return value against a
   literal built the same way (`tmp_path / "keystore" / "alpha"`). The module
   legitimately references the accessor AND legitimately builds taxonomy-shaped
   literals — because it is the accessor's own test — and the detector cannot
   distinguish that from an independent injection agreeing with an unrelated
   consumer.
2. **Generic local-variable names colliding with the marker vocabulary.**
   `test_run_telemetry_retention.py` never calls any accessor. It fires because
   line 157 assigns a local variable literally named `root_dir` — a wholly
   ordinary choice of scratch variable name a test author made — and `root_dir`
   is a member of `TAXONOMY_MARKERS`, reused wholesale as part of
   `CONSTRAINT_RISK_SIGNALS`. `TAXONOMY_MARKERS` was designed for
   `_trace()`/`origin_symbol()`'s narrow root-of-expression resolution; reused
   as a blanket "does this identifier appear anywhere in the module, in any
   binding role" scan, `root_dir`/`store_dir`/`db_dir`/`audit_dir`/`blobs_dir`
   are exactly the short, generic English words a test would pick for an
   unrelated local.
3. **Struct field names colliding with the same vocabulary.** `test_layout.py`
   fires because it reads `paths.db_dir`/`paths.blobs_dir`/`paths.audit_dir` —
   real attribute accesses on an unrelated `BucketPaths`-shaped structure whose
   field names happen to match `TAXONOMY_MARKERS`, matched by the same
   `isinstance(node, ast.Attribute) and node.attr in CONSTRAINT_RISK_SIGNALS`
   branch that was meant to catch a genuine accessor attribute chain.

All three share one root cause: the co-occurrence check treats
`CONSTRAINT_RISK_SIGNALS` membership as sufficient on its own, with no check on
*how* the identifier is bound (a call, a root-of-expression trace target, versus
an arbitrary local or field name). 18 of the 36 flagged files already carry a
`PINNED_TAXONOMY_LITERALS` declaration, which independently confirms the
over-firing concentrates exactly where accessor-and-literal co-occurrence is the
normal, already-handled case, not a novel hazard.

### the-two-misses-have-two-different-independent-causes | medium | One is the documented cross-module limitation firing correctly; the other is a genuine vocabulary gap

`_registry_cli_fixtures.py` injects `str(tmp_path / "secrets")` in a fixture
function and never itself references any accessor, `subprocess`, or `CliRunner`
name — the module docstring's own two mentions of the real mechanism
("`storage_overrides`", "subprocesses") are prose inside a `Constant` string
node, invisible to an `ast.Name`/`ast.Attribute` walk. The real CLI invocation
(`invoke_cached_cli`) lives in the separate consuming module,
`test_registry_cli.py`. This is the documented limitation
("module-local co-occurrence is the whole signal") working exactly as designed
and disclosed — not a defect, but proof the limitation is real and costs a
known true positive.

`test_m145_communication_cli.py` is the sharper case: the injection (line 141)
and the CLI invocation (`invoke_cached_cli`, line 158) are in the **same
module**, yet it still misses, because `invoke_cached_cli` — the project's own
wrapper used by nearly every CLI integration test in this repository, per
`treegates`'s independent observation on the `live`/`runs` bands — is not a
member of `CONSTRAINT_RISK_SIGNALS` (`subprocess`, `Popen`, `CliRunner`, plus
`TAXONOMY_MARKERS`). This is fixable in isolation (add the project's real
invocation wrapper name to the signal set), but fixing it does not touch the
over-firing findings above, which are the dominant failure mode by a wide
margin.

## Recommendations

**Do not ship or trust `WriteSite.constrained` as an automated finding
generator.** Precision on this run is roughly 1 in 40 (3 real true positives
among 114 flags at best; the third, `test_bundle_export_recovery.py`, is the only
unambiguous hit), and the detector fails its own pre-stated oracle on the recall
side too, missing 2 of 3 known positives for two unrelated reasons. Per the
standard applied before this sweep ran — missing any known positive is
disqualifying, not a tuning note — the instrument does not clear that bar, and
patching it to the three known cases now would make it a lookup table rather than
a working detector, which is the exact failure mode this diagnosis pass exists to
avoid.

**Keep the code, the tests, and the honest self-reported unresolved rate.** The
`--scope tests` widening, the `fixture` bucket, import-alias following in
`_bindings()`, and the documented, disclosed limitation are durable and correct
improvements independent of whether `constrained` ships as a trusted signal. The
36 unit tests for the new primitives (`_literal_tail`,
`_taxonomy_subpath_tokens`, `_module_signals_constraint_risk`, `_is_constrained`,
`_top_level_div_chains`) remain valid pins on those primitives' individual
behaviour; they were never claims about the composed detector's real-world
precision, and this finding does not invalidate them.

**If the category is worth pursuing further, it needs a sharper co-occurrence
join, not a bigger vocabulary.** A workable version would need to distinguish an
accessor *call* from a coincidental local-variable or field-name match (require
`ast.Call` context, not bare `ast.Name`/`ast.Attribute` presence), and would need
to see across the fixture-to-consumer boundary the cross-module miss exposed —
neither is a small change. Whether that investment is worth it, against six
literal bands already closed by hand at effectively zero tooling cost, is a
decision for whoever owns the campaign's remaining budget, not a default.
