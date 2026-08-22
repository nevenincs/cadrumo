---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:ffd0d184a463302195f810aff4cd27558cd475ab7c82cdfa9f676ba75cc3aea3'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace secure-storage-performance-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `secure-storage-performance-hardening` audit: `W01.P01.S49 ledger execution-policy review`

## Scope

Independently reviewed the uncommitted S49 ledger callback enrollment against
the accepted command-scoped-loading decision, the S03 execution-policy
contract, the S48 enrollment analogue, the live installed command census, and
the existing destructive/handoff authority pending its ordered S52 migration.
The review covered every reachable ledger root, group, and leaf; callback-local
ownership; maximum conditional authority; write routing; group help and bare
invocation behavior; and focused real-process and planted-negative gates.

## Findings

### ledger-conditional-network-authority | high | Six callbacks under-declare reachable network or Google execution

The callback-local shape is correct, but several declarations are not the
required maximum conditional authority. `ledger_add` at
`src/cadrumo/entrypoints/cli/_ledger.py:273` and `ledger_import` at
`src/cadrumo/entrypoints/cli/_ledger_import_cli.py:184` both install the
ECB-backed currency normalizer, whose production provider resolves non-euro
rates over the network. `invoice_add` and `invoice_import` at
`src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py:389` and
`:583` build invoices through the same ECB-backed conversion path; import also
calls the model-backed column-role mapper. `evidence_confirm` at
`src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py:522` builds the confirmed
invoice through that same conditional foreign-currency path. All five carry
`LEDGER_WRITE`, which declares no network authority or effect. Conversely,
`ledger_doclink` at `src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py:234`
fetches Drive bytes through Google credentials and `resolve_document_link` but
also carries only `LEDGER_WRITE`, omitting both Google and its implied network
authority. A future import/effect gate would therefore either reject legitimate
executions or be weakened around the very undeclared work this campaign exists
to expose. Approval is withheld while this high-severity gap remains.

### representative-policy-gate-gap | medium | Focused assertions do not exercise the under-declared external-I/O paths

`test_ledger_risk_and_route_judgments_live_on_callbacks` in
`src/cadrumo/entrypoints/cli/tests/test_ledger_execution_policy.py:53` covers
classify, split, invoice wizard, evidence rederive, Google folder pull, and risk
parity, but none of the six paths above. Exact-set presence proves only that a
policy exists, not that it is semantically sufficient. The planted-negative
node and real-process help checks are useful and passed, but neither would red
if one of these external-I/O callbacks were downgraded to `LEDGER_WRITE` again.

No additional critical or high issue was found. The live census contained a
policy on every ledger node, including executable `participation` and inert
groups; no new keyed command-path authority was introduced; legacy risk rows
remain intact for the mandatory S52 consumer-first migration; destructive and
handoff flags match every existing ledger risk row; and focused execution
completed with five tests passing plus clean Ruff checks.

## Recommendations

Resolve `ledger-conditional-network-authority` by assigning maximum conditional
presets: network-capable profile writes for ECB/model paths and the Google write
preset for Drive document linking. Confirm whether the shared network preset is
the narrowest honest declaration for each callback; do not add command-specific
path rows.

Resolve `representative-policy-gate-gap` with live-census assertions covering
all corrected paths, including Google (not merely generic network) for doclink,
and demonstrate the assertion bites when one representative callback is
externally downgraded. Re-run the focused policy suite, Ruff, destructive and
handoff parity, real-process help behavior, and the feature-scoped Vaultspec
gate before approval.
