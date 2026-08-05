---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:7782635d9f01b39801d7ad51bc76f62e889c6083c198e10371bd8920f79004a6'
step_id: 'S21'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Bundle the place-of-supply articles governing cross-border category selection, so the judgement is grounded rather than derived from counterparty country

## Scope

- `src/cadrumo/_data/corpus/normatives/html`

## Description

- Retrieve LIVA arts. 68, 69 and 70 and RIRPF art. 76 from the live BOE consolidated
  text through the datosabiertos block API, selecting the redaction currently in force
  for each article rather than the first published version.
- Discover that the three place-of-supply articles were already bundled and catalogued,
  resolving to anchored units of the bundled consolidated LIVA document; verify the
  bundled text against the live text instead of authoring a duplicate excerpt.
- Record on each of the three catalogue entries that the articles are the rule set
  deciding which IVA category a cross-border operation falls in, that the selection is
  a declared operator judgement, and the result and date of the live check.
- Bundle RIRPF art. 76 as a new corpus excerpt authored from the live text, with the
  extraction sidecars produced by the production extractor.
- Add the art. 76 legal catalogue entry, recording the two carve-outs that restore the
  withholding obligation for a non-resident payer.
- Promote the component table's pending art. 76 marker into a real citation and upgrade
  the seven affected rows from live-source-only to bundled-corpus grounding, in the same
  commit as the bundling. Four edit sites produce those seven rows: one shared builder
  is called four times and three rows are declared inline.
- Re-key the note requirement on the retención expectation after code review found the
  grounding upgrade had crossed a validator boundary, drop the covering test's
  bundled-corpus short-circuit, and add the refusal test.
- Add the statute half of the confirmation basis to the same seven rows, and date the
  bundled art. 76 redaction from its own bytes.

## Outcome

Three commits. `registry(iva): bundle RIRPF art. 76 and retire the pending retencion
marker` adds the art. 76 excerpt and its two extraction sidecars, the catalogue entry,
and the component-table promotion as one unit. `registry(iva): declare LIVA arts. 68-70
as the category-selection grounding` records the place-of-supply role and the live
verification on the three existing entries. A third commit answers the code review.

Code review returned one high finding against the promotion, and it was correct. The
note requirement was keyed on the grounding column, so upgrading the seven rows to
bundled-corpus lifted them above the gate and made the carve-out disclosure optional on
exactly the rows whose "no retención" is a default rather than a rule. A grounding
upgrade must never be able to switch a disclosure off. The requirement is now keyed on
the expectation as well: a NOT_EXPECTED retención requires its note however well
grounded. Nothing had shipped without the notes, so this closed a latent hole rather
than a live defect.

The three place-of-supply articles needed no new corpus file. Their anchored units in
the bundled consolidated LIVA document are character-identical to the current
redactions in force, once the amendment-history footnotes the BOE consolidated page
appends after each article body are set aside. Authoring per-article excerpts would
have duplicated authoritative text the repository already ships.

The art. 76 bundling and the marker promotion had to be one commit because the two
governing gates are inverses: one requires every cited reference to resolve in the
catalogue, the other requires every reference marked pending to be absent from it.
Landing the corpus and the entry without the promotion would have reddened the second
gate for every campaign sharing the tree.

## Notes

Gates run sequentially, not under parallel workers. Before the change: 72 passed, 0
failed across the registry legal-grounding gate, the component-expectation gate and the
retencion-parameter gate. After the change, with the extraction-sidecar freshness gate
added: 81 passed, 0 failed. A wider catalogue-verification pass over the same surface
plus the normatives verifier and the whole IVA domain test package: 373 passed, 0
failed. For the review remediation, the component-expectation and legal-grounding gates
were 68 passed, 0 failed before, and 78 passed, 0 failed after with the sidecar gate and
the new refusal test included.

Both changes carry mutation proof rather than a green run alone. Feeding the gate's own
pending-reference extractor the pre-change bytes of the component module reports exactly
one reference marked pending, and that reference is now in the catalogue, so the gate
would have failed had the promotion been split out; feeding it the post-change bytes
reports an empty set. Negating a required-text phrase on the new art. 76 entry, and
pointing its corpus reference at a different bundled file, are both refused by the
catalogue verifier. Pointing it at a wrong anchor within the same single-unit file is
accepted, because the verifier falls back to the whole file when an anchor does not
resolve; on a multi-unit file the anchor is load-bearing and a wrong one is refused.

The new note requirement carries its own mutation proof, run against the seven real
rows rather than a synthetic one. Stripping the note from each and rebuilding it is
refused by the new expectation-keyed rule on all seven, while the old grounding-keyed
rule would have fired on none of them, so the guard closes exactly the gap the review
identified. The positive control holds in the other direction: a bundled row whose
retención expectation is unknown is still accepted with no note, so the rule
discriminates the not-expected expectation rather than banning empty notes outright.

The provenance of every authored entry is recorded as agent authorship from the live
consolidated text, pending an operator re-stamp. No operator stamp was claimed. The
art. 76 entry additionally records an unresolved question for that re-stamp: its
effective date is the one the BOE block API reports for the redaction, which coincides
with the amending decree's publication date, and whether the amendment took effect on
publication or at the start of the following year was not established here. The date
was left as retrieved rather than guessed, and the doubt written down.

The art. 76 excerpt reproduces the consolidated page's own amendment history verbatim,
in the same markup the bundled consolidated law uses, so the redaction the excerpt
carries can be dated from the bundled bytes alone instead of only from the catalogue
entry beside them.

Two pre-existing defects were recorded rather than corrected. The place-of-supply entry
for the entregas article states its 1993 original entry into force while the bundled
text is the 2023 redaction, and it belongs to a batch of six operator-stamped entries
carrying the law's short name in place of its BOE document identifier. Correcting one
member of a six-entry batch would leave the batch less coherent than it is now, and
reshaping the batch is outside this Step.

The component module does not satisfy the repository formatter at a line unrelated to
this work. The same line fails on the committed bytes that preceded this change, so it
was left alone rather than swept into this commit.

The review's remaining findings were left to their owners: correcting the six-entry
batch that carries the law's short name instead of its BOE identifier is a whole-batch
change needing an operator re-stamp, the effective date itself is that operator's call,
and the Scope block above is machine-filled from the plan row.

Verification of two neighbouring Steps was carried out read-only and reported, with no
Step state changed: the legal catalogue entries the component table cites all resolve,
and the retencion rate parameters exist as registry data, are read through a
registry-backed loader, and replaced the feature-module literal at both of its call
sites.
