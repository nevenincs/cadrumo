---
tags:
  - '#research'
  - '#docs-sequence-static-reasons'
date: '2026-07-25'
modified: '2026-07-25'
related: []
---

# `docs-sequence-static-reasons` research: `Double-run classification as the sequences engine default`

Can a `cli-sequence` frame be classified as convertible from a single execution?
Measurement says no, and the failure is silent. Convertibility requires a
REPRODUCIBLE run, because the artefact a conversion must produce is a committed
golden that a later run reproduces byte-for-byte; a zero exit code is a strictly
weaker property. A 190-frame classification sweep keyed on exit status produced
five wrong verdicts, four of them in the bucket that reads as retirable debt, so
a future author would have picked each one up, attempted the conversion, failed,
and abandoned it.

The engine currently offers no primitive that answers "is this frame's output
reproducible?" — `refresh` writes a golden from one run and `check` compares a
later run against a committed golden, so the pair only detects instability once a
golden has already been committed and a second run happens to follow. Nothing
tells an author, before committing, that a frame can never hold a stable golden.
The evidence favors making a two-run reproducibility probe the engine's own
classification primitive rather than a remediation step authors are expected to
remember. What the ADR must settle is where that probe lives (a `check`-adjacent
mode, a `refresh` precondition, or a distinct verb), and whether a frame that
fails it is refused at refresh time or merely reported.

## Findings

### Exit status underdetermines convertibility, and the gap is not rare

Five frames exited zero and could not be converted. Two classes appeared, and
neither is visible in a single run.

Unstable output: `aeat app ledger export --export-format xlsx` ran twice in
fresh sandboxes, both exit 0, `byte_size` identical at 5626 both times, while
`export_id` differed (`f7e74c0b…` versus `79bd7a51…`) and so did the payload
`sha256` (`5b7e8d…` versus `aca13b…`). Same length, different bytes is an
embedded per-run timestamp; the export id hashes the written bytes, so it moves
every run. `aeat config reset start --yes` and `aeat config reset status` each
emit a fresh 64-hex `operation_id` per run. `aeat config recovery status` prints
a `recovery_path` that sits BESIDE the sandbox storage root rather than under it.

Sandbox posture: `aeat app ledger participation <id>` was recorded as needing
only a real captured id. Supplying one and running it twice returned exit 4,
`INTEGRITY_STORAGE_VALIDATION`, "No active bucket session is open" — the page's
sandbox deliberately holds no unlocked session, and the same lookup succeeds on a
page whose sandbox does. Blocked-ness there is a property of the pair
(verb, page sandbox), so no per-invocation classifier can decide it.

### The comparison used by a reproducibility probe must be the golden's own

A raw byte comparison of two runs is STRICTER than the pipeline and manufactures
false instabilities. `normalise_text_output` in
`dev/docs/sequences/_golden_store.py:271` tokenises three roots — sandbox storage
root, workdir, repository checkout root — and replaces the values in
`GOLDEN_MASK_FIELDS`. A probe must compare post-normalisation output or it will
report a per-run temp path that the golden would never have held. During this
work a raw comparison was run first and its three survivors were re-tested
through the normaliser before being trusted; they survived, but the ordering was
what made them trustworthy.

### Two masking gaps the probe would surface as decisions, not defects

`GOLDEN_MASK_FIELDS` (`cadrumo.core.observability`) currently holds only
`run_id` and `snapshot_id`. A per-run `operation_id` therefore reaches the
golden unmasked.

Separately, the path normaliser is deliberately value-anchored on the exact known
roots so it can never over-mask an unrelated operator path
(`dev/docs/sequences/_golden_store.py:104`). A path emitted as a SIBLING of the
sandbox storage root is consequently passed through verbatim, carrying the
per-run temp directory into the golden. The normaliser is behaving exactly as
designed; the frame is what does not fit. Widening either surface is a masking
decision with its own owner and gates, which is why these were recorded against
the frames rather than fixed by the classification sweep that found them.

### Instruments inherit the bias they exist to detect

Three artefacts in this area encoded the same axis error they were built to
catch, and the mechanism was traceable in one case: the honesty gate over
`@static` reasons was derived from the `StaticBlocker.LIVE_AEAT` docstring, which
then named "the `pull` verb family" as part of its criterion. That converted a
one-directional naming standard (an AEAT fetch must BE named `pull`) into a
bidirectional classifier, and the gate enforced the inversion — refusing a
correction that identified `aeat app ledger pull-folder` as reading Google Drive
rather than AEAT. The prose error had travelled into enforcement, where it was no
longer legible as prose.

The generalisable heuristic: a gate written FROM a docstring rather than FROM a
measurement inherits whatever the docstring got wrong. This bears on the proposal
because a reproducibility probe is itself an instrument, and its correctness
condition should be stated as an observation about two runs rather than as a
property of a command's spelling.

### What was not investigated

Twenty-four remaining frames carry a `<placeholder>` metavariable and were NOT
re-derived; the re-derivation skipped them by construction. Each asserts that a
capture-based conversion will work, which is the same positive claim that proved
false for the participation frame, so that residue is unverified rather than
clean. Whether a reproducibility probe should also cover a proposed capture chain
(as opposed to only an already-runnable frame) is open, and is the axis on which
those twenty-four would be settled.

**Settled 2026-07-25 by a cheaper measurement than the probe.** The residue did
not need a reproducibility probe to resolve: a capture chain can only draw from a
frame that runs EARLIER IN ITS OWN SEQUENCE, so counting preceding executed
frames answers the question directly. Twenty-two of the twenty-four have NO
preceding executed frame at all, which makes the claim false as stated for all
twenty-two — there is nothing in-sequence to capture from, and conversion would
mean authoring a whole new setup chain rather than annotating a capture. Exactly
one of the twenty-four is a genuine candidate.

The twenty-four decompose as:

- **1 genuine capture candidate** — `troubleshooting/troubleshooting-auth-diagnostics`
  frame 1 needs `<diagnostic-id>` and does have a preceding executed frame.
- **16 need a new setup chain authored** — locally-derivable ids
  (`work-unit-id`, `calculation-revision-id`, `verification-report-id`,
  `filing-record-id`, `bundle-id`, `relation-id`, `run-id`) with no producing
  frame in their sequence; nine of these are the `filing-spine` address-by-id
  family.
- **4 are pure teaching metavariables** — `<profile-name>`, `<value>`,
  `<sum-from-303>`, `<ID>=<VALUE>`. These are illustrative prose, never a
  captured value, so "unconverted" mis-frames them: they are not awaiting
  conversion.
- **3 are misclassified and need an externally-owned id** — the two
  `modelo-036` records need an AEAT `<acuse>`, and `modelo-390-records-audit`
  frame 1 needs a `<justificante-or-capture-id>`. These belong under
  `live-aeat` / `operator-artifact`, not `unconverted`; correcting the code
  lowers the ratchet honestly rather than by conversion.

So the optimistic reading was wrong for 23 of 24 — the same direction as the
participation frame, and for the same reason: a positive claim about a conversion
that was never attempted. The open probe-scope question is therefore not blocking
this residue. It remains open only for already-runnable frames.

Measurement: `dev.docs.sequences.discover_sequences` over the live corpus in this
checkout, reading each frame's own `blocked.code` and counting non-`STATIC`
predecessors per sequence. Reconciliation: 185 static frames total, 87 declared
`unconverted` (equal to the per-page sum committed in
`unconverted_static_baseline.json`), of which exactly 24 carry a metavariable —
confirming the figure above from the parser rather than from this document. A
first pass counting metavariable frames across ALL blocker codes returned 47; that
is a different question (it includes 15 `external-service`, 7 `live-aeat` and 1
`sandbox-posture` frames already correctly blocked for other reasons), not a
contradiction.

The cost of a second run per frame was not measured against the docs-build
budget. The sweep's own two-run pass covered 66 frames across 34 sequences
without difficulty, but a per-refresh default multiplies every author's cycle and
that trade-off needs numbers the ADR should demand.

## Sources

- `dev/docs/sequences/_schema.py` — the `StaticBlocker` taxonomy, including
  `NONDETERMINISTIC_OUTPUT` and `SANDBOX_POSTURE`, added for the two classes
  above; `LIVE_AEAT` carries the corrected criterion.
- `dev/docs/sequences/_golden_store.py:104` — `_path_replacements`, the
  value-anchored root tokenisation.
- `dev/docs/sequences/_golden_store.py:271` — `normalise_text_output`, the
  comparison a reproducibility probe must use.
- `dev/docs/sequences/_runner.py:263` — `_live_aeat_tokens`, the fail-closed argv
  scan; refusal at `_refuse_live_frames`.
- `dev/docs/sequences/__main__.py` — `refresh_sequences` and `check_sequences`,
  the one-run write and the compare-against-committed paths.
- `dev/docs/tests/test_static_frame_reasons.py` — the three honesty gates,
  including the split that replaced the name-derived direction.
- `dev/docs/tests/unconverted_static_baseline.json` — the ratchet the wrong
  verdicts fed.
- `cadrumo.core.observability` — `GOLDEN_MASK_FIELDS`, currently `run_id` and
  `snapshot_id`.
- Commits `69c4c27805` (grammar, gates, 190 annotations), `a8c5e99e83` (taxonomy
  corrections), `b9c33b5241` (re-derivation corrections).

Measurement provenance: every figure above is from a run in this checkout on
2026-07-25 through `sequence_sandbox`, two fresh sandboxes per frame. No figure
is carried from documentation or from a report.
