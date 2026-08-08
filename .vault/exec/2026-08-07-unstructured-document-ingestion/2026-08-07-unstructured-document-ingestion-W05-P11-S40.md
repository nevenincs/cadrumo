---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:13ef577ce8aa6d0e80af007015d7a3028b4d3e706d4d2f2153603862ae61bcd5'
step_id: 'S40'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` exec: `W05-P11-S40`

## What was already true at HEAD, and what was not

Two of this Step's three parts had already landed and were verified against HEAD
by reading the code rather than the checkbox.

The subprocess symbols are still asserted deleted, and the MCP positive control
survives: `test_no_deleted_cloud_symbol_survives_in_production` sweeps the whole
non-test package, and
`test_the_neighbouring_mcp_subprocess_transport_survived_the_deletion` asserts
`entrypoints/mcp/_call_runtime.py` both exists AND still spawns a process, so a
deletion scoped by the word rather than by symbol reds.

The four consent symbols are presence-asserted AND wired, not merely present.
`test_the_reinstated_consent_apparatus_exists_and_is_wired_at_the_choke_point`
walks the abstract syntax tree of `LLMClient.complete` for the consent call, so a
gate that exists and is never reached fails -- which is the dominant defect of
this campaign pointed the other way.

The third part had landed in the forbidden shape.

## The floor was a tally, and it guarded the wrong thing

`test_the_declared_symbol_set_is_not_silently_emptied` asserted
`len(_DELETED_CLOUD_SYMBOLS) >= 12`. Two independent problems.

It is a tally, which encodes the moment it was written and trains the next
person to raise the constant. And it is satisfiable by exactly the failure it
names: emptying the two-name operator-surface family leaves twelve symbols, so
the floor passes while a whole family has stopped being swept.

The deeper problem is that it measured the declaration and never the
instrument. The sweep reports clean when it finds nothing, and finding nothing
is also what a broken scanner reports -- an empty file list, a changed helper, a
read that yields no text. A full symbol tuple scanned over zero files passes.

## The re-base

`_DELETED_CLOUD_SYMBOL_FAMILIES` groups the deleted names by the family each
belonged to, and the flat tuple is derived from it. Grouped because the
property -- no family silently gutted -- cannot be expressed over a flat tuple,
which admits only a length.

`test_the_scanner_finds_a_symbol_that_is_actually_present` is the real
non-vacuity floor. It drives `_production_sites_naming`, the same helper the
sweep uses, over the same file set, looking for `build_provenance_stamp`, which
is present. The scan was factored out of the sweep specifically so the control
cannot re-implement the walk: a control with its own copy proves that copy
works and says nothing about the one that reports clean.

`test_no_declared_family_is_silently_gutted` asserts every family non-empty and
no symbol declared twice -- a borrowed name would make a family look populated.
It also asserts the reinstated consent set is non-empty, closing a vacuity in
the two totality checks above it: each only asserts the declared set and its
verifier mapping AGREE, so emptying both together satisfies both.

## Proof

Seven mutations from a plugin outside the repository; no tracked file touched.
Baseline 8 collected, 8 passed. Every mutation reddened exactly one assertion.

Two carry the argument. Gutting the smallest family leaves twelve symbols, so
the retired floor would have PASSED, and the family property reds -- the
discriminating case, not a restatement. And emptying the scanner's file walk
reds the new control while **the sweep itself still passes**: seven tests green
over a walk of nothing. That is the vacuity made concrete rather than argued,
and it is the reason the floor had to move from the declaration to the
instrument.

The rest: emptying the reinstated set and its verifier map together, unwiring
`LLMClient.complete` from the consent gate, declaring one symbol in two
families, pointing the MCP control at a missing file, and adding a live
production symbol to the deleted set each reddened the assertion that owns it.

## The live consent path was not disturbed

Consent is in production use this session, so the surfaces were run rather than
reasoned about. The change is confined to one test module and touches no
production code.

    uv run --no-sync pytest src/cadrumo/llm/tests -n0 -q -m unit
    409 passed, 4 deselected

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_evidence_extract_consent_verb.py \
      -n0 -q -m integration
    7 passed

The second is the one that matters: its positive control mints a real token
through the sole constructor and drives a real request into a loopback
endpoint, so it fails if the minting path stops working rather than only if it
stops refusing.

`ruff check`, `ruff format --check` and `ty check` clean.
