---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S62'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# write the conformance baseline through raw bytes as the manifest writer now does, closing the same line-ending defect in the second dev-side writer where the on-disk artefact the gate reads already differs from its committed bytes for every reader that is not git

## Scope

- `dev/registry/conformance/manager.py`
- `dev/tests/test_registry_conformance_cli.py`

## Description

- Encode the serialised baseline and write it with `write_bytes`, so the capture
  passes through no newline translation.
- Record at the change site what the previous write did, with the measurement.
- Add the capture proof: the file must not exist beforehand, must be non-empty
  afterwards, must carry no carriage return, and must equal the serialisation of
  the model the function returned.
- Add the drift gate over the real committed artefact on disk.
- Restore the on-disk baseline to its committed bytes.

## Outcome

### The defect was live in the tree, not a hypothesis

Re-measured before touching anything, and the sweep's numbers reproduced exactly:

```
HEAD blob     CRLF 0  / LF 28 / 1932 bytes
working tree  CRLF 28 / LF 28 / 1960 bytes
identical: False
git diff sees a change: False
```

The content was equal ignoring terminators, so nothing had drifted semantically —
which is the whole hazard. `git` normalises under `text=auto eol=lf`, confirmed by
`git check-attr` on the file, so the committed blob is LF on every checkout while
the working copy carried 28 CRLF terminators and every git-shaped review said
clean. The baseline is the artefact `audit --check` READS, so its on-disk bytes
and its committed bytes silently disagreed for every reader that is not git.

The fix is the one the governance writer already carries: serialise, encode, and
write the bytes.

### The drift gate is the half that would have caught it

The capture proof alone would have left the tree in its drifted state, because it
only measures files a test just wrote. The second test reads the real committed
artefact and asserts it carries no carriage return, which is exactly the read
nothing in the campaign performed. It was RED on the live tree before the
restore:

```
AssertionError: the committed baseline on disk carries translated terminators;
  a capture rewrote it after checkout and git cannot see the difference
assert b'\r' not in b'{\r\n  "ceilings": {\r\n ...
```

and green after it. That is the durable defence: a future capture through any
writer that translates re-reds it, and unlike a review diff it cannot be
normalised away.

The restore was a pure terminator normalisation. Content equality ignoring
terminators was asserted first, the written bytes were compared against the HEAD
blob afterwards, and `git diff` was empty on both sides of it — the file carries
no content change to commit and is therefore absent from the commit's pathspec.

### Verification

The capture proof is proved by reverting the production write to `write_text`
with nothing else moved. One assertion flips and the drift gate correctly does
not, because the mutated writer never touched the committed file:

```
FAILED ...::test_a_recorded_baseline_lands_as_the_bytes_it_serialised
AssertionError: the capture translated the file's terminators
assert b'\r' not in b'{\r\n  "ceilings": {\r\n ...
1 failed, 1 passed in 37.61s
```

The mutation was reverted and the module re-verified.

Full dev CLI module under the DEFAULT selector, and the real gating verb:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q --no-header
64 passed in 58.17s

uv run --no-sync python -m dev.registry.conformance audit --check  -> exit=0
```

Byte measurement after the change:

```
HEAD blob     CRLF 0  / LF 28 / 1932 bytes
working tree  CRLF 0  / LF 28 / 1932 bytes
identical: True
```

Style and lint:

```
uv run --no-sync ruff format --check ...  -> 2 files already formatted
uv run --no-sync ruff check ...           -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator
direction; the service is stopped and its index is broken. Grounding was by
whole-file reads and `rg`.

The carriage-return assertion is decisive only on a platform whose line separator
is not already LF, which is where the defect was measured. On such a platform the
byte-equality assertion carries the case alone. That scope is stated in the test
docstring rather than left for a reader to discover, and it is the same shape the
manifest writer's terminator-count assertion already has.

The test helper that seeds a moved-counter baseline still writes through
`write_text`. It writes only to temporary paths that are read back through the
normalising text reader, so nothing there can drift a committed artefact; it was
left alone rather than swept, to keep the commit to the writer under test.
