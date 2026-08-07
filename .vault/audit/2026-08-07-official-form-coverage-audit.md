---
tags:
  - '#audit'
  - '#official-form-coverage'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:998c8341aa028be0dccfced791b3b100c800c6dbe1dbce88da2a2c8291ac0b09'
related: []
---
## Scope

An audit of what the registry can actually be checked against. Triggered by a
standing concern that the completeness gates might be measuring the registry
against itself, and pursued until each claim was grounded in an artefact
outside the registry.

Covered: every modelo revision bundling an official AEAT Diseño de Registros
(38 of them); the casilla-to-box-number metadata across the whole registry
(9,000+ casillas); the legal evidence check's required-text grounding (599
entries); and the Modelo 303 filing surface where the largest coverage gap
landed.

Not covered: whether the casillas the registry DOES declare compute correct
values. This audit asks only what can be seen, not whether what is seen is
right.

## Findings

### external-form-check-blind-on-36-of-38 | critical | The only instrument comparing the registry to the official form silently reported zero gap for 36 of 38 revisions

Every completeness gate but one measures the registry against a set derived
from the registry: the manifest against the calculation closure, the export
gate against the manifest. None can see a casilla that exists on the real
modelo and was never authored. The single external check is the full-Diseño
coverage report, which compares declared casillas against the official AEAT
record design.

It extracted box numbers with a five-digit bracketed pattern. That is the
Impuesto sobre Sociedades convention; Modelo 200 and Modelo 220 write tags that
way and were the only two revisions ever driven through the report. Modelo 303
writes two and three digits, Modelo 390 two, Modelo 036 two and three. The
pattern matched nothing on them, and a matchless sweep does not raise: it
yields an empty set, from which the report computes zero total, zero covered
and zero gap. The failure presented as the good news.

Fixed by widening the pattern to one-to-five digits, bounded rather than
open-ended so amounts and position offsets bracketed in the same columns are
not admitted. Readable revisions went from 2 to 22.

### unread-and-covered-were-indistinguishable | high | An empty coverage gap could mean full coverage or an unread form, with nothing to tell them apart

Widening the pattern left 16 revisions still extracting nothing, because they
annotate their casillas outside bracketed field text entirely. Those would have
continued to read as fully covered. The report now carries an explicit
extraction-found-nothing flag: an official record design always declares
casillas, so an empty extraction is a limitation of the extraction and never a
property of the form. Ten revisions are now provably at zero gap, which is real
good news that was previously indistinguishable from having been unread.

### box-number-lives-in-two-fields | high | A box the registry computes and exports was reported as unauthored because the comparison read the wrong field

The comparison keyed the registry side on the casilla number field. That field
does not reliably hold the official box number: a casilla whose identifier is a
domain name rather than a box number tends to repeat that identifier in the
number field and record the official box separately.

Modelo 303's régimen-general result is the worked example. It IS box 46, its
downstream formula reads box 64 as box 46 plus 58 plus 76, and it exports to
the box 46 record field, yet it was reported as an unauthored Diseño casilla. A
false gap is as damaging as a missed one: it puts real work on a backlog long
enough to hide the genuine entries. Fixed by preferring the form-number field
and falling back to the number field.

### unnumbered-casillas-are-not-a-defect | low | 646 casillas record no box number anywhere, and the existing design does not require them to

Measured while investigating the finding above and recorded because the raw
figure invites the wrong conclusion. Only 18 of the 646 document a reason for
having no box number. The remaining 628 are not in breach: the export-exemption
validator scopes its requirement to casillas inside the completeness manifest,
and these sit outside it. Many are legitimately internal — intermediate
aggregates feeding an addressed casilla, declarante metadata, and fichero field
codes that are themselves the official identifier.

No action. Logged so a later reader measuring the same number does not open a
remediation campaign against a deliberate design.

### m303-three-unauthored-form-blocks | medium | Three whole blocks of the Modelo 303 form are absent from both the casilla set and the export layout

With the instrument fixed, Modelo 303 shows 84 official boxes the registry does
not declare, in three coherent families rather than scattered: the
annual-summary substitute block filed by taxpayers exonerated from the annual
IVA return; the prorratas block carrying up to five per-activity rows of CNAE,
operation volume, deductible volume, prorrata type and percentage; and the
régimen de deducción diferenciada block carrying two sectors of deduction
detail.

Confirmed absent from the export layout as well as the casilla set — the
layout's highest numbered field stops well below any of these blocks — so the
fichero cannot carry them either.

The prorratas finding has a structural edge worth naming: the registry models a
single global prorrata (total volume, volume with deduction right, percentage)
while the official form models up to five per-activity prorratas. That is a
shape difference, not only a missing-box difference, and it is what a follow-on
decision has to settle.

### exonerado-390-is-unreachable-not-wrong | low | The annual-block gap is latent because nothing can set the flag that requires it

Assessed before treating the annual-summary block as a live filing defect. The
export layout does declare the exonerado-390 header field, but the header is
not classified by the user-profile schema, so nothing populates it and the
contract check already emits a warning saying so. A taxpayer cannot mark
themselves exonerated through the application at all.

The gap is therefore an unsupported taxpayer population, not a silently wrong
filing. Where an exonerated taxpayer did export, the blank flag declares them
not exonerated, which errs toward also filing the annual return — the safe
direction. Severity set accordingly; this is a missing feature, not an
under-declaration.

### legal-grounding-quoted-headings-not-provisions | high | The evidence check confirmed an article heading was present and nothing more, on a population of 56

The legal evidence gate asserts an entry's required text appears in its corpus
excerpt. That proves the excerpt is the right document only when the quoted
phrase comes from the operative provision. When it quotes the article title, or
a term from the first sentence, the check confirms a heading — and a heading is
the first line of the file, so it survives any truncation of everything
beneath.

One entry was confirmed genuinely truncated: the LIVA right-to-deduct article
was bundled cut off mid-first-apartado in a superseded redaction, missing two
apartados and the point that grounds treating exports and intra-community
supplies as originating the right to deduct. It was stamped reviewed. Refreshed
from live BOE and requoted; two further articles, the LIVA interior-exemptions
article and the LIS related-party article, were requoted after confirming
against live BOE that both were complete. A shrink-only ratchet now pins the
population, currently 54, with its anti-tautology proof bound to the largest
remaining entry so it retires only when the worst case is genuinely fixed.

### grounding-gate-read-the-wrong-artefact | high | A gate built to measure legal grounding measured a file no grounding check consults

The corpus refresh above did not take effect when first landed, and the reason
generalises. The legal corpus resolution reads an extracted JSON sidecar, not
the corpus HTML: the HTML is an input to extraction and the sidecar is what
every grounding check consults. The refreshed article sat on disk while the
truncated extraction still grounded every citation.

The ratchet gate had the same defect one level up, and it is how the population
figure moved from 32 to 56: 24 entries were heading-only on the artefact that
grounds filings while reading as body-grounded on the artefact nobody consults.
Both are now bound to the production resolution. A corpus refresh must
regenerate the sidecar pair in the same change, through the owning generator
rather than by hand, because the sidecar carries a source digest the loader
cross-checks.

## Recommendations

Author the three Modelo 303 blocks against the official instrucciones and the
governing orden, one family per change, with the casillas, the export-layout
fields and the four-locale entries landing together. The prorratas family needs
a decision first, not just authoring: whether the registry adopts the form's
per-activity prorrata rows or keeps a single global prorrata and maps it. A
follow-on ADR must make that call, because it changes a persisted shape rather
than adding boxes to an existing one.

Classify the exonerado-390 header in the user-profile schema only as part of
that annual-block work, never before it. Making the flag settable while the
block it requires is unrepresentable would convert a latent unsupported case
into a live wrong-file case, which is the one change here that would make
things worse.

Continue the heading-only legal backlog largest-first, cross-checking each
article against live BOE before requoting so a phrase is never pinned to an
already-truncated excerpt. The ratchet enforces the cadence; the remaining work
is one legal reading per entry.

Extend the Diseño extraction to the 16 revisions whose annotation sits outside
bracketed field text, so their coverage becomes measurable rather than
explicitly unknown. Until then their reports carry the extraction-found-nothing
flag, which is honest but is not coverage.
