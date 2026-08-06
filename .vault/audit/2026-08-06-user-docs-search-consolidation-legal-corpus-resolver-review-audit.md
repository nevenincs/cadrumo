---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:872b2878c5e662b69dac29d9a18e83b6bb9f1fee728cb5c198d8e2003f1b7c83'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
---

## Scope

Formal review of the legal-search consolidation repair against the accepted user-docs-search-consolidation plan and ADR. The review covered the canonical anchor resolver, its real-behaviour tests, the 33 legal catalogue references corrected by the bounded data repair, and the 17 newly added narrow normative sidecars. RAG grounding was refreshed against the resolver contract, the legal-corpus fail-closed records, and the sidecar re-extraction execution record.

## Findings

### resolver-contract | low | No fail-open resolver defect found

Exact declared sidecar anchors remain authoritative; a single declared article may satisfy only a numeric subsection of that same article; structural heading selection is unique; and missing or duplicate candidates still raise. The focused resolver/legal suite passed 75 tests, the broader registry/legal envelope passed 133 tests, and Ruff lint, formatting, and diff checks passed.

### legal-granularity | medium | Subsection citations still return article-granularity evidence

The bounded same-article rule makes citations such as an article subsection resolvable when the committed sidecar contains one whole article unit. That is safe against selecting unrelated text, and the legal validator still checks required text, but it does not create a subsection slice. The recorded anchor ratchet explicitly treats this as an operator choice between apartado-level re-extraction and repointing the citation. The implementation must not be described as proving subsection-granularity text until that choice is made.

### strict-build | medium | Full documentation build remains red outside this repair

The strict build cleared legal-corpus validation and then failed at nine CLI-sequence goldens affected by concurrent peer changes: invoice option requirements, category ordering, profile-history ordering, ledger split behavior, and localized registry output. The failure is not evidence against the legal resolver or sidecar repair, but P03.S08 remains open and a full green build is not yet established.

### deployment-boundary | low | Live deployment remains intentionally unverified

Deployment was not attempted. Live-root and credential blockers remain outside this repair, so no deployment or live-search claim is made.

### locale-scope | low | Focused locale parity passes, built-root proof remains open

The registry locale-parity gate passed 2 tests, and the focused deployment/Pagefind/legal parity group passed 7 tests. These are source and parity checks, not the P03.S08 built-site probes for en, es, ca, and hu; those remain blocked by the unrelated sequence-golden failure recorded above.

## Recommendations

- Keep the resolver and sidecar repair as the bounded legal-search implementation; do not restore whole-document fallback for anchored multi-unit records.
- Record an explicit operator decision for the remaining article-versus-apartado citations before promising exact subsection text in the legal search surface.
- Re-run the strict documentation build after the peer sequence-golden changes settle, then close P03.S08 only with built and per-locale evidence.
- Keep P04.S12 and P04.S13 deferred until credentials, live roots, and full green pre-deployment gates are available.
