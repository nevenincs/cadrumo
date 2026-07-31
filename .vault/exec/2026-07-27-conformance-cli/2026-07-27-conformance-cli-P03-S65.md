---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:ec9914eaa20592d91b7a1fe7de5267a4a1abef6fb77ffdd6012563a1a3724497'
step_id: 'S65'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# give the stamp CLI command an injectable registry root so its own date defaulting and error translation can be exercised without writing to the shipped registry, and correct the coverage pragma that calls a reachable branch unreachable

## Scope

- `dev/registry/conformance/cli.py`
- `dev/registry/conformance/_stamp.py`
- `dev/tests/test_registry_conformance_cli.py`

## Description

- Add the registry-root option to the stamp command and pass it to the writer.
- Record on the command why the option exists and what had no coverage without it.
- Delete the false coverage pragma, replacing it with the measurement that refutes
  it, and make the refusal name the spelling requirement.
- Add three command-layer tests: the date defaulting, the refusal translation, and
  the S53 re-attribution refusal confirmed through the real app.
- Add the header-spelling case for both valid alternatives, asserting the tree
  still loads.

## Outcome

### An untestable command layer is an untested one

The writer accepted `registry_root` from the beginning and the Typer command
never passed it, so the only tree the verb could reach was the shipped registry.
Everything the command layer itself owns was therefore unreachable by any test:
the today-defaulting of `reviewed_at`, and the translation of a `StampError` into
a parameter error. Both live in the command, not the writer, so no amount of
writer-boundary coverage touches them — and the S53 record's own note is the
consequence, a finding reported as reproduced end to end that could not be
re-confirmed that way.

All three are now proved against a byte copy of the shipped Modelo 130 tree,
including the S53 refusal on the surface an operator actually drives, asserted on
bytes because a refusal raised after the rewrite would leave the re-attributed
signoff on disk and still exit non-zero.

### The pragma was false and the branch is reachable end to end

`_apply_governance` carried `# pragma: no cover - _declared_governance proves the
table exists` on its header lookup. That function proves the table exists in
PARSED TOML; the lookup compares against one exact spelling of the header LINE.
Measured against byte copies, before anything was changed:

```
"[revisions.'2019-y-siguientes']"    tomllib key ['2019-y-siguientes'] | exact-line match: False
'[ revisions."2019-y-siguientes" ]'  tomllib key ['2019-y-siguientes'] | exact-line match: False
  loader accepts the tree: True   (both)
  stamp: REFUSED revision manifest has no [revisions."2019-y-siguientes"] header line
```

The load assertion is the load-bearing half: both manifests COMPILE, so this is a
real authoring state rather than a broken file the pre-write check would catch
first. It fails safe, so the cost was never a bad write — it was a comment telling
the next reader a branch cannot happen when it can, and a caller left with a
manifest the registry accepts and the writer says it has no header for.

The narrow match is kept: the line editor needs a literal line to edit, and
widening it to re-implement TOML header parsing would trade a clear refusal for a
subtler class of mistake. What changed is that the pragma is gone, the branch is
covered by a parametrised case over both spellings, and the message now names the
requirement and the fix.

### Verification

Three mutations, one per behaviour the command layer owns, each flipping its own
assertion and leaving the others alone.

Removing the today-defaulting — sharp because the schema requires a date beside a
reviewed status, so the same invocation is refused rather than served:

```
assert result.exit_code == 0, result.stdout
E   assert 2 == 0
FAILED ...::test_the_stamp_command_defaults_the_review_date_to_today
1 failed, 4 passed
```

Removing the `StampError` to `BadParameter` translation — both the exit code and
the visible reason move:

```
E   assert 1 == 2
E   assert "already declares review_status 'operator_reviewed'" in ''
FAILED ...::test_the_stamp_command_turns_a_writer_refusal_into_a_parameter_error
FAILED ...::test_the_stamp_command_refuses_to_re_attribute_an_operator_signoff
2 failed, 3 passed
```

Dropping the registry-root pass-through, which is the change itself:

```
E   AssertionError: assert <RevisionReviewStatus.PENDING_REVIEW> is <RevisionReviewStatus.AGENT_REVIEWED>
FAILED ...::test_the_stamp_command_defaults_the_review_date_to_today
```

Every mutation was reverted and the module re-verified.

Full dev CLI module under the DEFAULT selector, and the real verbs:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q --no-header
74 passed in 56.62s

uv run --no-sync python -m dev.registry.conformance audit --check  -> exit=0
uv run --no-sync python -m dev.registry.conformance report         -> 90 row lines
```

Style, lint and types:

```
uv run --no-sync ruff format --check ...  -> 3 files already formatted
uv run --no-sync ruff check ...           -> All checks passed!
uv run --no-sync ty check ...             -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator
direction; the service is stopped and its index is broken. Grounding was by
whole-file reads and `rg`.

INCIDENT, and it is the reason this Step existed. The third mutation — dropping
the registry-root pass-through — made the test suite's own stamp invocation fall
back to the DEFAULT root, and it wrote a fabricated agent review into the SHIPPED
Modelo 130 manifest:

```
+review_status = "agent_reviewed"
+reviewed_by = "agent:opus-executor"
+reviewed_at = 2026-07-28
```

It was caught immediately by `git status`, the added lines were verified to be
exactly those three and nothing else before touching the file, and the manifest
was restored byte-identically to its HEAD blob. The shipped registry is clean.

The lesson is the Step's own thesis turned on its author: a verb whose target
tree is implicit will eventually be pointed at the wrong one, and the only reason
this was recoverable is that the write is a three-line append to a file under
version control. A `--registry-root` that DEFAULTS to the shipped tree keeps that
hazard alive for anyone who forgets the flag. Requiring the root explicitly, or
refusing a write to the bundled tree outright, is the durable answer and is
carried forward in the sweep below rather than taken here, since it is a
behaviour change the Step did not authorise.

The two command-layer assertions read `result.output` rather than `result.stdout`,
because click routes a parameter error to stderr and the two streams are separate
on this click version; a `stdout` assertion passes vacuously against an empty
string on the success path and fails confusingly on the refusal path.
