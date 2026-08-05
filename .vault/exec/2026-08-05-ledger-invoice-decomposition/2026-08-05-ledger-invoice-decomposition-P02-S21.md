---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:80860d17baf2251945ceeb45e7d7afcd8c0d5e84658d33260ee557e0dc21a6c6'
step_id: 'S21'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-invoice-decomposition with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S21 and 2026-08-05-ledger-invoice-decomposition-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Bundle the place-of-supply articles governing cross-border category selection, so the judgement is grounded rather than derived from counterparty country and ## Scope

- `src/cadrumo/_data/corpus/normatives/html` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
  the four affected rows from live-source-only to bundled-corpus grounding, in the same
  commit as the bundling.

## Outcome

Two commits. `registry(iva): bundle RIRPF art. 76 and retire the pending retencion
marker` adds the art. 76 excerpt and its two extraction sidecars, the catalogue entry,
and the component-table promotion as one unit. `registry(iva): declare LIVA arts. 68-70
as the category-selection grounding` records the place-of-supply role and the live
verification on the three existing entries.

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
failed.

Both changes carry mutation proof rather than a green run alone. Feeding the gate's own
pending-reference extractor the pre-change bytes of the component module reports exactly
one reference marked pending, and that reference is now in the catalogue, so the gate
would have failed had the promotion been split out; feeding it the post-change bytes
reports an empty set. Negating a required-text phrase on the new art. 76 entry, and
pointing its corpus reference at a different bundled file, are both refused by the
catalogue verifier. Pointing it at a wrong anchor within the same single-unit file is
accepted, because the verifier falls back to the whole file when an anchor does not
resolve; on a multi-unit file the anchor is load-bearing and a wrong one is refused.

The provenance of every authored entry is recorded as agent authorship from the live
consolidated text, pending an operator re-stamp. No operator stamp was claimed.

Two pre-existing defects were recorded rather than corrected. The place-of-supply entry
for the entregas article states its 1993 original entry into force while the bundled
text is the 2023 redaction, and it belongs to a batch of six operator-stamped entries
carrying the law's short name in place of its BOE document identifier. Correcting one
member of a six-entry batch would leave the batch less coherent than it is now, and
reshaping the batch is outside this Step.

The component module does not satisfy the repository formatter at a line unrelated to
this work. The same line fails on the committed bytes that preceded this change, so it
was left alone rather than swept into this commit.

Verification of two neighbouring Steps was carried out read-only and reported, with no
Step state changed: the legal catalogue entries the component table cites all resolve,
and the retencion rate parameters exist as registry data, are read through a
registry-backed loader, and replaced the feature-module literal at both of its call
sites.
