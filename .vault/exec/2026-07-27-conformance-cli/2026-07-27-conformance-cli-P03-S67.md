---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S67'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# refuse a stamp write against the bundled registry tree or require the root explicitly, closing the hazard that let a test mutation write a fabricated review into the shipped modelo manifest

## Scope

- `dev/registry/conformance/cli.py`
- `dev/registry/conformance/_stamp.py`
- `dev/tests/test_registry_conformance_cli.py`

## Description

- Remove the bundled-tree default from the writer, making the registry root a
  required keyword on both `stamp_revision` and `revision_manifest_path`.
- Add one named function that resolves the shipped tree, so the bundled path is
  reachable by calling something rather than by omitting something.
- Require exactly one of the two doors on the command, and refuse a named root
  that resolves to the shipped tree.
- Add six tests over the new resolution rule, five of them mutation-proved.
- Compare parameter-error messages on a stripped rendering so a wrapped panel
  cannot decide whether an assertion holds.

## Outcome

### The ruling: require the root, AND keep one unmistakable door to the shipped tree

The row offered two answers and this Step took both, because they close
different holes and neither is expensive.

Requiring the root closes the hole the incident actually went through. The
default was the single most consequential value the parameter could hold, and a
caller reached it by forgetting rather than by choosing. It is now undefaulted at
the writer, so the exact mutation that caused the incident — dropping
`registry_root=` from one call site — raises at the call instead of writing to
shipped data. That is the durable half: it holds for every future caller,
including one written by an agent that never reads this record.

Refusing the shipped tree ALTOGETHER was considered and rejected on the tool's
own doctrine. That doctrine is about OPERATOR SIGNOFF: `operator_reviewed` is
outside the vocabulary this CLI writes, because an agent asserting a human's
signoff is the dishonesty the whole surface exists to detect. It says nothing
about authorship or agent review, which are claims an agent is entitled to make
and which the measurement audit schedules a campaign to make across ninety
revisions. A verb that could not write to the shipped registry could not do the
one job it exists for, and the campaign would route around it by hand-editing
ninety manifests — which is strictly worse, because the hand path has no schema
probe, no post-write reload, and no rollback.

So the shipped tree keeps a door and the door says what it is. `--bundled-registry`
cannot be typed by accident, and forgetting it does not silently select the tree
it names: it produces a refusal naming both doors and the bundled path. This is
the same shape the audit verb already uses for `--accept-weakening` — the
consequential act is a visible token in the command line and in shell history,
not an inference from an absent one.

A path that RESOLVES to the shipped tree is refused for the same reason. Two
doors to shipped data, one of them reading like an ordinary sandbox run, would
give back most of what the flag buys; the refusal names the flag that says what
is happening. Note this is deliberately not a blanket "refuse anything under the
package": a byte copy of a shipped modelo tree is exactly what the tests use and
must keep working.

### Defence in depth, and it is now measurable

The two halves are independent, which the mutation runs demonstrate rather than
assert. With the command's neither-flag refusal removed, the invocation no longer
writes — it fails on the writer's required argument. The old failure needed BOTH
a permissive command and a defaulting writer; either one alone now stops it.

### Verification

Five mutations, each flipping its own assertion. Three of them would, unmutated,
write to shipped data, so they were run with `bundled_registry_root` redirected
to a byte copy of the shipped Modelo 130 tree. That redirection is what makes the
probes safe AND faithful: the test's own notion of "the shipped manifest" is
derived from the same function, so it follows the redirection and the assertions
still measure the real behaviour. The five guard tests were first confirmed GREEN
under the redirection alone, so no flip below is the redirection's doing.

Restoring the writer's optional root — the incident's own mutation, made safe by
leaving the body unchanged so it raises instead of writing:

```
E   AttributeError: 'NoneType' object has no attribute 'resolve'
FAILED ...::test_the_writer_refuses_to_be_called_without_naming_a_registry_tree
1 failed in 6.22s
```

Restoring the silent bundled default on the command — this is the incident
reproduced end to end, and the failure message is the fabricated stamp itself:

```
E   AssertionError: stamped modelo=130 revision=2019-y-siguientes manifest=revision.toml
E     engineered_by="agent:opus-executor" removed=-
E   assert 0 == 2
FAILED ...::test_the_stamp_command_refuses_when_no_registry_tree_is_named
```

Guessing a tree instead of refusing the contradiction, and reopening the second
silent door — both land a completed stamp where a refusal belongs:

```
E   assert 0 == 2   FAILED ...::test_the_stamp_command_refuses_two_registry_trees_at_once
E   assert 0 == 2   FAILED ...::test_a_registry_root_that_resolves_to_the_shipped_tree_is_refused_by_name
```

Pointing the override somewhere other than the shipped tree, which is the case a
refusal test cannot catch on its own:

```
E   assert 'C:\...\s67-fake-bundled\modelos\999' in "Usage: conformance stamp ..."
FAILED ...::test_the_bundled_flag_really_reaches_the_shipped_tree_and_still_writes_nothing
```

Every mutation was reverted, the redirection removed, and the resolver confirmed
to name the real tree again before anything was committed.

Full dev CLI module under the DEFAULT selector, 74 tests before this Step:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q --no-header
80 passed in 91.72s (0:01:31)
```

The real verbs, exit codes measured without a pipe so the reported status is the
command's own:

```
python -m dev.registry.conformance audit --check                              -> exit=0
python -m dev.registry.conformance stamp 130 2019-y-siguientes --engineered-by probe
                                                                              -> exit=2
python -m dev.registry.conformance stamp 130 ... --registry-root <bundled path>
                                                                              -> exit=2
git status --short -- src/cadrumo/_data/registry/aeat/modelos/130             -> clean
```

Style, lint and types:

```
uv run --no-sync ruff format --check ...  -> 3 files already formatted
uv run --no-sync ruff check ...           -> All checks passed!
uv run --no-sync ty check dev/registry/conformance/_stamp.py cli.py -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator
direction; the service is stopped and its index is broken. It was neither
started, restarted, reindexed nor probed. Grounding was whole-file reads of the
writer, the command and the test module, plus ripgrep sweeps for every caller of
the writer and for the verb in the task runner.

The shipped registry was verified clean before the commit and after every
mutation run. The one modelo tree these tests touch, Modelo 130, carries no
working-tree modification. Peer campaigns hold uncommitted work on the M303
registry tree and on two audit baselines throughout; none of it was staged, and
the commit named its three files explicitly.

`ty check` over the test module reports diagnostics, and all but three predate
this Step. The project's type gate targets `src` only, so `dev/` is outside it;
the three new ones follow the module's established conventions exactly — two
mypy-style `call-arg` ignores matching four such lines already present, and one
attribute read on the existing stamp helper's `object` return, matching every
other use of that helper. Correcting that helper's annotation is a real
improvement and is deliberately out of this Step's scope.

One scripted edit round-tripped the writer module through Python text I/O and
silently rewrote all 925 LF terminators to CRLF. `git diff` stayed clean under
`text=auto` normalisation and the only visible signal was a warning line from
`git diff --stat`. It was normalised back to LF and confirmed byte-for-byte
before staging. This is the same defect class two prior Steps fixed inside this
package's own writers, arriving from the tooling side; every later scripted edit
in this Step read and wrote bytes.
