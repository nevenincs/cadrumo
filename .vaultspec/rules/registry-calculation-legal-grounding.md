# Registry calculation values must cite their binding legal source

## Rule

Every regulatory value compiled into the registry schema — a tax rate, bracket
tranche, threshold, deadline window, reduction coefficient — MUST declare, in its
`legal_refs`, the specific binding provision that *establishes that value* (the
article, disposition, or transitional provision that sets it), and that provision
MUST be defined in the legal catalogue with a `corpus_ref` resolving to the real
BOE/AEAT text. Citing the general framework article alone (e.g.
`ley-27-2014:art-29`) is insufficient when a more specific provision (a
transitional disposition, phased schedule, or modifying law) actually fixes the
number. A value whose binding provision is not in the schema is ungrounded and
MUST NOT ship.

When authoring or changing a regulatory value, confirm the binding provision is
(1) cited on the value's `legal_refs`, (2) defined in the legal catalogue, (3)
backed by corpus text the evidence gate validates, and (4) consistent with the
value (the corpus clause states the number encoded).

## Why

The Modelo 200 micro-empresa (INCN<1M) rate carried `0.17 / 0.20` for 2025
grounded only in `ley-27-2014:art-29`; the binding source — LIS DT 44ª, added by
Ley 7/2024 (BOE-A-2024-26694), phasing the rate to 21%/22% for 2025 — was absent
from the schema, so the wrong rate sat undetected and commit #210 compounded it
to a flat 23%. A regulatory number with no binding-provision citation has no
anchor to verify against and is frail by construction.

## How

- **Good:** the micro-empresa 2025 bracket declares `legal_refs =
  ["ley-27-2014:art-29", "ley-27-2014:dt-44"]`, and `ley-27-2014:dt-44` is defined
  in `legal/is.toml` with `corpus_ref =
  "corpus/normatives/html/ley-27-2014-dt-44.html#dt44"`, `document_id =
  "BOE-A-2024-26694"`, and a `required_text` the evidence gate cross-checks ("21
  por ciento"). A deadline window or threshold likewise cites the specific
  orden/RD/ley article, not just the parent law, with matching corpus text.
- **Bad:** a phased/transitional rate citing only the framework article while the
  disposition that sets the year's figure is uncited; or a `legal_refs` entry
  pointing at a catalogue id with no `corpus_ref` or whose corpus text lacks the
  value's clause — the citation must be verifiable, not decorative.

## Source

Binding-law reconciliation of the M200 micro-empresa INCN<1M cuota (LIS art. 29.1
+ DT 44ª, Ley 7/2024, BOE-A-2024-26694); operator directive 2026-06-02. Companion:
`aeat-calculation-grounding`, `aeat-schema-central-config`.
