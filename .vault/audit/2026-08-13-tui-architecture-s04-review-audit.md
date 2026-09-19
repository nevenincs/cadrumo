---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:bceeb1afa562521678a41269d5d0e8371049561040883fa5812a44c72702c9c0'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `W01.P01.S04 independent review`

## Scope

Independent review of `W01.P01.S04`: the two accepted ADR amendments, their governing TUI topology ADR and research, and the Step execution evidence. The review checked entrypoint composition, canonical flow/bundle/secret ownership, decision-corpus consistency, and VaultSpec metadata.

## Findings

### residual-fallback-semantics | medium | The wizard ADR still describes a retired cross-entrypoint fallback path

The new D5 amendment correctly makes CLI line mode and the dedicated Textual launcher sibling projections and prohibits either entrypoint from selecting or importing the other. However, three unchanged clauses still call line mode the full-screen TUI's `fallback` or `safety net` and require exercising a `line-mode degradation path`. Those statements imply automatic full-screen-to-line-mode selection, the exact composition model this Step is meant to retire, and conflict with the new binding sibling-entrypoint clause. The flow engine, checkpoint, bundle publication/import, and ephemeral-secret ownership facts themselves remain intact and are not displaced.

## Recommendations

- Amend the three residual wizard passages to describe line mode as a separately launched CLI projection and degraded-host refusal as entrypoint-local behavior, without any TUI-to-line-mode fallback or selector.
- Retain the current profile-bundle amendment unchanged: it preserves the application flow engine, canonical bundle authorities, checkpoint prohibition, and exact ephemeral secret boundary.

VaultSpec evidence is otherwise sufficient: ADR status and links are clean, both amendments carry refreshed CLI-owned metadata and links to the topology authority, and the Step record reports schema and body-section checks without findings on the amended ADRs.

## Final re-review disposition

### residual-fallback-semantics | closed | Sibling projections replace every selector implication

The three residual passages now state that the dedicated TUI, CLI line mode, and non-interactive driver are sibling projections over the same application flow authority; no projection selects or imports another. Degraded-host behavior is split into a dedicated-TUI startup refusal and independent CLI line-mode behavior. The sole remaining use of `fallback` explicitly negates that relationship. Canonical `application.flows` ownership and the shared typed-intent semantics remain unchanged. No critical, high, or medium findings remain.
