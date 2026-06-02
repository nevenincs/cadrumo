---
name: registry-calculation-legal-grounding
trigger: always_on
---

# Registry calculation values must cite their binding legal source

## Rule

Every regulatory value compiled into the registry schema — a tax rate, a
bracket tranche, a threshold, a deadline window, a reduction coefficient — MUST
declare, in its `legal_refs`, the specific binding provision that *establishes
that value* (the article, disposition, or transitional provision of the law that
sets it), and that provision MUST be defined in the legal catalogue with a
`corpus_ref` resolving to the real BOE/AEAT text. Citing the general framework
article alone (e.g. `ley-27-2014:art-29`) is insufficient when a more specific
provision (a transitional disposition, a phased schedule, a modifying law) is
what actually fixes the number. A value whose binding provision is not in the
schema is treated as ungrounded and MUST NOT ship.

## Why

The Modelo 200 micro-empresa (INCN < 1M) two-tranche rate carried `0.17 / 0.20`
for 2025 in `is.modelo-200.tipo-gravamen-pyme`, grounded only in
`ley-27-2014:art-29`. The binding source — LIS **disposición transitoria 44ª**,
added by **Ley 7/2024** (BOE-A-2024-26694), which phases the rate to **21 % / 22 %
for 2025** and 19 % / 21 % for 2026 — was absent from the schema. Because the
specific provision that fixes the 2025 figure was never cited or cross-checked
against its corpus text, the wrong rate sat in the registry undetected and a
downstream commit (#210) compounded it by routing the cuota to a flat 23 %. The
value drifted precisely because nothing in the schema pinned it to the law that
sets it. A regulatory number with no binding-provision citation has no anchor to
verify against and is frail by construction. This is the authoring counterpart of
`[[aeat-calculation-grounding]]` (which preserves provenance through boundaries)
and `[[aeat-schema-central-config]]` (which keeps values in the registry): this
rule mandates that the value, at its authoring site, names and grounds the
provision that makes it binding.

## How

- **Good:** the micro-empresa 2025 bracket declares
  `legal_refs = ["ley-27-2014:art-29", "ley-27-2014:dt-44"]`, and
  `ley-27-2014:dt-44` is defined in `legal/is.toml` with
  `corpus_ref = "corpus/normatives/html/ley-27-2014-dt-44.html#dt44"`,
  `document_id = "BOE-A-2024-26694"`, and a `required_text` source-citation that
  the evidence gate cross-checks against the real text ("21 por ciento").
- **Good:** a deadline window or threshold cites the specific orden/RD/ley
  article that publishes it, not just the parent law, and the corpus carries the
  matching clause.
- **Bad:** a phased or transitional rate citing only the consolidated framework
  article while the transitional disposition that actually sets the year's figure
  is uncited — the number can be wrong and no gate can catch it.
- **Bad:** adding a `legal_refs` entry that points at a catalogue id with no
  `corpus_ref`, or whose corpus text does not contain the value's clause. The
  citation must be verifiable, not decorative.
- **Verification:** when authoring or changing a regulatory value, confirm the
  binding provision is (1) cited on the value's `legal_refs`, (2) defined in the
  legal catalogue, (3) backed by corpus text the evidence gate validates, and
  (4) consistent with the value (the corpus clause states the number you encoded).

## Source

Binding-law reconciliation of the Modelo 200 micro-empresa INCN<1M cuota
(LIS art. 29.1 + DT 44ª, Ley 7/2024, BOE-A-2024-26694). Origin: operator
directive recorded 2026-06-02 — "legal groundings the schema must be grounded
against and cross-referenced; if the actual modelo schema does not contain the
legal grounding all work will be frail." Promoted per the `[[vaultspec-codify]]`
discipline.
