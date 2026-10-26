---
tags:
  - '#adr'
  - '#modelo-locale-delta-keying'
date: '2026-09-17'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:7533eace79766259c03a41f746149668a808ebee732ce08d49864f73c3c17507'
related:
  - "[[2026-09-17-modelo-locale-delta-keying-research]]"
  - "[[2026-09-09-registry-edition-authoring-adr]]"
  - "[[2026-07-21-locale-key-resolution-adr]]"
---

# `modelo-locale-delta-keying` adr: `modelo locale delta keying and derived-text removal` | (**status:** `accepted`)

## Problem Statement

The registry stores Modelo editions as deltas, but the Modelo locale catalogues are keyed and populated per materialised edition. The catalogues therefore restate inherited text, carry scaffold nulls, generated help boilerplate and placeholder labels. They also hide genuine per-edition divergence among thousands of repeats (`2026-09-17-modelo-locale-delta-keying-research`). `2026-09-09-registry-edition-authoring-adr` already requires the label catalogue to inherit alongside declarations. The resolver implements that, but the key universe, scaffold and stored data were never brought to the same delta discipline.

## Considerations

- The resolver chain already provides the inheritance tiers: own occurrence, stating edition, continuity, then Spanish (research, first finding).
- Spanish casilla labels are derived from official designs and are legally meaningful; a collapse must be lossless in resolved meaning, never a re-authoring.
- Non-Spanish fallback currently crosses tiers, which becomes a correctness risk once values move to less specific keys (research, barrier finding).
- Generated help carries no information beyond the label, and help is optional at every reader.
- About 5,200 occurrences carry no `continuidad_id`, so continuity alone cannot hold every lineage-wide value.
- The locale edit surface is `dev/locales`; generated catalogues change only through its verbs (`aeat-locales-cli`).

## Considered options

- **A. Delta-keyed catalogue on the existing chain (chosen).** A value lives at the least specific key that yields the same resolution. Inherited rows and restatements carry no entry. Needs a key-universe change, a barrier in the resolver and a collapse tool; no new tier.
- **B. Add a modelo-wide casilla-id tier.** Would absorb the rows without `continuidad_id`, but casilla identity is edition-local, and repurposed ids (research, identity divergence) would inherit wrong meaning.
- **C. Require `continuidad_id` everywhere before collapsing.** Correct in the long run, but it blocks the collapse on 5,200 grounded lineage declarations; kept as follow-on registry authoring.
- **D. Keep per-edition keys and deduplicate only in tooling reports.** Rejected: it leaves the store impure and translators retyping inherited text.

## Constraints

- Resolved text for every locale, modelo, edition and casilla must be byte-identical before and after collapse, except for deliberate repairs recorded separately (placeholders, garbled help).
- The Spanish source value is never changed by collapse; content repair of Spanish labels needs same-box evidence from another edition or the official design.
- Runtime must not import `dev`; the collapse tool and key universe live in `dev`.

## Implementation

- **Canonical homes.**
  - A casilla value is stored under the stating edition's occurrence key, or under the continuity key when every stating edition of the lineage agrees.
  - Inherited rows get no occurrence key.
  - An occurrence value equal to what the next tier resolves is deleted.
- **Label origin across storage overrides.** A storage override keeps the row's label origin unless it changes `id`, `number` or `continuidad_id`; provenance-only patches do not detach a row from the text of the edition that stated it.
- **Key universe.** `load_modelo_locale_key_projection` emits occurrence keys only for stated rows, plus continuity keys. The scaffold stops creating null leaves for keys that are not the canonical home.
- **Barrier.** `resolve_modelo_localization` finds the most specific tier that has Spanish text. The requested locale is read only at that tier or more specific ones, and otherwise falls back to that Spanish text.
- **Derived help removal.** Help values generated from the label (the template families in the research) are deleted in every locale. Help remains optional. The generator that produced them is retired, and a gate refuses the templates.
- **Consumer.** `src/cadrumo/application/modelo/workspace.py` resolves through the casilla's key chain instead of the raw occurrence key.
- **Tooling.** A `dev.locales` collapse verb computes the canonical form, proves resolved-text equivalence for every locale, and writes through the catalogue authority. A gate asserts zero restatements, zero inherited keys, zero null leaves and zero template helps.
- **Data repair.**
  - Placeholders are replaced with the same-box sibling text.
  - The in-flight Spanish continuity additions are reviewed against sibling or official text.
  - Missing translations are filled at continuity keys; only genuinely new identities receive new translation.
  - Wording divergence (1,606 identities) is reviewed separately against official designs.

## Rationale

Option A removes the repetition with the machinery that already ships and keeps edition-specific divergence expressible. Adding the barrier is what makes moving values to less specific keys safe. B trades the repetition for wrong inheritance on repurposed ids. C is right but belongs to registry authoring, not to catalogue purity. D keeps the defect.

## Consequences

- The four catalogues shrink substantially. New editions ask translators only for text that actually changed.
- Resolved text is unchanged apart from recorded repairs; placeholder and garbled strings disappear from operator output.
- Help text disappears where it only repeated the label; operators see no help rather than boilerplate.
- Casillas without `continuidad_id` keep text at their stating edition and still repeat when restated by later editions. Closing that needs lineage authoring (option C), tracked separately.
- The key-universe change alters `dev.locales` parity expectations and dev tests that assume a key per materialised occurrence.
