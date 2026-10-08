---
tags:
  - '#audit'
  - '#vault-health-reconciliation'
date: '2026-10-01'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:907f6f204acd0bcb3ea59cb2a115f1edc67189af56418db39f3bdaf41030a2fe'
related:
  - "[[2026-08-28-test-reconciliation-sweep-adr]]"
  - "[[2026-09-27-website-repository-boundary-docs-static-delivery-adr]]"
  - "[[2026-09-09-registry-edition-authoring-plan]]"
  - "[[2026-09-24-retenciones-workflow-plan]]"
  - '[[2026-08-26-cli-root-verb-homes-close-honesty-audit]]'
  - '[[2026-08-31-tui-interface-audit]]'
  - '[[2026-09-03-tui-architecture-w08-p27-s379-full-audit]]'
  - '[[2026-08-31-tui-architecture-evidence-ancestry-practice-reference]]'
  - '[[2026-09-09-registry-generator-consumer-behaviour-reference]]'
  - '[[2026-10-01-website-repository-boundary-static-delivery-grounding-reference]]'
---
# `vault-health-reconciliation` audit: `pre-existing vault errors`

## Scope

Authorized by the user's 2026-10-01 request to handle the pre-existing vault
errors and verify what remains after the main merge. This is a bounded record
maintenance pass, with no new implementation plan or costly decision. The
initial whole-vault check reported 27 errors and 521 warnings: 15 legacy
per-Step execution records, ten plans with 181 closed Steps lacking ledger
rows, and two ADRs without grounding references.

This pass preserves accepted decision bodies, supersession, original execution
narratives and unrelated worktree changes. It does not certify every historical
feature against the current product implementation or repair the concurrent
registry conformance work.

## Findings

### legacy-execution-format | medium | Fifteen obsolete execution records lacked a lossless fold path

Resolved by the owning exact-manifest archive verb. The fold previews for
cli-workflow-redesign and modelo-100-renta-full-calc recovered zero paths and
would discard narrative outside recognized sections. Instead, all 15 originals
were moved to `.vault/_archive/exec/` with their original filenames and exact
bytes. The only incoming references were eight generated feature indexes;
the archive verb processed those incoming references; byte comparisons show
the eight generated indexes remained unchanged. No accepted decision, live plan or
execution narrative was removed. The archive is historical preservation, not
proof of the Steps' current implementation.

### adr-grounding-discovery | medium | Two accepted ADRs had no local grounding edge

Resolved without changing either decision body or status. The test-reconciliation
ADR now links the cli-root-verb-homes close-honesty audit, whose eighth and ninth
addenda measure the transport-governance coverage loss addressed by the ruling.
The static-delivery ADR's cited account audits lived in the portfolio vault;
`2026-10-01-website-repository-boundary-static-delivery-grounding-reference`
records their relevant dated findings and fingerprints here, and is linked from
the ADR. These are repairs to evidence discovery, not fresh approval or a claim
of current deployment health.

### missing-historical-ledger-rows | high | Ten plans carry 181 closures without mechanical evidence

Initial inspection, before the repairs below: nine plans' affected rows were first committed in the imported
vault snapshot `e6c52f6676f52e8063ebedac005255104341b59f`; their original Step-close
commits are absent from that record history. The retenciones-workflow row enters
through `ef8ad07c1911`. Some commit identities named in the narratives, including
`ef97b8dae6` and `5fef4b20cb`, do not resolve in the current repository. Neither
checked boxes nor an imported plan alone establish completion. Recoverable
source history and retained reviews will be distinguished from missing execution
or verification evidence before any repair is applied. No historical test result
will be invented.

### closure-evidence-dispositions | high | Twenty receipts recovered; 161 closures reopened

Resolved on 2026-10-01 by separating recoverable receipts from unsupported
completion claims. Twenty Steps remain closed with sourced ledger rows. The
other 161 Steps were reopened through the owning plan-progress verb. Their full
narratives, including historical test claims and qualifications, remain intact;
reopening records missing completion evidence, not proof that the work never
happened. No product code changed in this maintenance pass.

| Feature | Restored receipts | Reopened Steps |
| --- | ---: | ---: |
| `justfile-redesign` | 0 | 26 |
| `aeat-export-fragment-generator-authority` | 0 | 5 |
| `tui-architecture` | 3 | 4 |
| `tui-interface` | 3 | 10 |
| `semantic-consolidation` | 8 | 38 |
| `aeat-design-relayout-boundary` | 0 | 3 |
| `registry-edition-authoring` | 1 | 0 |
| `registry-generator` | 4 | 74 |
| `binding-schema` | 0 | 1 |
| `retenciones-workflow` | 1 | 0 |
| Total | 20 | 161 |

The retained tui-interface review supports the historical host consolidation,
awaited pushes, AST boundary investigation, and recorded review outcome. Its
self-review independence limit, retired C5 receipt precondition, and unresolved
accessibility/locale findings remain explicit; they are not passing verification
for the reopened rows. The 2026-09-03 tui-architecture audit supports S399's
focus-identity investigation. The evidence-ancestry reference and both archived
dependency references support the historical S99 archival outcome.

The registry-generator consumer reference supports S51, S53, S54 and S55's
investigations into inconsistent authority, missing-versus-zero values and
incoherent temporal selection. It does not settle the reference's held rulings
or certify other generator Steps.

Seven semantic-consolidation namespace receipts recover actual source operations
from retained commits `f35caf1dfb75c0420766f347557a3c66690ea5a6` and
`82f5f152e9c76ccbe87ae2fe54a5087e2356ae6f`, checked against their parents.
Removed package paths are historical operations. S76 additionally has a fresh
three-test pass for static and dynamic namespace reachability, including the
isolated planted-defect control. No unrelated historical test result was added.

Registry-edition-authoring S65 uses the actual 2026-09-30 whole-tree canonical
validated-authority compilation and v4 publication from the preceding merge
verification. Legal identity:
`01e2251c53ff7303152c76a60bfe0ecbd3cfee0b0791a8d7d3f1cfc58a981dae`.
This is a receipt for that tree; it does not certify concurrent registry edits
or filing-grade adoption for every modelo.

Retenciones-workflow S05 records the investigation's unresolved outcome and the
typed advisory in retained commit `2268a294cf8971c67502f83eb47731c104e46312`.
The official payment-year withholding authority was not settled. The
`m193_settled_row_amounts_unresolved_authority` advisory remains; no filing block
was lifted.

### final-verification | low | Original error inventory resolved; historical warning inventory remains

The complete canonical whole-vault check returned zero errors. Its last
whitespace warning was repaired and the focused markdown check then returned
no findings. The remaining inventory is 502 warnings, every one present in the
original baseline. All 27 original errors are resolved; this is structural
verification of the bounded repairs, not proof that the 161 reopened Steps are
implemented or that every other historical closure is fully evidenced.

| Remaining warning category | Count | Follow-up boundary |
| --- | ---: | --- |
| Empty or missing required body sections | 397 | Author or reconcile grounded content without inventing decision rationale. |
| Execution ledger/plan mappings | 49 | Recover retired Step identity or missing native evidence; preserve historical rows. |
| Legacy ADR status declarations | 23 | Compare recorded authority before changing status text. |
| Feature record completeness | 21 | Establish whether missing plans or references are real coverage gaps. |
| Duplicate frontmatter keys | 12 | Reconcile all original relationship values before canonicalizing metadata. |
| Total | 502 | The remaining historical warning work is outside this error-repair pass. |

The fresh namespace gate passed all three tests. Preservation checks passed for
all ten affected plans, both accepted ADR bodies, all fifteen archived records,
and the original lines in the six repaired ledgers. No source or test file was
changed by this maintenance pass.

## Recommendations

Keep archived execution evidence and the original decision history intact.
Recover missing ledger rows only from identifiable evidence. Preserve explicit
limits where original verification cannot be recovered; do not turn an absent
receipt into a passing result. Verify the entire vault after the scoped repairs
and report its remaining errors, warnings and any unresolved completion claims.

Treat reopened Steps as an evidence-recovery or execution backlog. Read their
preserved narratives and this audit before taking action: recover an identifiable
original receipt, or verify the required behavior and checks afresh, then close
and log only the supported outcome. Existing warnings are recorded separately
from this closure backlog; a structural pass is not a whole-product assurance.

## Context

### Restored Step inventory

- `tui-architecture`: `S363`, `S364`, `S399`.
- `tui-interface`: `S31`, `S34`, `S99`.
- `semantic-consolidation`: `S64`, `S65`, `S68`, `S70`, `S73`, `S75`, `S77`, `S76`.
- `registry-edition-authoring`: `S65`.
- `registry-generator`: `S51`, `S53`, `S54`, `S55`.
- `retenciones-workflow`: `S05`.

### Reopened Step inventory

- `justfile-redesign`: `S21`, `S22`, `S23`, `S24`, `S25`, `S26`, `S27`, `S28`, `S29`, `S30`, `S31`, `S32`, `S33`, `S34`, `S35`, `S36`, `S37`, `S38`, `S39`, `S40`, `S41`, `S42`, `S43`, `S44`, `S46`, `S47`.
- `aeat-export-fragment-generator-authority`: `S79`, `S122`, `S123`, `S125`, `S126`.
- `tui-architecture`: `S346`, `S343`, `S362`, `S394`.
- `tui-interface`: `S102`, `S105`, `S106`, `S121`, `S28`, `S29`, `S30`, `S122`, `S32`, `S33`.
- `semantic-consolidation`: `S41`, `S42`, `S05`, `S18`, `S43`, `S44`, `S47`, `S52`, `S53`, `S54`, `S55`, `S56`, `S57`, `S58`, `S11`, `S12`, `S13`, `S14`, `S15`, `S69`, `S74`, `S81`, `S85`, `S27`, `S28`, `S31`, `S32`, `S33`, `S35`, `S36`, `S37`, `S38`, `S49`, `S50`, `S62`, `S63`, `S71`, `S72`.
- `aeat-design-relayout-boundary`: `S12`, `S13`, `S14`.
- `registry-generator`: `S01`, `S02`, `S03`, `S04`, `S05`, `S06`, `S66`, `S07`, `S08`, `S09`, `S10`, `S11`, `S67`, `S12`, `S61`, `S62`, `S63`, `S64`, `S65`, `S13`, `S14`, `S15`, `S16`, `S17`, `S18`, `S19`, `S20`, `S21`, `S71`, `S22`, `S23`, `S24`, `S25`, `S26`, `S27`, `S28`, `S72`, `S29`, `S30`, `S31`, `S32`, `S33`, `S68`, `S69`, `S34`, `S35`, `S36`, `S37`, `S38`, `S39`, `S40`, `S41`, `S42`, `S43`, `S44`, `S45`, `S46`, `S73`, `S74`, `S47`, `S48`, `S70`, `S49`, `S50`, `S52`, `S56`, `S57`, `S58`, `S59`, `S60`, `S80`, `S81`, `S82`, `S83`.
- `binding-schema`: `S32`.

### Coverage and verification evidence

The ADR inventory was complete at 562 records. This pass followed the 27 reported
error targets and their supporting records; it did not semantically review all
562 ADR bodies, settle new costly decisions, or revalidate every feature against
the current implementation. One hosted semantic search answered with seven hits
(five returned); its grounding trace reported eleven requests and 103,003 input
tokens. Local evidence was used for the remaining bounded investigation.

Live verification:
`uv run --no-sync pytest -q -n 0 -m unit src/cadrumo/tests/test_namespace_attribute_reachability.py`
passed, 3 tests. Run receipt:
`<operator-home>/AppData/Local/Temp/.logs/test-runs/2026-10-01/20261001T000053.498855Z-pytest-43160-f1e289d1/run.log`.

All fifteen archived records preserve their exact original bytes. Both accepted
ADR bodies and statuses are unchanged. All ten affected plan bodies preserve
their nonblank prose and all checkbox states except the 161 explicitly reopened
Steps; the owning formatter may reflow blank lines. Ledger repair is append-only.

The complete machine-readable baseline, previews, provenance and verification
receipts are retained in the local evidence directory
`<operator-home>/AppData/Local/Temp/cadrumo-vault-repair-e8207a00ab7841b8bd7e88a413b6bc64/`.

### Repair-tool verification

The first post-repair check identified six generated feature indexes made stale
by archival and template, stamp and blank-line findings introduced by the owning
tools. Those findings were repaired. The installed feature-index verb has no
`--dry-run` flag, so its canonical regeneration was previewed against an isolated
copy of the exact active records and configuration. Only the six intended
indexes and ignored lock bookkeeping changed there; each real index then
matched its inspected preview byte for byte. Existing locks were not removed.

A bounded tool response briefly truncated one plan during formatting cleanup.
The preservation assertion caught it. The full saved body was reapplied through
the owning edit verb with a blob guard, and all ten plan-preservation assertions
passed afterward. No truncated narrative remains in the repaired records.

Machine-readable final results and preservation checks are retained alongside
the baseline in the local evidence directory named above. The final commit gate
checks only this pass's explicit owned paths; concurrent registry work retains
its own scope and verification.
