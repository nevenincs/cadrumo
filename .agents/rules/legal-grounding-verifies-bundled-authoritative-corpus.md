---
name: legal-grounding-verifies-bundled-authoritative-corpus
trigger: always_on
---

# Rule

When authoring or grounding any regulatory value (a registry `legal_refs`→`corpus_ref`
entry, a `corpus/normatives/html/*.html` excerpt, an `external_constants` figure), verify
the legal text against the BUNDLED authoritative consolidated corpus already shipped under
`src/cadrumo/_data/corpus/normatives/html/` FIRST — never author a new corpus excerpt from a
secondary source (a gestoría blog, a summary site, a paraphrase) without that
cross-check, and prefer pointing `corpus_ref` at the bundled authoritative file over
hand-authoring a duplicate excerpt.

## Why

Per audit `2026-06-14-aeat-grounding-completion-audit` (finding C1): a módulos DT 32ª
excerpt authored from a secondary source carried a fabricated year-list while the repo
already bundled the authoritative LIRPF text, and the `required_text` cross-check was
tautological (same author wrote excerpt and required_text, validating internal consistency
not BOE faithfulness) — the same root cause recurred in the M210 IRNR 24%-vs-19% defect and
the menor-tres 3.000-vs-2.800 mínimo defect. CRITICAL REFINEMENT (menor-tres + M210): the
bundled corpus is *preferred* over secondary sources but is NOT infallible — for any numeric
AMOUNT or RATE, cross-check the figure against the live BOE/AEAT consolidated text even when
the bundled corpus already states it. Companion to `registry-calculation-legal-grounding`
(cite the binding provision) and `aeat-safety-legal-gates` (ground in BOE/AEAT, never invent).

## How

- **Good:** before authoring a new legal entry, `rg` the bundled `ley-NNNN-AAAA.html`
  file for the provision's anchor (e.g. `#dttrigesimasegunda`, `#a25`), read the verbatim
  text, and point `corpus_ref` at that bundled file with a `required_text` phrase distinctive
  enough to match only the target provision — validating against authoritative text, not a
  self-written duplicate.
- **Good:** when the bundled corpus is a deliberately non-authoritative anchor snippet
  (empty `required_text` / a "Nota de catálogo" disclaimer), treat the registry parameter as
  the calc authority, verify the value against live BOE/AEAT, and flag the snippet for an
  operator corpus refresh — do not trust the snippet prose as the rate authority.
- **Good:** when a verification pass touches a numeric amount or rate, cross-check against
  live BOE/AEAT even if the bundled corpus states it; if the bundled corpus is wrong, correct
  the corpus, the grounded parameter, the legal-entry notes, and any tautological test that
  baked the wrong value in ONE atomic commit (the menor-tres 3.000→2.800 fix touched all four).
- **Bad:** authoring a new `corpus/normatives/html/<provision>.html` excerpt by copying a
  gestoría blog or summary site and citing it from a registry legal entry, or trusting a
  bundled-corpus AMOUNT/RATE without confirming the number against live BOE/AEAT — the
  self-referential `required_text` gate passes anyway (the C1 fabrication pattern).
- **Bad:** stamping an agent-authored legal-authority entry `review_status = "reviewed"`
  under the operator's name without the bundled-corpus cross-check — the legal catalogue is
  a human-reviewed, filing-grade surface; agent-prepared entries must record honest
  `reviewed_by` provenance and be grounded in bundled authoritative text pending operator re-stamp.

## Source

Audit `2026-06-14-aeat-grounding-completion-audit` (finding C1 + M210 corpus-staleness).
Companion: `registry-calculation-legal-grounding`, `aeat-safety-legal-gates`,
`aeat-calculation-grounding`.
