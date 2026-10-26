---
tags:
  - '#adr'
  - '#iva-workflow'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:e8a77f2004fc587ea87311566fcb28f23d9c2e36e338419ca6441d038ea2dc25'
related:
  - "[[2026-09-21-iva-workflow-reference]]"
  - "[[2026-08-06-invoice-canonical-structure-adr]]"
---

# `iva-workflow` adr: `Repeatable JSON invoice-line CLI input` | (**status:** `accepted`)

## Problem Statement

The canonical invoice aggregate already accepts ordered line items, but the
public CLI exposes only a scalar base and rate. The CLI needs a lossless
multi-line input contract. No existing invoice option establishes how repeated
structured line facts are encoded, so choosing a syntax is a public contract
decision rather than an implementation detail.

## Considerations

- The accepted canonical-invoice decision requires an operator-supplied
  multi-rate invoice to be expressible through the existing writer.
- The shared application operation accepts `Sequence[InvoiceLine]`; the CLI
  must project into that owner without calculating tax or creating a parallel
  line model (`2026-09-21-iva-workflow-reference`).
- Line order and line-local optional facts must survive validation, encrypted
  persistence, and structured readback.
- The pre-release no-compatibility rule does not require preserving the scalar
  shortcut as an alternate representation.

## Considered options

1. Accept repeatable `--line` values, each containing one JSON object matching
   the public `InvoiceLine` input shape. Chosen because each occurrence is
   independently parseable, ordered, and extensible.
2. Accept parallel repeated flags for each line field. Rejected because
   positional association is fragile and optional fields make the lists
   ambiguous.
3. Accept a delimiter-based mini-language. Rejected because escaping and schema
   evolution would become a second parser contract.
4. Accept a whole invoice document as one JSON argument. Rejected for this
   command because it duplicates the existing option surface and obscures which
   owner validates invoice-level facts.

## Constraints

- Each `--line` occurrence is exactly one JSON object and preserves command-line
  order.
- The object is mapped to the existing application/domain `InvoiceLine` shape;
  the CLI performs parsing and validation only, never tax arithmetic.
- Structured lines and legacy scalar base/rate inputs are mutually exclusive.
  No silent merging or precedence is allowed.
- Invalid, incomplete, or unknown line fields fail the command before the
  shared writer mutates persistence.
- Structured readback exposes the canonical persisted fields needed to prove
  round-trip tax meaning; it does not expose secure storage paths or raw source
  rows.
- Import provenance remains the existing basename, SHA-256, and one-based-row
  identity pattern described by `2026-09-21-iva-workflow-reference`; this ADR
  does not create another provenance type.

## Implementation

The invoice command accepts repeatable `--line` JSON objects, validates them as
the canonical public line input, and passes their ordered sequence to the
existing catalogue-invoice creation operation. The scalar shortcut is removed
or refused when structured lines are supplied. The existing invoice projection
is extended to return the persisted canonical line facts and the document-level
classification, operation, category, and rectification facts required by the
same workflow. Implementation seams and focused regression candidates are in
`2026-09-21-iva-workflow-reference`.

## Rationale

One object per option occurrence preserves the natural invoice-line boundary
and delegates meaning to the existing model. Unlike parallel lists, it cannot
misassociate optional fields; unlike a mini-language, it uses an established
typed data notation. Refusing mixed representations makes the mutation
deterministic and avoids a second precedence rule.

## Consequences

Operators can capture mixed-rate and richer line-level facts without frontend
arithmetic, and CLI readback can prove what survived reopening. Shell quoting of
JSON is less convenient than scalar flags, so help and diagnostics must show a
minimal object without echoing financial payloads. Future additions to the
public line input require deliberate schema evolution rather than ad hoc flags.
