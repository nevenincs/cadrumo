---
tags:
  - '#adr'
  - '#file-size-optimisation'
date: '2026-09-29'
modified: '2026-09-29'
body_schema: 'body-v2'
body_hash: 'sha256:302affe4f3c565472375bb20ae8f8009f7897fc91570c5078b82ed916c7b257c'
related:
  - "[[2026-09-29-file-size-optimisation-research]]"
  - "[[2026-07-13-docs-cli-sequences-adr]]"
  - '[[2026-06-30-deterministic-output-replay-substrate-adr]]'
  - '[[2026-06-01-docs-cli-buildtime-adr]]'
---

# `file-size-optimisation` adr: `Sequence goldens commit a fingerprint, not the output` | (**status:** `proposed`)

## Problem Statement

Decision D2 of `2026-07-13-docs-cli-sequences-adr` commits every sequence's full recorded output as its golden. It rests on two premises: goldens are "light, review-diffable data", and "the author reviews the git diff — which IS the behaviour-change review". `2026-09-29-file-size-optimisation-research` measures both premises as false on the current corpus. The goldens are generated, deterministic and cheap to regenerate, and nothing reads their history. Yet they dominate the diffs of the pull requests that change CLI output, and GitHub does not display those diffs. The review D2 relies on cannot take place. The diffs also hide the product change they accompany. The operator's test for committed artifacts is whether a file is generated, whether it is cheap to regenerate, and whether anything needs its history. A file that meets all three should not be carried in Git. A decision is needed because D2 explicitly rejected the simplest form of that remedy.

## Considerations

- Goldens are a pure function of committed inputs. A full regeneration on another machine took four minutes on one core, and it reproduced the compared form of every frame. The committed bytes also carry a centrally masked value that changes on every run, so a refresh churns files even when behaviour is unchanged (`2026-09-29-file-size-optimisation-research`, sequence goldens section).
- Every full docs build and the docs pytest gate already execute every sequence in order to compare it (`dev/docs/sequence_build_gate.py:180`, `dev/docs/sequences/checks.py:400`). Producing the output is not additional work in any lane that renders or checks.
- D2 rejected "fully regenerated goldens with no committed expectation" because the build could then not fail on drift. That concern remains valid: without a committed expectation, a regression is re-documented as the new truth.
- D3 compares the canonical, masked form of each output. Equality of that form is equivalent to equality of its digest.
- D4 already places the semantic claims in `@expect` assertions. The golden's remaining role is drift detection.
- Decision 3 of `2026-06-30-deterministic-output-replay-substrate-adr` rejects storing masked output, and D2 applies that reasoning to goldens. The same decision already commits post-mask canonical expectations for the operator golden gate. It gives three reasons, and each is answered here:
  - The mask could not be tightened later. With regeneration deterministic and four minutes long, tightening the mask costs one refresh.
  - A masked field that became deterministic could never be detected. The executor-level mask-honesty gate detects that by executing twice. It does not read committed bodies (`dev/docs/tests/test_sequence_goldens.py`, claim 1).
  - The stored record would be a less faithful record of behaviour. The faithful record is the transcript each build regenerates and renders.
- `2026-06-01-docs-cli-buildtime-adr` keeps the generated CLI reference out of Git on the same grounds.
- The repository already gitignores generated inputs that are regenerated locally: the published authority (`pyproject.toml:421`) and the `cli-tree.json` help projection (`.gitignore:93`).
- The output weight amendment (A1 to A4) reduces what readers are shown. It is independent of this storage question and stays.

## Considered options

- **Keep full outputs and shrink them through A3 and narrower CLI surfaces.** Rejected as the storage answer. It reduces bytes, but every output change still rewrites committed text that nobody reviews, and it depends on authoring discipline. A3 and A4 remain for the reader's sake.
- **Commit nothing. Regenerate at build time and gate on execution, `@expect` and the crash scan.** This meets the operator's test most literally. It drops the drift detection D2 was chosen to keep. Command frames without a payload `@expect` would no longer be asserted at all. Kept as the alternative if the operator prefers no committed expectation.
- **Commit a per-frame fingerprint (argv, exit code, captures and a digest of the compared form) and regenerate outputs at build time.** Proposed.
- **Move full goldens out of Git (LFS or an artifact store).** Rejected. It adds infrastructure and a network dependency to every docs build, and the files stay unreviewable.
- **Mark goldens `linguist-generated` only.** Rejected as a remedy. It changes presentation, not size or churn.

## Constraints

- The digest covers exactly the form D3 compares: the canonicalised, centrally masked envelope for JSON frames and the normalised stdout and stderr text for text frames. The gate is therefore neither weaker nor stronger than it is today.
- D2 stored pre-mask output so that the mask set could change without rewriting goldens. A digest has to be taken after masking, so a change to `GOLDEN_MASK_FIELDS` (`src/cadrumo/tests/golden_comparison.py:70`) or to the canonical form requires a refresh. That refresh rewrites one line per frame.
- The substrate's capture primitive is unchanged. The live side still captures the raw envelope and masks at compare time. Only what the docs commit changes.
- The mask-honesty gate keeps executing twice and comparing unmasked output. It remains the detector for a masked field that becomes deterministic.
- The refresh CLI stays the only writer of goldens.
- A page renders only output from an execution whose digests matched. The build never renders unverified output.
- Rendered transcripts live in a gitignored cache and are never committed. A verdict-cache hit must also hold the transcripts it vouches for, otherwise rendering re-executes.
- No gate may use Git state as its oracle (`aeat-quality-gates`).
- Existing Git history is not rewritten.

## Implementation

The golden schema version advances, and a golden in the earlier format is refused with the refresh invocation. Each frame keeps its kind, argv, exit code, captures and envelope source, and gains the digest and byte size of its compared form. Output, text and stderr bodies are no longer stored.

Refresh executes each sequence and writes the fingerprint golden. It also writes the full transcript into the rendered-output cache. Check executes, recomputes digests and compares. On a mismatch it names the page, sequence, frame and argv. It shows differing paths when a locally cached earlier transcript exists, and otherwise points to the live output it wrote to the cache.

The docs build renders every cli-sequence directive from the transcripts produced by the check in the same build, or from the verdict cache entry that recorded them. The deploy root that runs the check populates the cache the other roots render from. The crash-marker gate scans transcripts instead of committed bodies. The enrolment floor and the mask-honesty gate are unchanged, since both already execute sequences.

One refresh rewrites all 205 goldens to the new form in the same change.

## Rationale

The fingerprint keeps the one property D2 was chosen for: the build fails on any output drift, at D3's strictness. It removes every byte that fails the operator's test. The committed form shrinks from 12 MB and 314,000 lines to about 0.43 MB and 20,000 lines. An output change becomes a one-line digest change per frame, which a reviewer can see and question. Committing nothing would save the last 0.4 MB but give up drift detection. That trade was rejected in D2 and nothing measured since changes it. The evidence is in `2026-09-29-file-size-optimisation-research`.

## Consequences

- Pull requests that change CLI output show the product change, plus one digest line per affected frame, instead of hundreds of thousands of JSON lines.
- The committed diff no longer shows what an output became. That review was not happening, because the diffs exceeded GitHub's rendering limits. A reviewer who needs it runs the check or refresh locally. A CI summary that renders only changed frames is a possible follow-up.
- A docs build that skips the check must obtain transcripts from the cache or execute the sequences. It can no longer render from the repository alone.
- A change to the mask set now requires a refresh.
- This amends D2 and the diagnostics part of D3 in `2026-07-13-docs-cli-sequences-adr`. For docs goldens only, it narrows how D2 applies decision 3 of `2026-06-30-deterministic-output-replay-substrate-adr`. D1, D4 to D7 and the output weight amendment are unaffected. The earlier golden bodies remain in Git history.
