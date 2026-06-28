---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `Cross-cutting --explain legal reference convention` | (**status:** `accepted`)

## Problem Statement

The BOE and AEAT-manual citation corpus lives behind `aeat app registry
citations` and `aeat app registry manuals`. Operational decisions
across `app ledger`, `app modelo`, `config profile`, `config auth
apoderado`, and `app live verify` produce outcomes whose legal grounding
the operator needs to surface (e.g., "why is this expense not
deductible?", "why is this NIF-IVA failure a 349 obligation?", "which
LIRPF article governs this ratio limit?"). Today the operator must
separately consult `registry citations` and manually map their decision
to the citation. There is no consistent CLI convention that links a
command's effect to its governing law in one step.

## Considerations

- Every modelo binding, every spending-category classification, every
  ratio constraint, every NIF-IVA verification expectation has a
  registry-declared legal reference identifier.
- Surfacing this on every command would clutter normal output; making it
  opt-in via a flag preserves the default-clean output.
- The convention must be uniform: same flag name, same output shape,
  same JSON envelope key across every verb that supports it.
- Some verbs are mutations (`set`, `calculate`, `verify`, `file`) where
  `--explain` shows the rule that would apply; some are reads (`list`,
  `bindings list`) where `--explain` enriches the output with citations
  per row.

## Constraints

- The convention is a `--explain` boolean flag accepted by every verb
  whose output is grounded in a registry rule, normative, or AEAT
  manual section.
- When `--explain` is set, the verb's output enriches each affected
  decision/binding/casilla/finding with a `legal_refs: [{normative_id,
  articulo, manual_ref, quote, url}, ...]` field.
- The verb's text output adds a per-row "Rule: ..." line citing the
  normative id and article when `--explain` is set.
- The flag is opt-in; default output is unchanged.
- The verb does not contact AEAT or any remote source when computing
  `--explain` output; all citations are resolved from the local registry
  / manuals corpus.
- The flag name is exactly `--explain`. Aliases (`--why`, `--legal-ref`,
  `--with-legal`) are rejected to prevent vocabulary drift.

## Verbs that must support `--explain`

The following verbs are required to accept `--explain`:

- `aeat config profile set KEY VALUE` — explains the rule governing the
  key (typically a regime-defining LIRPF/LIVA article).
- `aeat config profile keys` — `--explain` enriches each key row with
  its governing legal reference.
- `aeat config auth apoderado configure --scope SCOPE` — explains the
  AEAT apoderamiento catalogue entry.
- `aeat app ledger classify TRANSACTION_ID --category CATEGORY` —
  explains the deductibility rule for the chosen category.
- `aeat app ledger ratios set KEY VALUE` — explains the proportional-
  deduction rule (typically art. 29-30 RIRPF).
- `aeat app modelo bindings list --modelo M --year YYYY --period P` —
  enriches each binding row with the rule that requires it.
- `aeat app modelo calculate` and `aeat app modelo verify` — enriches
  each casilla value with the formula's registry-declared legal
  reference.
- `aeat app live verify nif-iva NIF` and `aeat app live verify tgvi
  NIF` — explains the obligation that mandates the verification.
- `aeat app overview explain MODELO` — already a dedicated explain
  surface for modelo applicability; this ADR aligns it with the cross-
  cutting flag shape.

Verbs that are pure storage / data-quality / discovery (e.g., `aeat app
ledger import`, `aeat app ledger list`, `aeat config bucket history
list`) do not accept `--explain` because their effects are not
rule-grounded.

## Implementation

Output contract:

- JSON envelope: every enriched item carries
  `legal_refs: [{normative_id: "RD439/2007", articulo: "29", manual_ref:
  "renta/2024/parte3/seccion2", quote: "...", url: "https://boe.es/..."},
  ...]`.
- Text format: a "Rule: " line follows the primary row text, e.g.:

```text
Category: gastos_oficina (deducible)
  Rule: RD439/2007 art. 29 — "Gastos de oficina son deducibles cuando..."
        Manual: renta/2024/parte3/seccion2
```

Implementation routes through the existing normatives / manuals
application services. The CLI layer does not fetch citation content; it
formats the structured data returned by the application layer.

## Rationale

A consistent `--explain` flag answers the operator's most common
follow-up question — "why?" — without requiring them to leave the
command they just ran. Centralising the convention in one ADR prevents
each verb's owning ADR from inventing a different flag name. The opt-in
default keeps everyday output clean while making legal grounding one
keystroke away for every rule-grounded decision.

## Consequences

- Every verb in the "must support `--explain`" list above gains the
  flag; the verb's owning ADR may reference this ADR rather than
  re-declaring the flag locally.
- The JSON envelope schema gains the optional `legal_refs` field on
  enriched rows; documentation must call this out as a stable contract.
- The registry must declare a legal reference per spending-category,
  per profile-key, per modelo-binding, per modelo-casilla, per
  apoderamiento-scope, and per live-verify expectation. Where a
  reference is missing in the registry, the output emits `legal_refs:
  []` with a debug-log note rather than failing.
- Tests must cover: `--explain` enriches output for every required
  verb; missing registry references produce empty `legal_refs` not
  errors; `--explain` adds no bucket events; text and JSON formats
  carry the same citation set; alias flags (`--why`, `--legal-ref`)
  are rejected with a "use `--explain`" hint.
