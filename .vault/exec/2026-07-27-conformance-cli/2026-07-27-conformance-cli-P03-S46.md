---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S46'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# render the reviewer attribution with its review tier attached so an agent-tier review naming a person cannot be read as an operator signoff when scanning rows

## Scope

- `dev/registry/conformance/manager.py`

## Description

- Add the pure `reviewer_attribution` join to the manager facade, returning the reviewer
  qualified by the tier that claimed them and `None` when no review is declared.
- Carry the joined form on the rendered payload as `reviewed_by_attribution` alongside the
  raw `reviewed_by`.
- Render the tier-qualified form in the text row's reviewer column.
- Record the join as a fifth reading rule on the module, naming what it does and does not
  close.
- Add three tests: the tier-change flip on a real composed row, the JSON payload carrying
  both forms, and the absence-stays-absence case.

## Outcome

### The status column was honest; the attribution column was not

Beyond its non-blank validator, `reviewed_by` is unconstrained free text, so
`--review-status agent_reviewed --reviewed-by "Gergely Wootsch"` writes cleanly. It is a
legitimate stamp and the tool is right to accept it: an agent CAN review a revision, and
naming who did is better than naming nobody. The dishonesty was in the reading. Rendered
bare, the reviewer column of an agent-tier review and of a genuine operator signoff were
byte-identical, and a reader scanning ninety rows takes in one reviewer column.

Demonstrated before the change, with the same name stamped at both tiers:

```
modelo=036 revision=2025-02-03-y-siguientes review_status=agent_reviewed reviewed_by="Gergely Wootsch"
modelo=038 revision=2002-y-siguientes review_status=operator_reviewed reviewed_by="Gergely Wootsch"

as a scanning reader sees the reviewer column alone:
  reviewed_by="Gergely Wootsch"
  reviewed_by="Gergely Wootsch"
```

### What is closable here, and what is not

This is not fully closable and the record should not pretend otherwise. Reviewer identity
is free text by necessity — the governing decision says so, and no vocabulary can enumerate
who may review a revision. Nothing in this package can make an attribution TRUE, and a gate
that claimed to would be a worse lie than the one it replaced.

What is closable is the PRESENTATION. The text row now renders the reviewer as
`<status>:<name>`, so the two columns cannot be read independently; the payload keeps the
raw `reviewed_by` and carries the joined form as `reviewed_by_attribution`, so a JSON
consumer filtering on the reviewer alone reaches the same qualified answer rather than the
bare name.

The join is applied to EVERY tier, not only to `agent_reviewed`. Qualifying one tier and
leaving the other bare would make a bare name mean `operator_reviewed` by convention, which
is a rule a reader must already know before the column is safe — and the reader who does
not know it is exactly the one the join exists to protect. A revision claiming no review is
never joined to a tier: the registry schema pairs the reviewer identity with a status beyond
`pending_review` and refuses either alone, so no reviewer means no claim, and the column
renders `n/a` rather than a manufactured one.

### Verification

The decisive proof changes ONLY the tier on a real composed row and asserts the rendered
reviewer column changes with it. The stamp is moved on the shipped composer's own output and
the report is built by the real projection, so the join under test is computed by production
code rather than assembled by the probe:

```
modelo=036 revision=2025-02-03-y-siguientes review_status=agent_reviewed reviewed_by="agent_reviewed:Gergely
  reviewer column as scanned: reviewed_by="agent_reviewed:Gergely Wootsch"
modelo=036 revision=2025-02-03-y-siguientes review_status=operator_reviewed reviewed_by="operator_reviewed:Gergely
  reviewer column as scanned: reviewed_by="operator_reviewed:Gergely Wootsch"
```

Same row, same name, different tier, different rendering. Before the change these two lines
were identical in the reviewer column.

The real verbs after the payload gained a field:

```
uv run --no-sync python -m dev.registry.conformance report --json   -> exit=0
uv run --no-sync python -m dev.registry.conformance report          -> 90 row lines
uv run --no-sync python -m dev.registry.conformance audit --check   -> exit=0
```

Full dev CLI module under the DEFAULT selector:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q --no-header
44 passed in 34.77s
```

Style and lint:

```
uv run --no-sync ruff format ...  -> unchanged
uv run --no-sync ruff check ...   -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator direction; the
service is stopped and its index is broken. Grounding was by whole-file reads and `rg`.

A module-scoped fixture holding the shipped composer's profile was added so a governance
stamp could be moved on a REAL row. The first fold costs about nine seconds and the warm one
under two, because the registry loader caches beneath it; the module's wall time did not
regress.

`StampResult.render()` in the stamp writer also echoes a reviewer name beside its status on
one line. It was left alone: that surface confirms a single write the caller just made with
both fields adjacent, rather than being a ninety-row scanning surface, and this step's scope
is the manager. Worth revisiting if stamp output ever becomes something read in bulk.
