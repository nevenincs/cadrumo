---
tags:
  - '#audit'
  - '#llm-evidence-classification'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
  - "[[2026-06-10-llm-evidence-classification-adr]]"
---



# `llm-evidence-classification` audit: `Wave W01 code review`

## Scope

Mandatory `vaultspec-code-review` of Wave W01 commits `983143078` (W01.P01) and
`bf6bf3d88` (W01.P02): the `EvidenceInput` representation + secure-storage
resolvers, the `add()` change that stores invoice bytes in the encrypted
`AttachmentStore`, the cloud-upload consent posture, and their tests. Primary
focus: the `sensitive-financial-data-secure-storage-only` invariant. Gate
decision: REVISION REQUIRED (one HIGH on the secure-storage invariant, blocking
W02).

## Findings

### EVIDENCE-INPUT-H1 | HIGH | EvidenceInput byte tripwire bypassed by nested serialization, dict(), and pickle

`src/aeat/application/ledger/_evidence_input.py`. The overridden
`model_dump`/`model_dump_json` intercept only DIRECT calls; they install no
pydantic serializer, so the `data: bytes` field schema is still live. The
decrypted FINANCIAL bytes leak via three vectors: (1) nested serialization -- when
`EvidenceInput` is a field on any other model, the parent's `model_dump_json()`
serializes `data` verbatim (the realistic W02.P04 path: provenance/request records
in `_llm_classification.py`); (2) `dict(ei)` / `__iter__`; (3) `pickle.dumps(ei)`.
Remediation: make refusal a property of the field/model -- a `@model_serializer`
that raises (covers nested dump) plus `__iter__` and pickle (`__reduce_ex__`)
refusals. Add regression tests per vector. STATUS: fixed in follow-up commit
(model_serializer + __iter__ + __reduce_ex__ refusals + nested/dict/pickle tests).

### EVIDENCE-INPUT-M1 | MEDIUM | Persistence-tripwire test misses the realistic leak path

`src/aeat/application/ledger/tests/test_evidence_input.py`.
`test_evidence_input_refuses_persistence` asserts only direct `model_dump()` /
`model_dump_json()` raise; it would pass with H1 fully exploitable. A safety test
must fail when the invariant breaks. Remediation: assert nested-model dump,
`dict()`, and `pickle` do not surface `data`. STATUS: fixed alongside H1.

### EVIDENCE-INPUT-M2 | MEDIUM | put_file buffers the whole invoice in memory (pre-existing)

`src/aeat/adapters/persistence/storage/attachment.py` `put_file` accumulates all
chunks in a list then re-joins -- a streaming API that does not stream. No bytes
hit disk outside secure storage; pre-existing; not a W01 defect. Note for the
large-evidence/rasterisation path W02 introduces. STATUS: deferred (out of W01
scope).

### EVIDENCE-INPUT-M3 | MEDIUM | Torn-write window across blob/manifest/catalogue writes

`src/aeat/application/ledger/_evidence.py` `add()` does four separate
secure-object writes with no enclosing transaction. The ordering is the safe
ordering (record saved last, so a saved record always has its blob); a crash
leaves at worst an orphan content-addressed blob (harmless on re-add). Does not
break the secure-storage invariant. STATUS: accepted for W01; prefer a
single-writer atomic primitive if one lands.

### EVIDENCE-INPUT-L1 | LOW | add() method docstring stale vs behavior

`src/aeat/application/ledger/_evidence.py` `add()` docstring omits the in-store
byte copy and `attachment_id` recording. STATUS: fixed in follow-up commit.

### EVIDENCE-INPUT-L2 | LOW | resolve_attachment_evidence_input lacks a Raises clause

`src/aeat/application/ledger/_evidence_input.py` -- documentation-completeness nit;
the error paths are correctly handled by the store. STATUS: noted.

### EVIDENCE-INPUT-L3 | LOW | attachment_id None-tolerance vs no-legacy

`src/aeat/application/ledger/_evidence.py` -- `attachment_id` defaults to `None`
for hand-constructed/pre-contract records; freshly-added records always set it. The
refusal path is the correct safety behavior; could tighten to required later.
STATUS: noted.

### Verified clean (adversarial)

No byte persistence outside secure storage (no temp files / scratch / side stores /
on-disk caches); `source_path` never read as a byte source; `repr`/`str` do not
leak `data`; consent gate default-off, gestor-bar-first, per-invocation (not
sticky); content-address integrity verified on read; import boundary consistent
with existing `_evidence.py` patterns; tests are real-behaviour (no
mocks/stubs/skips/xfail).

## Recommendations

Fix EVIDENCE-INPUT-H1 (structural serialization refusal: `model_serializer` +
`__iter__` + pickle) and EVIDENCE-INPUT-M1 (regression tests for nested/dict/pickle
leak vectors) before W02 nests `EvidenceInput` in any request/provenance record.
Fix L1 (docstring) opportunistically. M2/M3/L2/L3 are noted/deferred and do not
block W02.

## Codification candidates


