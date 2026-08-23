---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:04479cca578c21dffaa430da36c802ad3355262635d510195186d0aa3a4334bd'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# `secure-storage-performance-hardening` audit: `W01.P02.S07 frozen complete-CLI baseline review`

## Scope

Independent review of `W01.P02.S07` against the accepted campaign ADR, plan,
research, reference, the S05 fresh-process profiler, and the S06 calibration
contract. The review covered the generator, committed baseline, rejected-run
diagnostic, documentation, and tests under `dev/benchmarks/cli`. It exercised
the live artifact check and adversarially rewrote source identity, raw samples,
derived distributions, controls, and rankings. It also inspected the artifact
for enrollment, failures, absolute paths, and secret-bearing output.

The artifact contains the exact current live set of 361 nodes: one root, 72
groups, and 288 leaves. Every node carries three samples, policy and ownership
metadata, and an honestly labelled `help-render` lane; 100 controls bracket and
interleave the sweep. No failed or timed-out accepted samples, absolute user
paths, raw stdout, raw stderr, or credential values were found. The existing
tests and `--check` command pass, but the findings below show that those checks
do not yet prove the evidence is current or internally accurate. Approval is
withheld while the high-severity findings remain open.

## Findings

### source-staleness | high | The frozen capture is not bound to the source being checked

`dev/benchmarks/cli/baseline.json` records source snapshot digest
`c14753ffe15c79f7c4d9636302d7b77d1d046030f618b84d9be3583b1989e4ca`,
while the current digest of `src/cadrumo` is
`fff44ea57924e487240f38e2e5b9474ad33ce586d5361bd90fff343289e110c7`.
The artifact originated at Git revision `b08acf6e115d17cdefe1b55ab43916971a7c92af`,
while the reviewed tree is at `fe97c2fa16ce5e934762666fa4a8a4b5f4fe2bca`.
`check_baseline` nevertheless passes because it checks only that each digest is
a 64-character string and compares current command metadata, not the measured
source identity. Replacing `source_snapshot_digest` with 64 zeroes also passes.
Consequently arbitrary handler, import-graph, profiler, or storage changes can
leave the performance evidence green as long as the live path metadata is
unchanged. This defeats the artifact-staleness gate required for actionable
baseline evidence.

### derived-statistics-integrity | high | Stored distributions and controls are not verified from raw samples

`check_baseline` requires at least three samples and recomputes ranking order
from the stored `control_ratio`, but it never recomputes command medians, median
absolute deviations, control distributions, ratios, or method sample counts.
In adversarial review, setting a raw resolution sample to `999999.0`, setting
its stored median independently to `999999.0`, or setting the stored control
median to `999999.0` each passed. The ranking gate therefore proves only that a
list is sorted by claims in the same artifact; it does not prove those claims
represent the retained observations. A corrupted or manually edited baseline
can silently mis-rank outliers and distort the performance campaign's input.

### evidence-compaction | high | Compaction discards the import and storage membership needed to action outliers

`_observation_payload` replaces the complete imported-module set with one
count and one digest, replaces every import-family member list with a count and
digest, and retains only the top 20 storage-call symbols. A digest can detect a
known-set change but cannot recover or inspect the set. For example, the
baseline proves that `aeat config profile list` loaded 230 storage-family
modules and invoked 223 distinct storage symbols in each sampled phase, yet it
cannot identify the imported modules and omits 203 invoked symbols. This is not
the “import-family membership” and complete “storage-call counts” promised by
`dev/benchmarks/cli/README.md`, and it prevents a reviewer or S40 worker from
attributing many observed costs without rerunning a historical, now-mismatched
source snapshot. The accepted baseline must retain actionable raw membership,
or publish a separate content-addressed raw artifact that the compact summary
can be verified against.

### rejected-run-evidence | medium | The rejected mutable-tree diagnosis is no longer independently verifiable

`dev/benchmarks/cli/rejected-mutable-tree-diagnostic.md` makes precise claims
about 48 measured nodes and four paths whose resolution and help samples all
failed, but the raw JSON was deleted and no content digest or sanitized raw
attachment remains. The narrative is plausible and explicitly excluded from
the accepted baseline, but it is now a contemporaneous assertion rather than
auditable execution evidence. Retaining sanitized failure envelopes would let
future reviewers distinguish the documented mixed-source failure from a later
reinterpretation without exposing local paths or output.

## Recommendations

For `source-staleness`, make `--check` recompute the governed source identity
and reject a mismatch, or deliberately retain and verify an immutable snapshot
artifact identified by the recorded digest. Include the profiler/generator and
dependency-lock identities that affect measurements, then recapture from the
source state S07 will claim as its baseline. Add a planted wrong-digest test.

For `derived-statistics-integrity`, validate the complete artifact schema and
recompute every distribution, MAD, control ratio, ranking, failure index, and
declared sample/control count from retained observations. Reject non-finite or
non-positive control values. Add independent bite tests for a raw sample,
derived median, control sample/distribution, ratio, method count, failure, and
timeout mutation.

For `evidence-compaction`, retain the complete sorted module-family membership
and storage-call mapping in sanitized raw evidence. If repository size requires
separation, store a compact summary plus a content-addressed raw artifact and
make the checker verify both directions. Correct the README if any deliberately
omitted field remains unavailable.

For `rejected-run-evidence`, preserve sanitized rejected envelopes or downgrade
the document explicitly to an unaudited operator note. Do not feed rejected
samples into distributions, and retain the current explicit statement that no
failed path was selectively rerun.

## Re-review

The mandatory re-review verified the remediated content-addressed evidence
pair. `baseline.raw.json.gz` authenticates against both declared SHA-256
digests, decompresses to the declared byte count, and recompresses byte-for-byte
identically at gzip timestamp zero. Its lossless observations retain every
imported module, import-family member, storage symbol, and call count; the
`aeat config profile list` specimen exposes 2,120 imported modules, 230 storage
family members, and all 223 storage symbols. The compact artifact is an exact
mechanical derivation of that raw payload.

The distribution, control, ranking, failure-index, sample-count, and compact
derivations are now recomputed. The accepted artifact contains 361 snapshot
nodes, 100 controls, and zero failed or timed-out paths. `--check` passes
internal content checks; `--check-fresh` correctly rejects current divergence,
and `current-source-delta.md` accurately names the two current additions. The
rejected mutable sweep is now explicitly classified as an unaudited operator
note rather than execution evidence. The three original high findings and the
medium finding are resolved by these changes.

### frozen-census-authority | high | Internal checking no longer proves the snapshot command set

The remediated `check_baseline` constructs the current live census only when
`require_current_source=True`. Its historical/internal lane requires merely
that `commands` be non-empty. It has no independently retained frozen-census
declaration or executable frozen source with which to compare the raw command
keys. The existing missing-path test mutates only `baseline.json`; it reds at
the generic compact-versus-raw comparison, so it does not prove an exact-set
detector. A coherently republished raw/compact pair with a removed or invented
command satisfies the internal set logic. The same omission means resume loads
`checkpoint.commands` without verifying that its keys are a subset of
`expected_paths`; a poisoned or accidentally coherent checkpoint entry can be
carried into the final evidence. `--check-fresh` cannot close this gap because
it intentionally rejects at the earlier source-manifest divergence and never
reaches current census comparison for this historical snapshot. Approval
remains withheld until the frozen 361-node enrollment and resume subset are
independently enforced.

For `frozen-census-authority`, retain a canonical frozen census declaration
with path, kind, ownership, and policy identity separately from measured
command observations, authenticate it in the raw evidence, and require exact
equality during internal checking. Validate checkpoint command keys as a subset
of `expected_paths` on resume and exact equality before publication. Replace
the current compact-only removal test with planted raw-and-summary missing and
extra-node cases so the set detector, rather than the pair-integrity detector,
is proven to bite.

## Final re-review

The `frozen-census-authority` high finding is resolved. The separate canonical
`baseline.census.json` carries the snapshot source digest and 361 path records,
each with kind, loader owner, handler owner, and complete execution policy. Its
declared byte count and SHA-256 match the file; its source digest matches the
capture manifest; its path set and every metadata record exactly match the
measured artifact. Internal checking authenticates this authority before
requiring exact command-set and metadata equality.

Resume now rejects checkpoint command keys outside `expected_paths`, and
capture requires exact equality with the frozen census before publication. The
two planted tests coherently republish both raw and compact artifacts after
removing or inventing a node; both fail specifically at the independent frozen
exact-set gate. This proves the detector rather than relying on a raw/compact
mismatch.

The final scoped verification passed Ruff, ty, all 11 baseline tests, internal
artifact checking, deterministic gzip authentication, raw/compact derivation,
and independent census set and metadata comparison. The historical artifact
remains 361 nodes, 100 controls, and zero failures; the explicit freshness lane
continues to reject the two-node current-source delta. No critical, high,
medium, or low findings remain open. `W01.P02.S07` is approved.
