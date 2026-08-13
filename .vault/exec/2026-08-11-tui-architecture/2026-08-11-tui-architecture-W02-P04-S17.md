---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:2a3c9acb77d70d527ab9992f787fd0742a53f3764c9106a0023972b50f00f3da'
step_id: 'S17'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Define lifecycle journal, ordered event stream, owner lease, compare-and-swap revision, and secure reference ports and ## Scope

- `src/cadrumo/application/operations/_journal.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Define lifecycle journal, ordered event stream, owner lease, compare-and-swap revision, and secure reference ports

## Scope

- `src/cadrumo/application/operations/_journal.py`

## Description

- Define the atomic snapshot-plus-event journal port with explicit expected revision and owner lease.
- Define ordered cursor replay, durable lease acquisition/renewal/release, and confidential operand reference ports.
- Validate immutable lease identity and positive UTC ownership windows.
- Bind every lease transition/refusal to a closed disposition, observation time, stable evidence digest, and the exact predecessor/current lease facts required by that disposition.
- Return bounded authoritative replay pages whose closed status distinguishes pages, caught-up streams, expired cursors, compaction, and unknown operations.
- Export the approved ports through the sole operation-platform facade and prove their runtime structural surfaces directly.

## Outcome

The application boundary now states the complete persistence capabilities required by D3 and D5 without choosing a concrete adapter. Journal commits bind one snapshot and its ordered events to both the expected optimistic revision and current owner lease. Confidential operands remain outside the credential-free journal and are addressed through the canonical `ContentDigest` shape.

Focused verification passed:

- `uv run pytest -q -n 0 src/cadrumo/application/operations/tests/test_journal.py src/cadrumo/application/operations/tests/test_facade.py` - 11 passed in 1.06 seconds.
- `uv run ruff check src/cadrumo/application/operations/_journal.py src/cadrumo/application/operations/__init__.py src/cadrumo/application/operations/tests/test_journal.py src/cadrumo/application/operations/tests/test_facade.py` - all checks passed.
- `uv run basedpyright src/cadrumo/application/operations/_journal.py src/cadrumo/application/operations/__init__.py src/cadrumo/application/operations/tests/test_journal.py` - 0 errors, 0 warnings, 0 notes.
- `uvx vaultspec-core vault check all` - exit 0; structure, frontmatter, links, schema, ADR status, rename integrity, and encoding were clean. The shared vault reported 1,359 advisory warnings, including retained template annotations and stale modified stamps in concurrent vault artifacts; no error blocked S17 closure.

## Notes

Live code and vault semantic searches converged on `JournalRepositoryBase`, secure-object compare-and-swap, bucket event-history storage, the operation models/events, and D3/D5/D10. Whole-file reads covered the generic credential-free journal substrate and governing ADR/plan; targeted `rg` covered event-history repository protocols, secure-object unit-of-work writes, revision CAS, and lease identities. Existing authorities provide concrete atomic-file and secure-object mechanics but no operation-specific snapshot-plus-event, lease, cursor, or secure-reference port.

The S19 and S21 rows plus D3 require lease conflict/expiry/takeover/owner-loss evidence and replay cursor failure states before supervisor recovery can be implemented. The canonical boundary therefore owns only immutable evidence/result shapes and storage capabilities: it does not choose expiry timing, takeover policy, compaction policy, or adapter mechanics. Lease evidence now correlates operation identity, owner/token continuity or change, predecessor expiry, current acquisition, and observation time by disposition. Replay results bind the requested cursor explicitly: pages are contiguous and strictly after it, caught-up and unknown results preserve it, and expired/compacted results carry an authoritative restart boundary that must advance strictly beyond the requested cursor and equal `next_cursor`, preventing rollback. The constrained replay limit refuses zero, negative, or unbounded requests. Direct runtime implementations invoke every protocol method with typed production snapshots, events, leases, results, and operands; signature assertions pin all keyword-only correlation surfaces.

The new ports reuse `OperationSnapshot`, `OperationEvent`, `OperationRevision`, `ContentDigest`, and `Hex64Str`; they do not redeclare persistence implementation, event history, secure-object transaction logic, or supervisor policy. The first remediation test run exposed a stale facade assumption about `ContentDigest`; importing its actual canonical owner fixed collection without adding a facade export. The corrected final run is recorded above.
