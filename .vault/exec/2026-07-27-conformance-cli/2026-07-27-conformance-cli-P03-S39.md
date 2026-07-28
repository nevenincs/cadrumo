---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S39'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# coerce the review status at the stamp writer function boundary so handing it the core enum member raises instead of writing an operator signoff, and prove the refusal leaves the manifest byte-identical

## Scope

- `dev/registry/conformance/_stamp.py`

## Description

- Coerce the requested review status through `StampableReviewStatus` as the first
  statement of `stamp_revision`, before the merge that reads `.value` off it.
- Raise a `StampError` naming the accepted vocabulary, why `operator_reviewed` is absent,
  and the path a real operator signoff takes.
- Narrow the module docstring's headline claim to what the coercion enforces, and record
  on `StampableReviewStatus` that it is now the coercion as well as the parse-boundary
  vocabulary.
- Add three tests: the core `OPERATOR_REVIEWED` member refused with a byte-identical
  manifest, the paired core `AGENT_REVIEWED` member served, and four out-of-vocabulary
  string spellings refused without touching the manifest.

## Outcome

### The guarantee was false at the public entry point

The module's own headline section is "Why an agent may not stamp `operator_reviewed`",
and it calls itself "deliberately the narrowest and most suspicious code in the package".
That claim was enforced by a TYPE HINT and nothing else. `stamp_revision` is in `__all__`;
the core `RevisionReviewStatus` is one import away in `cadrumo.core` and is the enum a
caller reaches for first because that is where the closed value set lives; every line
downstream read `.value` off whatever object arrived. Nothing coerced at the boundary.

Reproduced before the fix, against a byte copy of the shipped modelo 130 tree:

```
ACCEPTED: stamped modelo=130 revision=2019-y-siguientes manifest=revision.toml
  review_status="operator_reviewed" reviewed_by="agent:opus-executor"
  reviewed_at=2026-07-28 removed=-
manifest byte-identical: False
compiled review_status: <RevisionReviewStatus.OPERATOR_REVIEWED: 'operator_reviewed'>
compiled reviewed_by: 'agent:opus-executor'
--- manifest governance lines ---
review_status = "operator_reviewed"
reviewed_by = "agent:opus-executor"
reviewed_at = 2026-07-28
```

A manifest on disk claiming a completed operator signoff, naming an agent as the
signatory. Neither existing guard could see it. The pre-write schema probe passed because
the registry schema legitimately accepts `operator_reviewed` — the governing decision
deliberately keeps direct authoring legal, which is exactly why the refusal cannot live in
the schema. The post-write reload passed because it proves only that the tree still
compiles, which it did. The one place the refusal exists is this CLI, so the one place it
can be enforced is this CLI's function boundary.

The failure this leaves open is not hypothetical friction. A stamping-campaign agent told
the CLI cannot record operator signoff writes a three-line driver rather than ninety
manifest edits, passes the core member because it is the one in `cadrumo.core`, and ninety
revisions leave the backlog stamped `operator_reviewed`. Nothing reds. The backlog the
whole feature exists to expose reads as fully countersigned, and a false stamp is
indistinguishable in every rendered row from a true one.

### Coercion, not an identity check

The refusal keys on the VALUE a manifest would carry, never on which enum class the caller
imported. `StampableReviewStatus(value)` serves the core `AGENT_REVIEWED` member, the bare
string `"agent_reviewed"`, and its own member alike, and raises for `operator_reviewed` in
any spelling. An `isinstance(value, StampableReviewStatus)` guard would have refused a
perfectly honest caller for importing the other enum and taught them to reach past this
function rather than through it — while satisfying the refusal test just as well. That is
why the paired test exists: a coercion rejecting every core member would pass the refusal
proof and break every real caller, and no other assertion in the file would notice.

Two argument shapes were checked for the same annotation-only gap and are already closed.
A `datetime` handed to `reviewed_at` (annotated `date`, and `datetime` is a subclass) is
refused by the pre-write schema probe with a strict pydantic `date_type` error and leaves
the manifest byte-identical, because the probe validates against the real revision model.
A non-string `engineered_by` raises before anything is written. Neither can put a false
claim on disk, so neither was widened in scope. The bare-string `review_status` case
previously raised an uninstructive `AttributeError: 'str' object has no attribute 'value'`
from inside the merge; it now reaches the same instructive refusal.

### Verification

The decisive proof is a mutation of the production code, not of a fixture: the identical
probe script against an identical byte copy of the shipped modelo 130 tree, run once
before the change and once after. Only the module moved, and the result flipped.

After:

```
REFUSED StampError: refusing to write review_status
<RevisionReviewStatus.OPERATOR_REVIEWED: 'operator_reviewed'>: this CLI writes only
'pending_review', 'agent_reviewed'. 'operator_reviewed' is absent by decision, not by
omission: this CLI is agent-driven, and an agent recording a human's signoff is the
dishonesty the conformance surface exists to detect. Passing the core
RevisionReviewStatus member does not make the claim true. The operator signs off by
editing the revision's revision.toml directly, which the registry schema accepts.
manifest byte-identical: True
```

The byte-identical line is the load-bearing half and is asserted in the durable test too:
a refusal that raised AFTER rewriting the manifest would leave the false claim on disk and
still satisfy a bare `pytest.raises`.

CORRECTION, recorded by the S53 to S57 pass. Both byte-identity assertions added here sit
on the PRE-WRITE refusal path, where nothing is written, so they are trivially true and
prove only that the refusal precedes the write — which is worth pinning, but is not what
the module's separate claim that a failed write is "restored to its previous bytes" is
about. That claim was FALSE at the time: the writer read with `read_text` and restored with
`write_text`, which on Windows expanded every LF to CRLF, taking the bundled Modelo 130
manifest from 422 bytes and eight LF terminators to 430 bytes and eight CRLF ones. The only
test exercising the restore compared `read_text`, which normalises the difference away —
and it turned out not to reach the restore at all, because it staged its failure before the
pre-write check. Step S54 moves the writer onto raw bytes, re-points the assertion onto
bytes, and triggers the post-write failure from the written bytes themselves.

Full dev CLI module under the DEFAULT selector, before and after:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q --no-header
37 passed in 50.98s
```

Focused stamp surface:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -k "stamp or vocabulary" -q --no-header
17 passed in 8.91s
```

Style and lint on both changed files:

```
uv run --no-sync ruff format --check ...  -> 2 files already formatted
uv run --no-sync ruff check ...           -> All checks passed!
```

The verb was deliberately NOT run against the shipped registry, following the S16
precedent: writing a review claim nobody made is the exact dishonesty this work prevents.

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator direction; the
service is stopped and its index is broken. Grounding was by whole-file reads and `rg`.

`ty` reports an `invalid-argument-type` diagnostic on each test line that hands a
deliberately wrong-typed value past the annotation. That is the point of those tests, the
lines carry the same `# type: ignore[arg-type]` comment as the pre-existing identity
test at line 658 which draws the identical diagnostic, and the project type gate
(`dev.quality.types`) scopes `ty` to `src` and `pyright` to the domain and application
packages, so `dev/` is out of its scope. No new diagnostic class was introduced.

A peer landing Step S40 was mid-sweep in the registry facade during this work: the
filing-year grounding resolver had been renamed at its definition while the package
`__init__` still imported the old name, which made the whole registry package transiently
unimportable and briefly failed a probe here. It resolved on its own within a minute. No
peer file was touched.
