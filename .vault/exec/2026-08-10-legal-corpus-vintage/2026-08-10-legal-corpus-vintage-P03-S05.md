---
tags:
  - '#exec'
  - '#legal-corpus-vintage'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:2efe2983f835a7e10adf4ecebce458ee8a5d9a29f9b89dce23d8ca578871a62f'
step_id: 'S05'
related:
  - "[[2026-08-10-legal-corpus-vintage-plan]]"
---

# Acquire the redaction history for the 157 excerpt-backed entries that have no bundled consolidated counterpart, through dev/corpus/fetch_boe_normative.py and never by hand. Three traps are already measured and must be carried: act.php lists versions NEWEST first while the open-data article endpoint concatenates them OLDEST first, so a take-the-last rule is right for one and bundles repealed law for the other

## Scope

- `a fresh BOE payload is CRLF while .gitattributes declares eol=lf`
- `so the extracted sidecar records a sha that no checkout reproduces unless the source is normalised to LF BEFORE extracting`
- `and legal text must never pass through a shell. Read every written file back before trusting it`
- `src/cadrumo/_data/corpus/normatives/html/`

## Description

- Derive the population programmatically from the legal catalogue rather than
  from any published count, classifying every corpus payload by its own bytes.
- Resolve each entry's BOE document and article block, refusing rather than
  guessing where the bundled evidence does not settle it.
- Acquire each article's redaction history through the existing acquirer,
  serialised with a delay, with an empty required_text.
- Normalise the fetched bytes to LF before extracting, then re-validate the
  normalised payload through the acquirer's own in-force assertion.
- Generate the sidecar pairs with the production extractor and prove each pair
  through the production loader.
- Commit the payloads and sidecars with an explicit pathspec.

## Outcome

**Population: 116 entries, not 157.** The count was measured here rather than
taken from the reference, and it is materially lower for two compounding
reasons. Peers have bundled many more whole consolidated documents since the
reference was written -- 44 distinct norms now carry one, and every fragment
whose norm has one is measurable and therefore out of this population. And the
reference's own denominator is unreliable, as the sibling row already
established. The derivation reported here: 628 catalogue entries, 323 whose
corpus_ref points at a per-article fragment, 207 of those with a consolidated
oracle, leaving 116 without.

**Classifying the corpus by marker does not work, and this cost a rewrite.** A
first classifier keyed on the canonical excerpt header comment and put 135 of
395 payloads in an unclassifiable bucket, because the corpus has accumulated at
least four header conventions and the oldest fragments carry none at all. A
second keyed on the presence of a version selector and mis-called every article
fragment sliced before the extractor learned to strip that widget. What actually
discriminates is SCOPE: a whole consolidated document wraps each article in its
own bloque div and carries hundreds, a fragment carries one unit heading and no
wrapper. Measured, the consolidated IVA law has 300 bloques and 243 article
headings against its own article-90 fragment's 0 and 1.

**Acquired 58, deduplicated 3, refused 55.** The 58 payloads span 23 norms and
456 KB, largest 112 KB, carrying between 1 and 23 redactions each.

**The refused class is not the one the acquirer's own documentation predicts,
and this is the finding.** That documentation records that BOE holds no
consolidated text for bilateral tax conventions "at all". That is measurably
false. Belgium, Germany, France, Portugal, the United Kingdom, the United
States, Morocco and the Netherlands all have consolidated records, and all are
acquired here. Only the Argentina 1992 convention does not. The real refused
class is annual modelo-approval ordenes, which BOE does not consolidate. Every
refusal is evidenced twice independently: the consolidated index answers 404 for
the document, AND a request to the consolidated whole-document view redirects to
the single-document view, which is the provenance marker the acquirer already
documents. Six of the refusals additionally had no resolvable article at all --
apartados addressed by ordinal word and annexes naming a modelo form.

**The block anchor is not derivable from the article number, and a first sweep
proved it the expensive way.** Deriving the block by convention mis-refused 59
of 116 rows on a 404, and the 404 was initially read as "this document has no
consolidated text". A control settled that it says nothing of the kind: a
deliberately bogus block on a document whose consolidated text demonstrably
exists answers 404 as well. The block grammar simply is not uniform across BOE's
corpus. Article 11 of the Spain-Morocco convention lives at block ar-10; article
10 of the Spain-Netherlands convention lives at a1-2; the two apartados of one
2003 orden live at pr-2 and se-2 under the titles Primero and Sexto. Each of
those would have been silently wrong or silently missing. The block is therefore
looked up in BOE's own block index and matched on BOE's own title, and a
non-unique match refuses rather than picks.

**22 acquired rows carry a catalogue anchor that disagrees with BOE's real block
id.** Recorded as evidence, not acted on: repointing an anchor is adjudication
and this phase is acquisition.

**The CRLF trap did not fire, and the ordering is kept anyway.** Every payload
this endpoint served was already LF-only, so no file needed rewriting. The
normalisation still runs on bytes before extraction, because the next fetch
carries no such guarantee and the failure is invisible when it happens. The
proof is against the committed tree rather than the working copy: for all 58
payloads the sidecar's recorded source digest equals the digest of the blob as
committed, and no committed blob contains a carriage return.

**Gates.** The corpus sidecar freshness sweep passes with all 58 new pairs
present. The registry suite reported 68 failures, none of them this surface. Nine
carry the loader's own concurrent-registry-write refusal, which is the documented
symptom of peers writing registry data during the run; the rest sit in peer
campaigns on modelo 232, 390, 303, 180, 190 and 100, revision spans, export
offsets and schema hygiene, none of which read the legal corpus. The one gate
that could plausibly have been this surface -- the ratchet on catalogue entries
whose anchor nothing verifies -- was settled by a control rather than by
argument: with these 174 files relocated out of the tree it fails at 90 against
an 89 ceiling, and with them restored it fails identically at 90. This change is
neutral on it. That ratchet is a pre-existing peer regression.

## Notes

- **No adjudication was performed.** No catalogue entry, corpus_ref,
  required_text, effective_from or test was touched. The commit is evidence
  only.
- **A pre-existing extractor artefact ships with these sidecars.** The
  production normatives extractor has no article-heading delimiter to split the
  article-endpoint XML shape on, so it falls back to a whole-document unit and
  the response envelope's status tokens lead the extracted text in 57 of the 58
  new sidecars. This is not a regression introduced here -- one of the two
  article-endpoint payloads already bundled carries exactly the same artefact.
  Left as-is deliberately: the extractor is shared production code well outside
  this row's scope, and changing it would also churn the two existing sidecars.
  It adds one junk clause per file to any clause-level comparison built on these
  sidecars, which the following row should know about.
- **The driver was not committed.** It is a one-off composition over the
  existing acquirer, the existing extractor and the existing sidecar writer,
  re-deriving none of them; the precedent for an article-endpoint acquisition
  bundles the evidence without adding a module, and this row's scope is the
  corpus directory.
- **Requests were serialised throughout** with a fixed delay and never
  parallelised. Legal text passed through no shell at any point: every payload
  was written by the acquirer and read back off disk in binary.
- **Code review has not been run on this change** and is outstanding.
