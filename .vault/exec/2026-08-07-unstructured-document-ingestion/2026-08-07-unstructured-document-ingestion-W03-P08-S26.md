---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:61e9cc929d464d9208d87586f5cb8385e35f46407babe2f2db5275198fba913a'
step_id: 'S26'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Build the semantic column-role mapping capability: observed headers to the closed FieldRole enum once per file, UNMAPPED surfaced and reported, never refuse-whole, gated by allow-list refusal tests, accuracy owned by the W04 measured lane

## Scope

- `src/cadrumo/llm`

## Description

- Add `_column_role_mapping.py`: observed headers to one `FieldRole` per column,
  decided once per file, over an allow-list enumerated from the enum itself.
- Enumerate the permitted roles as `tuple(FieldRole)`, and read each member's
  documented meaning out of the enum's own attribute docstrings so a new member
  arrives offered, accepted and gated with no edit in this module.
- Return a typed proposal carrying the positional roles plus four separate
  records of what was not established: unmapped columns, role tokens outside
  the allow-list, claims that lost to an earlier claim, and claims about
  columns the table does not carry.
- Bind the mapper to `LLMClient` with no transport of its own, temperature
  pinned to zero, and a stable prompt id so a mapping call is attributable in
  usage and run telemetry separately from a document read.
- Bind `default_tabular_mapping_resolver` to the mapper, so the tabular
  fallback lane obtains a real mapping where it previously obtained none.
- Resolve the model through `select_model_for_role` against the column-role
  mapping role rather than inheriting the general default, pairing a
  role-resolved on-host runtime id with the local provider.
- Pin the adapter-tier peer edge from the financial provider package to the
  local-inference subpackage in the layering contract.

## Outcome

The tabular lane is live. The bundled libro registro export — every field the
product needs semantically present, not one header name matching an importer
column token — previously normalised and was then refused whole because no
mapping could be established. Driven end to end through the real provider, the
real resolver, the real client and a loopback endpoint, it now reports
`is_valid: True`, ingests 8 of 8 rows, and reports its one unrecognised column
rather than refusing: `column 7 'tipo_retencion' was not mapped to a role and
is not imported`. Every ingested value is byte-equal to its source cell,
because the model never touches a cell — headers go out, roles come back, and
the existing deterministic projection copies the data.

Four adjudications shaped the result. The versioned prompt registry was read
and deliberately not enrolled: its definitions hold a static template with
brace substitution, while this instruction is computed per file from the enum
and the observed headers, which a static template cannot express. The existing
client and provider adapters were reused whole rather than given a second
transport. The exact fixed-layout CSV path, which scores five known bank
layouts by header alias, was kept strictly separate — it is the exact path,
this is the general one, and the fallback still runs last. A private balanced-
brace JSON extractor in the transactions domain was found but not reached into,
since it is not exported and its owning module is another lane's hot file; the
standard-library decoder serves here and the duplication is recorded for a
later sweep.

Two findings came only from running it. The local provider adapter resolves its
endpoint from process-wide settings rather than from the client's injected
settings, so injecting settings alone silently dialled a real host. And the
client consults its response cache before building any request, and that cache
is profile-bound — so on a host with no unlocked profile the mapper raised a
storage refusal, not an LLM error. Guarding the binding on the LLM error family
alone would therefore have crashed detection of every tabular file for anyone
not logged in; the guard is the project error base, and an unavailable mapping
resolves to the same "roles could not be established" report the lane gave
before this binding existed.

Accuracy is not claimed. Every reply in the suite is authored by the test, and
the module and test docstrings both say so; how often a real model is right is
a measured figure owned by the measurement lane.

## Verification

    uv run --no-sync pytest src/cadrumo/llm/tests/test_column_role_mapping.py -p no:randomly -q -n 0
    22 passed in 21.61s

    uv run --no-sync pytest src/cadrumo/llm/tests src/cadrumo/adapters/inbound/financial -p no:randomly -q -n 0
    1 failed, 344 passed, 3 deselected in 165.61s (0:02:45)

    uv run --no-sync lint-imports
    Contracts: 6 kept, 0 broken.

The single failure in the combined run is peer-owned and was recorded rather
than patched: a local text model default moved between catalogue candidates
without its assertion being swept. A later run showed one further broken import
contract, also peer-owned and uncommitted at the time — an invoices bulk-import
module reaching outward into the financial adapter package.

Four mutations, each applied from outside the repository through a throwaway
plugin on the interpreter path so that no tracked file was edited and a crashed
run could leave no residue. Accepting a role token outside the allow-list:
10 failed, 10 passed, including the named allow-list refusal gate. Refusing the
whole file when any column is unmapped: 13 failed, 7 passed, including the
never-refuse-whole gate. Freezing the allow-list to a literal subset instead of
tracking the enum: 7 failed, 13 passed, including both enum-derivation gates.
Dropping the role binding so the mapper inherits the general model default:
1 failed, 21 passed, failing exactly the gate that names it. Every refusal test
carries a positive control proving the accept case crosses the same path.

## Notes

The role member was renamed by the catalogue lane mid-execution, from a tabular
name to the column-role name, and its default moved from a vision candidate to
a smaller text candidate. Both were picked up by reading the live enum rather
than the briefed name; the rename was verified present in the committed history
before anything depended on it, so no commit-ordering window was opened.

The positional mapping the consumer takes carries roles only, so the reason a
column is unmapped cannot travel through it. Which token the allow-list refused
is logged, but surfacing it on the operator surface needs a notice and belongs
to the consuming step.

One test file belonging to the fallback lane was committed alongside the
binding. It is exclusively the counterpart of that change — it drops the
assertion that no resolver is installed — and left behind it would have turned
the tree red the moment the binding landed.
