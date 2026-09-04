---
tags:
  - '#audit'
  - '#cli-distribution-consolidation'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:434247b3de5ba40b84fd028385702edf36f513e2ab30190a64425e12402c0299'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# `cli-distribution-consolidation` audit: `cohort build cost`

## Scope

The immutable release cohort build, measured rather than reasoned about. The
campaign's own evidence lanes wait on this build, and a matrix leg had been
observed exceeding ten minutes, so the question was whether the cost is
proportional to the work or whether the build repeats itself.

Measured by running the real, unmodified `build_python_cohort` against a clean
detached checkout of `9df21163`, instrumented only by wrapping the module's own
bound names to record `time.perf_counter` deltas. No tracked file was modified.
Conditions differ from CI and the difference matters: Windows/NTFS, warm `uv`
cache, warm page cache, fast link. Total wall time **336.9 s**. The wider
`build_release_cohort` wrapper was not run end to end; claims about it below
come from reading it, and are marked as such.

## Findings

### cohort-build-cost | high | A quarter of the build is work it has already done

Of 336.9 s measured, roughly 85 s is recomputation with no captured benefit.
The tree is serialised twice before the first real compressor runs: `git
archive` reads and compresses the whole tracked tree (28.1 s), then
`extractall` writes those same bytes back out as about 39,090 individual files
(47.7 s) purely to give the build a working directory. The extracted tree is
then deleted, and moments later `uv pip install --target --no-deps` rebuilds an
equivalent importable tree by unpacking the 24,849-member wheel that was just
written (27.9 s), only so the command-spec probe has something to import. The
artifact projection is walked twice in the same process (3.9 s + 3.3 s) with no
cache between the call sites, and each of the eight artifacts is digested two to
four times per build.

### cohort-build-cost | high | The build validates itself a second time before returning

`build_python_cohort` ends by calling `load_python_cohort` on the output it has
just written (9.9 s): a full closed-world scan, all eight digests recomputed,
the attestation revalidated, the projection re-walked, and the wheel and sdist
metadata re-parsed — immediately after the code that produced and trusted that
same manifest. Read separately, `build_release_cohort` adds a third pass,
copying the built artifacts and calling `load_python_cohort` again on the copy.

### cohort-build-cost | medium | The runtime wheelhouse refetches unchanged bytes serially

`build_runtime_wheelhouse` downloads through a single-threaded `urlopen` loop
over up to twelve platform and runtime combinations (37.4 s), checking no cache
first. The bytes are lock-pinned, so a build minutes after another with an
unchanged lock refetches every wheel from the index.

### cohort-build-cost | medium | Part of the cost is genuinely proportional and must stay

`git archive` and the three `uv build` invocations (107.1 s combined) are real
work: six distributions over 87 MB of registry and 654 MB of split corpus. The
registry fingerprint pass (26.5 s over 19,831 files averaging 4.4 KB) is a
legitimate once-per-build content digest whose cost here is dominated by
per-file syscall overhead on NTFS; it should not be extrapolated to a Linux
runner.

### cohort-build-cost | low | The ten-minute observation was not reproduced directly

The instrumented run measured 5 m 37 s under favourable local conditions. The
gap to the reported figure is attributed, by code reading rather than
measurement, to the outer clone, the copy-and-revalidate pass, and per-file
scanning overhead on the roughly 84,000 file touches a build performs. Whether
real-time antivirus scanning is active on the measuring host was not checked.

## Recommendations

Ordered by measured saving against risk. None of these change what the build
produces; each removes a repetition, so each must be proved by a byte-identical
cohort digest before and after.

Return the cohort from data already in hand rather than re-deriving it through
`load_python_cohort`, which removes that pass and one of the two projection
walks. Run the command-spec probe against the extracted tree that already exists
rather than deleting it and reinstalling the wheel to recreate it. Cache the
artifact projection on its inputs so the second caller reuses it. Thread the
digest computed for the manifest through to the install target and the
attestation instead of recomputing it. Give the wheelhouse download a cache
check and a small thread pool.

The digest-parity requirement is the load-bearing constraint here: this build
mints the acquisition evidence a release promotes, so a change that alters the
output digest is a defect regardless of how much time it saves.
