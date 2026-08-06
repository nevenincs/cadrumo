---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:c434c67a2358600a0601867c8eeb427590b14a5bc0b0c43d5ea97c61bdec723f'
step_id: 'S54'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# write and roll back the manifest through raw bytes so a refused stamp truly restores the file rather than rewriting every line ending, and assert the restoration on bytes instead of normalised text

## Scope

- `dev/registry/conformance/_stamp.py`
- `dev/tests/test_registry_conformance_cli.py`

## Description

- Read the manifest as bytes and keep the raw bytes for the restore, decoding a
  separate text view for the parser and the line editor.
- Write and roll back through `write_bytes`, so neither path passes through the
  platform's newline translation.
- Join the rebuilt manifest with the terminator the input already used, making the line
  editor's own "passed through byte for byte" claim true for CRLF input as well.
- Correct the module docstring claim that was measured false, naming the measurement.
- Re-point the rollback assertion at bytes, trigger the post-write failure from the
  written bytes themselves, and pin the mtime so the case cannot degrade back into the
  pre-write branch.
- Split the pre-write refusal out as its own named case and add a successful-write
  byte-preservation case.

## Outcome

### The restoration claim was false, and so was the successful write

`stamp_revision` read with `read_text` and restored with `write_text`. `read_text`
decodes under universal newlines; `write_text` re-encodes under the platform's. On
Windows the pair therefore expands every LF to CRLF. Measured on the pristine bundled
Modelo 130 manifest:

```
before  CRLF 0 / LF 8 / 422 bytes
rolled  CRLF 8 / LF 8 / 430 bytes
read_text says equal: True
bytes say equal:      False
```

The successful path is the worse half of it. A one-line governance stamp rewrote every
terminator in the file, so the module's line-editor rationale — touch the governance
lines, pass everything else through byte for byte, keep the diff reviewable — was not
what the code did. In a shared worktree that is invisible in review, because `git diff`
normalises line endings under `text=auto` while the working tree carries the rewrite.

The fix reads and writes bytes and reads the joiner off the input, so an LF manifest
stays LF and a CRLF one stays CRLF. The writer still collapses a manifest to exactly one
terminating newline, which the shipped manifests exercise because they end with a blank
line; that is a one-byte EOF normalisation, is deliberate and pre-existing, and is stated
in the test that measures around it.

### The rollback test never ran the rollback

This is the part worth recording. The existing proof staged a malformed sibling fragment
into the revision directory and asserted the manifest came back. But `stamp_revision`
runs its compiled-record check BEFORE it reads or writes anything, over the same tree the
post-write reload loads, so a breakage staged beforehand is caught pre-write and no byte
is ever written. A file that was never written is trivially unchanged.

Established by pinning the mtime, since both branches leave byte-identical files and only
a write moves the timestamp:

```
REFUSED: modelo 130: registry refuses to load the modelo: ...
manifest mtime moved: False
manifest bytes equal: True
-> refusal came from the PRE-write check; NO write happened
```

So the campaign carried three byte-identity assertions on the stamp writer and all three
sat on paths where nothing was written. The finding named two of them; this is the third,
and it is the one whose docstring said "proved by a reload that genuinely fails, not by a
stubbed one".

The failure now originates in the written bytes. An identity carrying an interior newline
survives the trim, which strips only the ends; the schema probe accepts it, because a
newline inside a string is nothing pydantic objects to; and the rendered TOML basic
string then carries a literal newline, which TOML forbids. The pre-write check passes,
the write lands, the reload refuses, and the restore is what keeps the broken manifest
off disk — exactly the event the two-phase design exists for, caused by the write rather
than staged around it:

```
REFUSED: modelo 130: registry refuses to load the modelo: ...revision.toml
mtime moved (a write happened): True
bytes restored exactly: True
```

The mtime assertion is now part of the durable test, not just the investigation. Without
it the case can silently slide back into the pre-write branch on any future change to the
ordering, and pass while proving nothing — which is precisely how it got here.

### Verification

The decisive mutation is the production write path reverted to `write_text`, with nothing
else moved. Both byte assertions flip and the pre-write case correctly does not:

```
FAILED ...::test_stamp_restores_the_manifest_when_the_written_tree_no_longer_loads
FAILED ...::test_a_successful_stamp_leaves_every_other_line_byte_identical
2 failed, 1 passed in 9.44s
```

with the successful-write failure reading

```
assert [b'[revisions..."]\r', ...] == [b'[revisions..."]', ...]
At index 0 diff: b'[revisions."2019-y-siguientes"]\r' != b'[revisions."2019-y-siguientes"]'
```

which is the terminator rewrite itself, named at the byte. The mutation was reverted and
the module re-verified.

Full dev CLI module under the DEFAULT selector:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q --no-header
53 passed in 52.79s
```

Style and lint:

```
uv run --no-sync ruff format --check ...  -> 2 files already formatted
uv run --no-sync ruff check ...           -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator direction; the
service is stopped and its index is broken. Grounding was by whole-file reads and `rg`.

The writer can still emit invalid TOML for an identity carrying an interior newline or
another control character, because the trim only strips the ends and the escaper handles
quotes and backslashes only. It is left open deliberately and knowingly, not by oversight.
The two-phase design already makes it safe — the loader refuses, the bytes are restored,
and the caller gets a refusal — and it is currently the only genuine post-write failure
available, so closing it at the identity boundary would leave the restore with no
exerciser again. Refusing control characters in an identity is carried in the fifth-hole
sweep recorded under Step S57, as a change that must land WITH a replacement trigger for
the rollback proof, never before one; H7 there names a candidate trigger.

Peer churn in the IVA prorrata module and the core external constants made the tree
transiently unimportable twice during this work; both probes were re-run until the import
resolved. No peer file was touched.
