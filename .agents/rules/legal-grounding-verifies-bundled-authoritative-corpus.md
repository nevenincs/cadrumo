---
name: legal-grounding-verifies-bundled-authoritative-corpus
trigger: always_on
---

# Rule

When authoring or grounding any regulatory value (a registry `legal_refs`→`corpus_ref`
entry, a `corpus/normatives/html/*.html` excerpt, an `external_constants` figure), verify
the legal text against the BUNDLED authoritative consolidated corpus already shipped under
`src/aeat/_data/corpus/normatives/html/` FIRST — never author a new corpus excerpt from a
secondary source (a gestoría blog, a summary site, a paraphrase) without that
cross-check, and prefer pointing `corpus_ref` at the bundled authoritative file over
hand-authoring a duplicate excerpt.

## Why

The honesty review of the grounding-completion campaign found a CRITICAL defect (finding
C1): a módulos DT 32ª corpus excerpt was authored from a secondary source ("supercontable")
with a fabricated year-list ("…2025 y 2026"), while the repository ALREADY bundled the
authoritative consolidated LIRPF (`ley-35-2006.html#dttrigesimasegunda`) whose real text
reads "en los ejercicios 2016 a 2024" and records the 2025/2026 extensions were DEROGADAS
(BOE-A-2026-4667). The `required_text` corpus cross-check was tautological — the same author
wrote both the excerpt and the `required_text`, so the gate validated internal consistency,
not BOE faithfulness. The same root cause recurred as the M210 IRNR interest defect (a
stale bundled corpus snippet phrased art. 25.1.f as EU/EEE-conditional, contributing to a
wrong 24% rate where the law is 19%). And it recurred a third time as the IRPF menor-tres
mínimo defect — the bundled `ley-35-2006-art-58.html` itself carried "3.000 euros" (despite
a header asserting it was the official unchanged BOE text) where the AEAT manual and BOE
state 2.800, grounding a wrong registry parameter and two tautological tests. Grounding a
regulated calc value against a secondary-source or self-authored excerpt is how a wrong
figure ships looking grounded; the bundled consolidated corpus is the faithful source the
project already trusts and is the companion check to `registry-calculation-legal-grounding`
(cite the binding provision) and `aeat-safety-legal-gates` (ground in BOE/AEAT, never
invent). CRITICAL REFINEMENT (from the menor-tres + M210 cases): the bundled corpus is
*preferred* over secondary sources but is NOT infallible — it can carry authored figure
errors. For any numeric AMOUNT or RATE, cross-check the figure against the live BOE/AEAT
consolidated text even when the bundled corpus already states it; a bundled-corpus figure
is a strong default, not a substitute for confirming the number itself.

## How

- **Good:** before authoring a new legal entry, `rg` the bundled `ley-NNNN-AAAA.html`
  consolidated file for the provision's anchor (e.g. `#dttrigesimasegunda`, `#a25`), read
  the verbatim text, and point `corpus_ref` at that bundled file with a `required_text`
  phrase distinctive enough to match only the target provision — so the cross-check
  validates against authoritative text, not a self-written duplicate.
- **Good:** when the bundled corpus is a deliberately non-authoritative anchor snippet
  (its `required_text` is empty / it carries a "Nota de catálogo" disclaimer), treat the
  registry parameter as the calc authority, verify the value against the live BOE/AEAT
  consolidation, and flag the snippet for an operator corpus refresh — do not trust the
  snippet's prose as the rate authority.
- **Good:** when a verification pass touches a numeric amount or rate, cross-check the
  figure against the live BOE/AEAT consolidated text even if the bundled corpus already
  states it — and if the bundled corpus is wrong, correct the corpus, the grounded
  parameter, the legal-entry notes, and any tautological test that baked the wrong value, in
  one atomic commit (the menor-tres 3.000→2.800 fix touched all four).
- **Bad:** trusting a bundled-corpus AMOUNT/RATE without confirming the number itself against
  live BOE/AEAT — the corpus can carry an authored figure error (3.000 vs 2.800) behind a
  header that claims it is the official unchanged text, and the self-referential
  `required_text` gate passes anyway.
- **Bad:** authoring a new `corpus/normatives/html/<provision>.html` excerpt by copying a
  gestoría blog or summary site, then citing it from a registry legal entry — the year-list
  / scope / figures may be stale or wrong, and the self-referential `required_text` gate
  passes anyway (the C1 fabrication pattern).
- **Bad:** stamping such an agent-authored legal-authority entry `review_status = "reviewed"`
  under the operator's name without the bundled-corpus cross-check — the legal catalogue is
  a human-reviewed, filing-grade surface; agent-prepared entries must record honest
  `reviewed_by` provenance and be grounded in the bundled authoritative text pending operator
  re-stamp.

## Source

Audit `2026-06-14-aeat-grounding-completion-audit` (finding C1, reinforced by the M210
art. 25.1.f corpus-staleness finding). Companion rules: `registry-calculation-legal-grounding`
(cite the binding provision), `aeat-safety-legal-gates` (ground in BOE/AEAT, never invent),
`aeat-calculation-grounding` (provenance through boundaries). Promoted per the
`vaultspec-codify` discipline after the lesson held across multiple findings in one campaign.
