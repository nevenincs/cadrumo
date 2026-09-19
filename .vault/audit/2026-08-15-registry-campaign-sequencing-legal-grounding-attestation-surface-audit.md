---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:d9e90292f70f58a96c48afc666548bcb3f2e0dac258af294bc7f98f09e08f00a'
related:
  - "[[2026-07-27-docs-terminology-search-legal-ref-attribution-audit]]"
---

# `registry-campaign-sequencing` audit: `Legal grounding: what local validation can and cannot establish`

## Scope

The registry side of a grounding failure found on Modelo 714, measured against
the whole legal catalogue. The question was not whether that one citation is
wrong -- it is -- but whether local validation is capable of catching a wrong
citation at all, and how large the population is that depends on the answer.

Measured in one pass over the working tree while peers were concurrently editing
the legal catalogue files. Counts belong to that window. No status was stamped,
altered or cleared; nothing was fetched; no corpus file was repaired.

## Findings

### population | medium | two thirds of the catalogue carries the agent attestation, and nothing is unstamped

Six hundred and thirty-three legal-catalogue entries. Four hundred and thirteen
carry the agent status, two hundred and twenty carry the operator status, and
none carries a pending status or no status at all. Every entry declares an
identifier: six hundred and thirty BOE, three BOCM.

### value-backing | medium | the agent-reviewed value population is dominated by dates, not rates

Ninety-seven entries are cited by a surface that carries a regulatory value --
a parameter with a literal amount, or a deadline window. Forty-one of those are
agent-reviewed, fifty-six operator-reviewed. Three hundred and twenty-three
entries are cited only descriptively, by casillas and bindings.

The severity split inside the forty-one matters more than the count. Six back a
numeric coefficient or threshold. Thirty-five back a deadline window: the orden
articles fixing when a modelo is due. A wrong citation under a rate produces a
wrong number; a wrong citation under a deadline produces a missed filing. Both
lists are reproduced below so the judgement is made on the distribution rather
than on the headline.

### local-verification-incapable | high | no link in the chain can establish that a cited excerpt is authentic

Four links, none of which closes.

The excerpt check compares each declared phrase against the corpus file named by
the citation. Where one author wrote both the file and the phrase, this compares
a string to itself through a file and cannot fail.

The corpus manifest records a per-file digest and a self-attesting manifest
digest. That is integrity, not authenticity: it proves the bytes have not changed
since bundling. A file that was wrong when bundled stays wrong, hashed, and
attested.

The declared document identifier is constructed and never compared against the
content of the file it names.

Nothing compares a bundled file to the published original, and locally nothing
can.

### no-statistical-tell | high | a self-referential check is statistically unremarkable

The obvious cheap detector is a coverage ratio: flag an entry whose declared
phrases account for a large share of the file they are checked against. Measured
across all six hundred and thirty-three, the maximum is 0.22 and nothing exceeds
a quarter. The known-bad entry sits inside that normal range.

No threshold on that axis would have flagged it, so the detector is closed by
measurement rather than by argument.

### identifier-agreement-has-no-discriminating-power | high | the one locally closable link turns out not to be closable either

The declared identifier is never checked against the file, and the files do carry
identifiers in their own text, so this looked like a check nobody was running.
It was measured: six hundred and ten files carry an identifier, six hundred and
five contain the identifier their entry declares, five do not, and twenty-three
carry none.

Read as defects that would be five. It is zero. Every one of the five is a
consolidated text citing another norm -- an amending decree, or a framework law
it develops -- without restating its own identifier. That is how published
consolidated legislation is written.

The check has no discriminating power in the other direction either: of the six
hundred and five agreements, three hundred and seventy-seven contain other
identifiers alongside the declared one. The rule cannot separate an identifier a
document asserts about itself from one it merely cites, so agreement is weak
evidence and disagreement is mostly noise.

This is the more important result. Every local avenue is now exhausted, and
authenticity cannot be established without retrieving the published text.

### fabrication-is-internally-consistent | high | the wrong identifier propagated, which is why no internal check sees it

The identifier that resolves to an unrelated municipal notice does not appear
only in the entry that declares it. It appears in the Modelo 714 orden stub, in
two Ley 19/1991 article files that cross-reference the approving orden, and in a
bundled AEAT procedure page -- four source files, plus their derived extractions.

The two Ley 19/1991 entries declare the correct identifier for their own law;
what they carry is the wrong one, inside a cross-reference. So the error is
coherent across the corpus rather than isolated to one field.

That coherence is the mechanism. A fabrication authored in one pass is internally
consistent by construction, and every check available locally tests internal
consistency. The set agrees with itself, and agreeing with itself is all any of
these checks can measure.

### attribution-screen-scope-gap | high | the shipped screen for this class reads one citation surface of two

This class is already recorded, and a screen for it already ships. Its rule is
sound, including the subtlety that declared phrases must be read jointly because
one modelo records its approval phrase and its form number in separate entries.

Driving that screen's own discriminator over compiler-tier data -- because the
screen cannot currently run at all, since it loads through the validated
authority that this campaign's refusals block -- gives zero mismatches on
modelo-level citations and three on revision-level ones. Modelos 187, 188 and 194
each cite an article whose approving text names modelo 193.

The screen reads each modelo definition's own citations. Revision-level citations
are not in its input. Its prose records that the four known cases were corrected
and the worklist reads zero, and that is accurate for the surface it reads: the
correction was applied to modelo-level citations and the revision-level ones were
left. The entries themselves were not altered to silence it, and this was checked
-- the approving text still names modelo 193, and the notes still say so.

All three survivors carry the operator status, which is the part that reframes
the problem: attestation grade does not track attribution correctness, because no
grade's process includes an ownership check.

### the-two-lists | reference | the populations the judgements above are made over

## A. agent_reviewed entries backing a regulatory value

### A1. numeric coefficient or threshold (a rate that computes money)

- `ley-35-2006:art-31` -> parameter(s): lirpf-art-31:eo-exclusion-rendimientos-agricolas-ganaderos-forestales-eur
- `ley-35-2006:dt-32` -> parameter(s): lirpf-dt-32:eo-exclusion-compras-eur, lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur, lirpf-dt-32:eo-exclusion-rendimientos-factura-eur
- `rd-439-2007:art-110` -> parameter(s): rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario, rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrario-objetiva
- `real-decreto-ley-6-2024:anexo` -> parameter(s): rdl-7-2024-art-11-2:iva-simplificado-reduccion-cuota-devengada-2024
- `real-decreto-ley-7-2024:art-11.2` -> parameter(s): rdl-7-2024-art-11-2:iva-simplificado-reduccion-cuota-devengada-2024
- `real-decreto-ley-7-2024:df-14` -> parameter(s): rdl-7-2024-art-11-2:iva-simplificado-reduccion-cuota-devengada-2024

### A2. deadline window (a date operators file against)

- `ley-35-2006:art-25` -> modelo(s) 123, 193
- `ley-35-2006:art-99` -> modelo(s) 100, 111, 115, 123, 130, 180, 193
- `orden-eha-1881-2011:art-4` -> modelo(s) 763
- `orden-eha-3290-2008:art-4` -> modelo(s) 216
- `orden-eha-3316-2010:art-5` -> modelo(s) 210
- `orden-eha-3435-2007:anexo-i` -> modelo(s) 117
- `orden-eha-3435-2007:anexo-iv` -> modelo(s) 126
- `orden-eha-3435-2007:anexo-v` -> modelo(s) 128
- `orden-eha-3481-2008:art-5` -> modelo(s) 189
- `orden-eha-3514-2009:art-6` -> modelo(s) 181
- `orden-eha-672-2007:art-1` -> modelo(s) 130
- `orden-eha-672-2007:art-3` -> modelo(s) 131
- `orden-eha-789-2010:art-10` -> modelo(s) 361
- `orden-hac-1197-2025:art-4` -> modelo(s) 185
- `orden-hac-1400-2018:art-4` -> modelo(s) 233
- `orden-hac-1504-2024:df-unica` -> modelo(s) 721
- `orden-hac-242-2025:art-8` -> modelo(s) 100
- `orden-hac-3580-2003:art-4` -> modelo(s) 156
- `orden-hac-510-2021:art-3` -> modelo(s) 604
- `orden-hac-539-2003:art-4` -> modelo(s) 186
- `orden-hac-590-2021:art-3` -> modelo(s) 490
- `orden-hac-612-2021:art-4` -> modelo(s) 179
- `orden-hac-66-2002:art-6` -> modelo(s) 038
- `orden-hac-85-2003:art-3` -> modelo(s) 848
- `orden-hap-1695-2016:art-4` -> modelo(s) 289
- `orden-hap-2118-2015:art-4` -> modelo(s) 280
- `orden-hap-2368-2013:art-3` -> modelo(s) 270
- `orden-hap-2455-2013:art-4` -> modelo(s) 165
- `orden-hap-70-2013:art-7` -> modelo(s) 136
- `orden-hfp-227-2017:art-5` -> modelo(s) 222
- `orden-hfp-823-2022:art-4` -> modelo(s) 345
- `orden-hfp-886-2023:art-4` -> modelo(s) 721
- `orden-min-2000-12-15-m341:art-2` -> modelo(s) 341
- `rd-439-2007:art-100` -> modelo(s) 115, 180
- `rd-439-2007:art-109` -> modelo(s) 100

A1 count: 6   A2 count: 35   total: 41

## B. revisions whose entire revision-level grounding is agent_reviewed

- modelo 100 revision `2020` -- 15 citation(s), none operator-attested
- modelo 100 revision `2021` -- 6 citation(s), none operator-attested
- modelo 100 revision `2022` -- 6 citation(s), none operator-attested
- modelo 100 revision `2023` -- 6 citation(s), none operator-attested
- modelo 100 revision `2024` -- 6 citation(s), none operator-attested
- modelo 136 revision `2026` -- 9 citation(s), none operator-attested
- modelo 145 revision `2012-01-31-y-siguientes` -- 4 citation(s), none operator-attested
- modelo 189 revision `2025` -- 5 citation(s), none operator-attested
- modelo 280 revision `2025` -- 7 citation(s), none operator-attested
- modelo 289 revision `2025` -- 20 citation(s), none operator-attested
- modelo 345 revision `2025` -- 13 citation(s), none operator-attested
- modelo 361 revision `2010-y-siguientes` -- 4 citation(s), none operator-attested
- modelo 379 revision `2024-y-siguientes` -- 5 citation(s), none operator-attested
- modelo 714 revision `2021-y-siguientes` -- 5 citation(s), none operator-attested

B count: 14

## Recommendations

Widen the shipped attribution screen's input to revision-level citations. Its
discriminator is already correct and already finds the three survivors when fed
that surface; only the function that collects citations needs to read revisions
as well as modelo definitions. This is a small change to a validated instrument
rather than a new one, and it does not disturb the standing refusal recorded
elsewhere against rebuilding a different, abandoned detector.

Do not build a coverage-ratio screen or an identifier-agreement gate. Both were
measured here and both are closed: the first has no signal, and the second has no
discriminating power.

Restore the ability to run the attribution screen. It resolves the registry
through the validated authority, so the refusals installed during this campaign
disable it. An instrument that cannot run while the tree is deliberately red is
unavailable exactly when authoring activity is highest.

Treat retrieval of published text as the verification mechanism rather than as a
repair task. That is the conclusion the measurements force: local validation can
establish that our records agree with each other, and nothing more.

A follow-on decision record must rule on what evidence a citation requires before
it may back a filing-grade value, given that no locally computable check can
supply it. That decision also has to say what happens to the forty-one and the
fourteen below in the meantime, because they are not defects -- they are the
population whose correctness is currently unestablished in either direction.
