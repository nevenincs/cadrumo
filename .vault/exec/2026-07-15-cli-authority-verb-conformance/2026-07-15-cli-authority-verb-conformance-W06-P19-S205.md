---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S205'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Rerun Vaultspec-RAG semantic searches across certificate custody, ledger evidence, export, hashing, replay, namespaces, filed capture, LLM review, registry queries, and duplication infrastructure

## Scope

- `src/cadrumo/`
- `dev/audit/`

## Description

Rerun the semantic searches across certificate custody, ledger evidence, export, hashing,
replay, namespaces, filed capture, LLM review, registry queries and duplication infrastructure.

## Outcome

UNVERIFIED. The instrument is degraded and every result it returned is unusable as evidence.

The index self-reports healthy while being truncated. Status output at run time: `Source code
sections: 466`, code generation 1 `succeeded`, server running. The tracked Python file count is
3982, and the product source tree alone carries 3658. A 466-section index over a 3982-file tree
cannot represent the tree.

All ten concept sweeps were run against the code index. Every one returned a miss. Three results
demonstrate the failure directly rather than merely failing to confirm.

Searching for copy-paste duplication detection returned the CLI profile-duplicate command and did
NOT return the duplication runner, which is the tree's single canonical owner of exactly that
concept and was independently confirmed to exist under S203.

Searching for a file-bytes digest returned a release-readiness module and did NOT return the core
hashing module, which declares both the bytes and the file digest helpers.

Searching for the secure-object namespace registry returned an auth operator test and did NOT
return the namespace registry module.

Two unrelated probes, replay and duplication, returned the SAME file and the same offset, which is
the recognised signature of a partial index answering from a tiny candidate pool.

## Notes

Per the governing instruction the service was NOT restarted and NOT reindexed.

The operational consequence is recorded plainly: for this Phase the semantic instrument can supply
a pointer when it hits but can never support a claim of absence. Every negative in this Phase was
established by exact search and by reading, and is recorded that way under S206.

The deeper hazard is that the degraded index answers confidently. It reports no degradation
reasons, so the mandate to refuse work when semantic discovery is unavailable never fires. That is
a standing instrument defect for the coordinator, independent of this campaign.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.
