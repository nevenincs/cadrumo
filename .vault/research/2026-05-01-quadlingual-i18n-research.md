---
tags:
  - '#research'
  - '#quadlingual-i18n'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-04-12-trilingual-i18n-research]]"
  - "[[2026-04-12-trilingual-i18n-adr]]"
  - "[[2026-04-12-trilingual-i18n-reference]]"
  - "[[2026-05-01-quadlingual-i18n-adr]]"
  - "[[2026-05-01-quadlingual-i18n-reference]]"
---

# `quadlingual-i18n` research: extending the i18n contract from es/en/hu to es/en/ca/hu

## why this revision

The trilingual contract from 2026-04-12 (`es`, `en`, `hu`) covers the
canonical legal language, the project's working language, and the
operator's first language. It does **not** cover Catalan, which is
co-official across Catalunya, the Illes Balears, and the Comunitat
Valenciana, and is the day-to-day language of a non-trivial fraction
of the Spanish autónomo population — the very audience this tool
serves. Adding `ca` is therefore a UX requirement, not an i18n nicety.

A second, equally important driver: the corpus already carries
structured `{es, en, hu}` maps on every casilla `label` and `help`
field, plus on every `normatives` summary slot. Adding `ca` is a
pure additive extension of an existing contract; the storage shape,
the runtime primitives, the fallback chain, and the authoritative-
language matrix do not need to change.

The third driver — the user's explicit instruction — is to roll out
**legal language** properly, not machine-quality copy that drifts
when an autónomo reads it next to the official AEAT or Generalitat
documentation. This research doc therefore spends most of its
budget on terminology grounding, not on architecture.

## scope

In scope:

- Extending `Language` and `Translatable` to include `ca`.
- Updating the configured fallback chain default and the hardcoded
  last-resort order to acknowledge `ca`.
- Authoring a legal-terminology reference (the quad-lingual glossary)
  that anchors every CA rendering in published Generalitat / Agència
  Tributària de Catalunya / EU sources, plus the corresponding HU
  rendering anchored in NAV (Nemzeti Adó- és Vámhivatal) and EU
  Directive translations where applicable.
- Migrating every user-facing CLI string still hard-coded in English
  to a `Translatable` routed through `get_translation`.
- Backfilling `ca` on every existing corpus JSON record with a
  grounded translation drawn from the glossary, marked with a
  reviewer-readable provenance flag so a native Catalan reviewer can
  sweep later.

Out of scope:

- The LLM-driven translation pipeline (#21).
- Automated terminology drift detection across BOE / DOGC publications.
- A web/desktop UI; the project remains CLI-only for the v0.x line.
- Adding any further languages beyond the quad-lingual contract.

## the legal-language problem

Spanish tax terminology is **not** freely translatable. Every
casilla label, every BOE article reference, and every status code
from the Sede Electrónica has a specific legal meaning that maps
to a corresponding article of Spanish, EU, or autonomous-community
law. Bad translations corrupt the user's mental model of what a
field actually represents.

For the four contract languages the canonical terminology sources
are:

- **`es`** — Boletín Oficial del Estado (BOE), Agencia Tributaria
  manuales prácticos, AEAT Sede Electrónica labels. These are the
  legal-canonical sources; `es` slot content must be quoted from
  them, not paraphrased.
- **`en`** — primary sources are the EU directives in their English
  translations (notably Directive 2006/112/EC for VAT and Directive
  2011/16/EU for administrative cooperation), the OECD Model
  Tax Convention commentaries, and the Spanish Tax Agency's own
  English-language summaries on `agenciatributaria.gob.es`. Where
  these disagree, EU directives take precedence for cross-border
  terms (intra-Community, reverse charge), AEAT's own English copy
  for Spain-specific terms (autónomo, modelo, casilla).
- **`ca`** — the Generalitat de Catalunya publishes the Catalan
  rendering of state-level tax instruments through the Diari Oficial
  de la Generalitat de Catalunya (DOGC) and the Agència Tributària
  de Catalunya (ATC) publications. Convention there is to keep
  Spanish acronyms intact (`IVA`, `IRPF`, `IRNR`) rather than coining
  Catalan acronyms, because the underlying legal instrument is
  state law, not autonomous law. Catalan-language tax forms from
  ATC use this convention consistently.
- **`hu`** — Hungary has no Spanish-tax counterpart, so `hu` slots
  are anchored in NAV's published vocabulary for analogous concepts
  (e.g. `IVA` ↔ ÁFA, `IRPF` ↔ SZJA, `autónomo` ↔ egyéni vállalkozó),
  with the Spanish acronym retained in parentheses on first use to
  preserve the link to the source document. EU directive HU
  translations (eur-lex.europa.eu) are the cross-reference.

## terminology survey for the recurring spanish tax vocabulary

The legal glossary is captured separately in
`.vault/reference/2026-05-01-quadlingual-i18n-reference.md`. The
research summary here covers only how the entries were derived.

The casillas corpus (`corpus/casillas/modelo_*/<period>.json`) shows
that `label` and `help` map keys recur in fewer than 100 distinct
shapes per modelo. A first-pass enumeration of the recurring lemmas
across modelos 100, 111, 115, 123, 130, 131, 180, 200, 232, 303, 347,
390, 720, 840 and the alta/baja-de-actividad modelos 036/037 yields
roughly 220 distinct terms — well within human-curation budget.

Each glossary entry carries:

- `es` — quoted from the AEAT manual práctico for the relevant
  modelo or, for cross-modelo terms, from the BOE article that
  defines the term.
- `en` — primary EU-directive rendering where one exists; AEAT
  English-language site copy otherwise; OECD glossary as a tertiary
  fallback.
- `ca` — DOGC / ATC rendering. Acronyms held identical to `es` per
  the convention above.
- `hu` — NAV equivalent for the analogous Hungarian concept;
  Spanish acronym retained on first occurrence inside parens.

For terms with no directly equivalent foreign concept (e.g.
*recargo de equivalencia*, a Spanish-only VAT regime for retail
resellers), the foreign-language slot uses a literal translation
followed by `(régimen aplicable solo en España)` glossing in the
respective language. This is the pattern AEAT itself uses on its
English-language pages.

## architecture impact

The trilingual ADR's six core decisions all hold under the quad-
lingual extension:

1. **Storage shape** — nested dict keyed by ISO 639-1 code.
   Adding a `ca` key is additive; no record migration is needed
   because `total=False` on the `Translatable` TypedDict already
   permits incremental population.
2. **Default and authoritative languages** — Spanish remains the
   AEAT-domain authority; English remains the project-docs authority.
   Catalan and Hungarian are user-facing renderings only; neither
   becomes authoritative for any field.
3. **Validation strategy** — every record continues to require its
   domain's authoritative language. Missing `ca` is a warning, not
   an error, exactly as missing `hu` is today.
4. **CLI / output language selection** — `AEAT_OUTPUT_LANGUAGE` and
   the `--lang` flag now accept `ca` in addition to `es`/`en`/`hu`.
   The fallback chain is widened.
5. **Encoding** — UTF-8 + NFC, unchanged. Catalan's geminated `l·l`
   and accented diacritics round-trip cleanly under NFC.
6. **Tooling** — no gettext, no `.po` files. Decision unchanged.

The runtime primitives (`get_translation`, `require_authoritative`,
`with_translation`, `normalize_language_code`) need no API change;
their behaviour adapts because the `Language` enum and the
`Translatable` TypedDict expand. The `_HARDCODED_FALLBACK_ORDER`
constant in `src/aeat/core/i18n/__init__.py` switches from
`["en", "es", "hu"]` to `("es", "en", "ca", "hu")` — Spanish first
so AEAT legal text stays canonical when every other slot is empty.

## CLI-side gaps surfaced by the audit

Issue #377 lists 27+ user-facing CLI strings still hardcoded in
English plus one call path (`cli/review/queue.py:_summary_text`)
that bypasses `AEAT_OUTPUT_LANGUAGE` entirely. The same audit found
nine pseudo-translations: `Translatable` literals where every
language slot carries the identical English string.

The migration touches the call sites currently scattered across:

- `entrypoints/cli/review/queue.py` — `_summary_text`
- `entrypoints/cli/manual.py` — `summary.get('es', '')` rendering
- `entrypoints/cli/filing/__init__.py` — finding-table rendering
- `entrypoints/cli/setup.py` — verifier-table rendering
- `entrypoints/cli/auth/__init__.py` — Cl@ve Móvil prompt block
- `entrypoints/cli/deadlines/_helpers.py` and `next.py` — empty-state
  messages
- `entrypoints/cli/financial/{txs,invoices,profile}.py` — operational
  errors
- `application/review/_adapters.py` — pseudo-translation literals
- `application/setup/_verifier.py` — pseudo-translation literal

Every site routes through `Translatable` literals and the shared
`output_language()` helper extracted to
`entrypoints/cli/_i18n.py`.

## on machine-translated catalan content

Native Catalan tax-terminology review remains a valuable downstream
step. The glossary entries written here are anchored in published
DOGC / ATC sources where I have direct knowledge; entries marked
`needs-native-review` carry my best-effort rendering plus a citation
to the most authoritative source consulted, so a native reviewer
can decide between accept-as-is, edit, or fully replace.

The project does not ship anywhere near the volume of free-form
Catalan prose that would justify a paid translation contract; the
glossary plus per-record `definition_reviewed_by = human-codex`
metadata gives a future native reviewer a tractable surface area
to sweep.

## decision direction

Accept the quad-lingual extension; ship the `ca` enum/contract
expansion immediately; backfill the corpus from the glossary in
the same change set; close every open call site flagged by issue
#377; lock the audit with a regression test that fails CI when
any `typer.echo`, `_CONSOLE.print`, or `typer.BadParameter` in
`entrypoints/cli/` carries a bare string literal that is not routed
through a `Translatable`.
