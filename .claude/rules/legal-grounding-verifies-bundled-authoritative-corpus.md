---
name: legal-grounding-verifies-bundled-authoritative-corpus
trigger: always_on
---

# Verify legal grounding against the bundled authoritative corpus

## Rule

When authoring or grounding any regulatory value — a registry `legal_refs` to
`corpus_ref` entry, a `corpus/normatives/html/*.html` excerpt, an
`external_constants` figure — verify the legal text against the BUNDLED
authoritative consolidated corpus already shipped under
`src/cadrumo/_data/corpus/normatives/html/` FIRST. Never author a new corpus
excerpt from a secondary source — a blog, a summary site, a paraphrase —
without that cross-check, and prefer pointing `corpus_ref` at the bundled
authoritative file over hand-authoring a duplicate excerpt.

**The bundled corpus is preferred but NOT infallible.** For any numeric AMOUNT
or RATE, cross-check the figure against the live BOE or AEAT consolidated text
even when the bundled corpus already states it.

## Why

An excerpt authored from a secondary source carried a fabricated year list while
the repo already bundled the authoritative text — and the `required_text`
cross-check was tautological, because the same author wrote both the excerpt and
the phrase that validated it, so it confirmed internal consistency rather than
faithfulness to the BOE. The same root cause has recurred on rate and amount
defects, in both directions: an excerpt that was wrong, and a bundled corpus
figure that was wrong.

## How

- **Good:** before authoring a legal entry, `rg` the bundled consolidated file
  for the provision's anchor, read the verbatim text, and point `corpus_ref` at
  that bundled file with a `required_text` phrase distinctive enough to match
  only the target provision.
- **Good:** when the bundled corpus is a deliberately non-authoritative anchor
  snippet — empty `required_text`, or a catalogue-note disclaimer — treat the
  registry parameter as the calc authority, verify the value against live BOE or
  AEAT, and flag the snippet for an operator corpus refresh. Do not trust the
  snippet's prose as the rate authority.
- **Good:** when a verification pass touches a numeric amount or rate,
  cross-check against live BOE or AEAT. If the bundled corpus is wrong, correct
  the corpus, the grounded parameter, the legal-entry notes, and any tautological
  test that baked the wrong value, in ONE atomic commit.
- **Bad:** authoring a new corpus excerpt by copying a secondary source and
  citing it from a registry legal entry; the self-referential `required_text`
  gate passes anyway.
- **Bad:** trusting a bundled-corpus amount or rate without confirming the number
  against live BOE or AEAT.
- **Bad:** stamping an agent-authored legal-authority entry as reviewed under the
  operator's name without the bundled-corpus cross-check. The legal catalogue is
  a human-reviewed, filing-grade surface; agent-prepared entries must record
  honest `reviewed_by` provenance pending operator re-stamp.

**A fetched file can still be unfit.** A consolidated-legislation payload carries
every historical version, oldest first, so taking the first block bundles
repealed law under a current filename — and a truncating shell heredoc silently
loses text. Take the last version, assert the amending norm's identifier, never
pass legal text through a shell, and read the file back before trusting it.

## Source

Audit `2026-06-14-aeat-grounding-completion-audit`. Companions:
`registry-calculation-legal-grounding`, `aeat-safety-legal-gates`,
`aeat-calculation-grounding`.
