---
tags:
  - '#reference'
  - '#llm-package-split'
date: '2026-08-06'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:0b54cd06e33e86d3df736275579d28d409cb82d6515e7a438c4ffc927a55c186'
related:
  - "[[2026-08-06-llm-package-split-adr]]"
---

# `llm-package-split` reference: `Measurement basis: every quantitative claim with its key, sample size and provenance`

## Summary

**Read this before quoting any number from this campaign.** The measurement harness, its
corpus and its result artefacts live in a scratch directory outside the git tree and will not
survive a session handoff. This document is the durable record of what was measured, against
which key, at what sample size, and with what caveat. Every figure below was recomputed
directly from the result artefacts rather than restated from a prior document's prose, because
two successive drafts of the governing ADR carried figures that could not be reproduced.

**A receiving team cannot re-run any of this.** Live model inference is barred — a prior
session's inference run crashed the development host and terminated four concurrent agent
sessions — and the corpus is not in the repository. Treat every figure here as final for this
campaign. Where a re-measurement is genuinely needed, the offline procedures are recorded at
the end, not started casually.

### The keys

Three scoring passes exist and they are **not interchangeable**. Any figure quoted without its
key is unsafe.

| Pass | Key | Scope | Status |
|---|---|---|---|
| pre-v4 | **unstamped** | 94-document corpus, 54 parsed records | superseded; figures scored against it are withdrawn |
| v4 | `7b04d81e40ab...` | 302-document corpus, 103 parsed records | superseded by v5 |
| **v5** | **`e2db6a499f6f...`** | 102 parsed rows, 56 scoreable | **current; every surviving figure is keyed here** |

The v5 key is embedded in the rescore artefact as `ground_truth_sha256` and is the same key the
vision runs scored against, which is what makes the two axes comparable at all.

### The metric trap that must not be repeated

Each result row carries **two** accuracy fields, and they diverge sharply:

- **`accuracy_present`** — correct over all ten scored fields. **This is the metric every
  figure below uses.**
- `accuracy_representable` — correct over only the fields the application's prompt can express.

For the incumbent vision model the two read **75.8%** and **100%** respectively. Reading the
wrong one makes the vision models look flawless and makes the published figures look
fabricated; it produced exactly that false conclusion once during this trace before being
caught. If a future re-score disagrees with this document, check which field it used before
concluding anything.

### Structured parsing, v5

| Claim | Value | Basis |
|---|---|---|
| Mean field accuracy | **82.1%** | mean `accuracy_present` over the 56 rows carrying a non-null truth, of 102 parsed |
| Scoreable / unscoreable | **56 / 46** | the 46 have no truth in the key, not a parser failure |
| Wrong fields | **34** total, **22** in ZUGFeRD | |
| Missing fields, ZUGFeRD | **0** | the parser finds every field and selects the wrong one — a selection bug, not a coverage gap |
| ZUGFeRD | **88.5%**, n=20 | |
| Facturae | **88.8%**, n=17 | |
| UBL | **100%**, n=2 | **cell far too small to carry weight** |
| TicketBAI | 50.8%, n=6 | |
| VeriFactu | 81.6%, n=10 | |
| Loud refusal | one document refused with a parse error and produced **no record** | the fail-loud property the decision rests on |

**Withdrawn:** an earlier 88.2% over 53 documents, and a claim that ZUGFeRD and UBL were both
exact. Both were scored against the unstamped pre-v4 key.

### Parse latency is jittery across passes — quote the range, never a point

This is the single most important correction in this document. Parse latency varies materially
between passes, so a point value misrepresents it:

| Pass | Median parse | Worst parse |
|---|---|---|
| pre-v4 (unstamped) | 0.926 ms | 163.61 ms |
| v4 (`7b04d81e`) | 0.815 ms | 106.28 ms |
| v5 (`e2db6a49`) | 0.593 ms | 70.28 ms |

**Quote the median as a range: 0.59–0.93 ms. Quote the worst parse as a range: 70–164 ms.**

An earlier draft quoted a worst parse of **86.8 ms**, which appears in no artefact and is
withdrawn as phantom.

### The 5,200x-versus-8,000x discrepancy is reconciled, not an error

Two campaign documents stated **~5,200x** while the ADR stated **~8,000x**, and this looked
like a contradiction. It is not. **Both anchor to real observed passes** and differ only in
which median is the denominator:

- 4.81 s / **0.926 ms** (pre-v4 median) = **5,194x** ≈ 5,200x
- 4.81 s / **0.593 ms** (v5 median) = **8,118x** ≈ 8,100x

Neither is wrong; each is right about its own pass. The honest presentation is the range
**~5,200–8,100x**, and a future reader should not "correct" one to the other.

### Latency multipliers, stated with numerator, denominator and statistic

All against the structured parse medians above. Each model figure is its own median wall time
over its run.

| Comparison | Multiplier | Arithmetic |
|---|---|---|
| vs the incumbent vision model (4.81 s) | **~5,200–8,100x** | 4.81 s over 0.926–0.593 ms |
| vs the **slowest measured** model (37.59 s) | **~40,000–63,000x** | 37.59 s over 0.926–0.593 ms |
| **honest floor** — worst parse against fastest model | **~29–68x** | 4.81 s over 164–70 ms |

Two corrections ride here. A previously quoted flat **"20,000x"** was derived from mid-range
models and a superseded median, and is withdrawn. **"~29,000x against the slowest tested" is
mislabelled, not miscomputed**: ~29,000x is the correct multiplier against the 17.23 s model,
but that is **not** the slowest — the slowest measured is the 37.59 s model, giving
~40,000–63,000x.

On the honest floor: the like-for-like v5 pairing (4.81 s over 70.28 ms) gives **68x**. Pairing
the v5 fastest model against the pre-v4 worst parse gives **29x**, which is more conservative
but crosses passes. An earlier **55x** derived from the phantom 86.8 ms and is withdrawn. State
the floor as a range and say which pairing produced each endpoint.

### The vision axis is three documents. This is the caveat that matters most.

| Model | `accuracy_present` | Median wall | n |
|---|---|---|---|
| incumbent 3B vision default | **75.8%** | **4.81 s** | 3 |
| 2B successor | 75.8% | 15.59 s | 3 |
| 4B successor | **78.8%** | **17.23 s** | **2** (third call failed) |
| 3B OCR-specialist — **slowest measured** | 71.7% | **37.59 s** | 3 |
| small 2B baseline | 4.2% | 6.67 s | 3 |

**Every vision figure rests on three documents**, against 56 for the structured path. The
measured structured-versus-vision margin is 82.1% against 75.8% — **6.3 points across a
three-document cell, which is within the noise such a sample produces.** The governing decision
therefore claims **no accuracy advantage** and rests instead on the fail-loud property, the
latency gap and the zero marginal dependency cost, each of which is measured on a cell that can
carry it.

Two further caveats the harness records against its own interest: most documents in the vision
run were **synthetic**, and synthetic renders are cleaner than photographed receipts, so these
figures are likely **optimistic**; and no variance claim is made anywhere, because n=3 cannot
support one.

### Hallucination counts measure the key, not the parser

**Do not quote a hallucination rate in any form.** Across only the 56 scoreable rows the count
is **9, all in ZUGFeRD**. Across all 102 rows it is **453** — ZUGFeRD 289, UBL 104, Facturae 60
— because a row with no truth in the key counts every emitted field as unmatched. An earlier
draft's claim that the hallucinations are "wholly concentrated in ZUGFeRD" is therefore **false
at corpus level** and is corrected here. The figure becomes meaningful only once the
wrong-identifier defect is fixed and the key's gaps are closed. The accuracy figures above are
unaffected, being computed only over fields with a non-null truth.

### Corpus composition — confirmed exact against the v5 key

An earlier verdict called these untraceable. **That verdict is withdrawn**; all four are
confirmed:

- **130** vision-path documents in the v5 corpus
- **124** of them scoreable
- **107** of those real rather than synthetic
- **28** of the 124 carry a non-empty stage-1 reference transcription, 135–1743 characters

These matter because they bound what a future measurement could achieve: the vision matrix
could be re-run at roughly **40x** its current sample size, and the stage-isolation run that
would settle the pipeline shape is **executable today** and simply was not run.

**What the corpus does not establish:** what share of documents a real user receives as
structured XML versus as a photograph of a paper receipt. The corpus was **curated, not sampled
from user traffic**, so it bounds nothing about real-world format mix. The accurate claim is
that where a structured record exists the deterministic path is better on every measured axis,
not that structured records are the common case.

## Offline measurement procedures

Both require **live model inference, which is barred by default**. Neither may be started
casually, and neither is a precondition of the current campaign. Run only with the fleet
quiesced and explicit authorisation.

**Stage-1 / stage-2 isolation — the measurement that decides the pipeline shape.** Preconditions:
fleet quiesced, GPU showing under 1 GB in use, the model host running with nothing else
resident. Documents: the 28 v5 vision-path documents carrying a non-empty reference
transcription. Runs: three pipelines over the same 28 documents with one model — single-shot,
two-stage, and stage-2 fed the reference transcription instead of the model's own stage-1
output. The third minus the second isolates OCR error; 100% minus the third isolates
classification error on perfect input. If the third is near 100% the extraction problem is
entirely OCR and a better vision model is the lever; if it is materially below, the classifier
is a genuine error source no OCR improvement fixes. Roughly 84 calls. **Until this exists,
neither pipeline shape should be adopted** — which is exactly why the governing ADR leaves the
shape open.

**Vision matrix at usable sample size.** The 124 scoreable vision-path documents, 107 of them
real, across the incumbent and two successor models. This would move every figure in the vision
table above from a three-document claim to a real one, and is the single highest-value
outstanding run. It is also what a future reader would need before restoring the accuracy margin
to a load-bearing position.

**GPU contention is a live confound for both.** A same-class query on this host swung from 1.58 s
to 126.6 s under contention, so a run started while the fleet is busy measures the fleet, not the
model.
