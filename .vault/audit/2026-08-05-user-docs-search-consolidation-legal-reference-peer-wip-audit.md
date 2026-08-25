---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:41020a0605f5b37ebbd954871e92d9101d06e03476479a48ddd7e855d1090a88'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

## Scope

Read-only formal review of the current peer-owned legal-reference and glossary diff against the RAG-grounded P05 plan, ADR, legal projection, unified record contract, and Pagefind injection boundary. No code, tests, builds, generation, deployment, or runtime probes were run.

## Findings

### contract-parity | low | PASS: the peer diff preserves the P05 legal contract

The current changes are limited to typing/path-authority narrowing in `legal_reference.py` and `glossary_reference.py`. Deterministic catalogue ordering, schema validation, generated per-law/provision targets, record-id parity, and BOE permalink provenance remain unchanged. `_legal_projection.py` still consumes renderer-owned targets, and `pagefind_inject.py` receives the same target.

### fail-closed-read | low | PASS: malformed legal input still aborts before generated writes

`load_legal_provisions` does not wrap `UnicodeDecodeError`, but the exception still aborts the generation path before stale-page removal or output writes. The accepted P05 contract requires fail-closed behavior, not a particular wrapper type, so this is optional hardening rather than a plan defect.

## Recommendations

Keep the peer-owned diff intact. If a typed `LegalReferenceError` wrapper for decoding failures is desired later, treat it as an independently scoped hardening change with its own owner and review; it is not required to advance P05 under the current contract. P05.S14-S17 remain open for generation, target-resolution, parity, and runtime evidence.
