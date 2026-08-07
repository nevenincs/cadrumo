# Verify legal grounding against the bundled authoritative corpus

When authoring or grounding any regulatory value — a `legal_refs` to `corpus_ref`
entry, a corpus excerpt, an `external_constants` figure — verify the legal text
against the BUNDLED authoritative consolidated corpus already shipped under
`src/cadrumo/_data/corpus/normatives/html/` FIRST. Never author a new corpus
excerpt from a secondary source without that cross-check, and prefer pointing
`corpus_ref` at the bundled authoritative file over hand-authoring a duplicate.

**The bundled corpus is preferred but NOT infallible.** For any numeric AMOUNT or
RATE, cross-check the figure against the live BOE or AEAT consolidated text even
when the bundled corpus already states it.

An excerpt authored from a secondary source once carried a fabricated year list
while the repo already bundled the authoritative text — and the `required_text`
cross-check was tautological, because the same author wrote both the excerpt and
the phrase validating it, so it confirmed internal consistency rather than
faithfulness to the BOE.

## How

- **Good:** `rg` the bundled consolidated file for the provision's anchor, read
  the verbatim text, and point `corpus_ref` at that file with a `required_text`
  phrase distinctive enough to match only the target provision.
- **Good:** when the bundled corpus is a deliberately non-authoritative anchor
  snippet, treat the registry parameter as the calc authority, verify against
  live BOE or AEAT, and flag the snippet for an operator corpus refresh.
- **Good:** if the bundled corpus is wrong, correct the corpus, the grounded
  parameter, the legal-entry notes, and any tautological test that baked the
  wrong value, in ONE atomic commit.
- **Bad:** authoring an excerpt from a blog or summary site — the
  self-referential `required_text` gate passes anyway.
- **Bad:** stamping an agent-authored legal entry as reviewed under the
  operator's name without the cross-check. The legal catalogue is a
  human-reviewed, filing-grade surface.

**A fetched file can still be unfit.** A consolidated-legislation payload carries
every historical version, oldest first, so taking the first block bundles
repealed law under a current filename; and a truncating shell heredoc silently
loses text. Take the **last** version, assert the amending norm's identifier,
never pass legal text through a shell, and read the file back before trusting it.

Source: audit `2026-06-14-aeat-grounding-completion-audit`. Companions:
`registry-calculation-legal-grounding`, `aeat-safety-legal-gates`.
