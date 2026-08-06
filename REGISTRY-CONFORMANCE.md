# Registry conformance

This runbook covers the registry conformance tool for Cadrumo contributors:
what it measures, how to read each of its four commands, how to record a
revision's governance provenance, and how to move its committed baseline. AEAT
is the Spanish tax authority that owns the official modelo structure.

The tool is contributor tooling under `dev/`. It ships with the repository, not
with the application, which is why this runbook sits beside
[CONTRIBUTING.md](CONTRIBUTING.md) rather than in the user documentation.

Run every command from the repository root:

```bash
uv run --no-sync python -m dev.registry.conformance --help
```

## Read what the tool measures, and what it does not

The tool reports **coverage of checking**. It does not report correctness.

A high number means many casillas are checked against something independent of
the calculation engine. A low number means most figures are reconciled only
against the engine that produced them — the engine agreeing with itself. In
neither case does the tool state that a figure is right or wrong.

The `coverage` command carries that distinction in its own output, so a
programmatic reader cannot take the number without it:

```
axis axis=external_grounding.independently_checked_casillas scope=casilla
  measured=59 population=1261 fraction=0.0468
  caveat="coverage of independent checking, never correctness: a low value means
  most reconciliation here is the engine agreeing with itself, not that any
  number is wrong"
```

Read the population beside every measurement. `0 of 43` is a dead schema
surface. `0 of 0` says only that nothing could have declared the axis either
way. The two look identical if you read the count alone.

## Choose a command

The tool has four commands. Three of them read; one writes.

| Command | Purpose | Exit code |
| --- | --- | --- |
| `report` | One row per modelo revision, every axis. | Always 0. |
| `coverage` | Each axis's measured count against its real population. | Always 0. |
| `audit` | Current counters against the committed baseline. | 0, or 1 with `--check`. |
| `stamp` | Write one revision's declared governance provenance. | 0, or non-zero on refusal. |

`report` and `coverage` are screens. They print findings and exit 0 whatever
they find, so they never block a lane.

`audit` is a screen by default and a gate with `--check`. Use the bare form to
read the current state; use `--check` when you want a non-zero exit on a
regression.

Both read commands accept `--json` for the strict payload instead of the
greppable `key=value` rows, and `--no-validate` for a degraded read that
survives a registry another contributor is mid-edit. A degraded run stamps
every row `registry_validated=false`, and the axes that need the validating
authority report `n/a` rather than zero — so a degraded read is never mistaken
for a clean one.

### Print the current state

```bash
uv run --no-sync python -m dev.registry.conformance report
```

Every line carries its kind as its first token, so you can select one kind with
a plain `grep`. A run over 90 revisions emits one `summary`, three `census`
lines, 90 `row` lines, a `unused_axis` line per schema axis nothing declares,
and a closing `note`:

```
summary registry_validated=true revisions=90 modelos=73 engineered_by_declared=0
  independent_check_coverage=0.0468 reconciled_casillas=1261
  independently_checked_casillas=59 ...
census review_status=agent_reviewed revisions=0
census review_status=operator_reviewed revisions=0
census review_status=pending_review revisions=90
row modelo=036 revision=2025-02-03-y-siguientes registry_validated=true
  review_status=pending_review engineered_by=n/a reviewed_by_attribution=n/a
  reviewed_at=n/a calc_grade=true casillas=31 formulas=0 bindings=1 ...
unused_axis axis=revision.support_removal_decisions population=90
note n/a means NOT MEASURED or NO CLAIM MADE, never zero, while '-' is a real
  empty list; ...
```

Read the closing `note` before you read any number. `n/a` means not measured or
no claim made — never zero — and `-` means a real empty list. A reader who
takes `n/a` for zero draws the opposite conclusion from the one the row states.

### Compare against the baseline

```bash
uv run --no-sync python -m dev.registry.conformance audit
uv run --no-sync python -m dev.registry.conformance audit --check
```

`audit` checks three directions and reports them separately, because they fail
for different reasons and want different responses:

- A **ceiling** violation means a defect count grew — a grounding finding, a
  classification incoherence, an unattributed oracle payload.
- A **vacuity floor** violation means a measurement population fell. Fewer
  revisions, casillas, oracle payloads, or locale leaves were reached than the
  baseline proves the run must reach. Every clean counter beside it is then
  vacuous, which is why this direction is reported first.
- A **progress floor** violation means declared provenance or translation was
  lost — a signoff erased, an authorship claim dropped, a translated leaf
  deleted.

Population growth is not gated. A new revision moves the population and leaves
the progress counters alone, so adding one does not force you past a refusal.

Run `just audit-registry-conformance` to print `report` and `audit` together.

## Stamp a revision's governance provenance

Governance provenance is the one conformance axis nothing can derive. Who
engineered a revision, and how far its review has progressed, are facts about
people and agents. The tree cannot compute them, so they are declared.

`stamp` writes four scalars — `engineered_by`, `review_status`, `reviewed_by`,
`reviewed_at` — and writes them only into the revision's own `revision.toml`
manifest. It never writes them into a per-section fragment: a stamp declared in
a fragment merges silently and wins, so a revision can read unstamped while the
compiled snapshot claims a completed review.

### Name the target tree

Every `stamp` run must name the tree it writes to. Pass exactly one of
`--registry-root` or `--bundled-registry`. There is no default.

Stamp your own copy of a tree:

```bash
uv run --no-sync python -m dev.registry.conformance stamp 130 2019-y-siguientes \
    --engineered-by "agent:example" \
    --review-status agent_reviewed \
    --reviewed-by "agent:example" \
    --registry-root /path/to/registry/aeat
```

```
stamped modelo=130 revision=2019-y-siguientes manifest=revision.toml
  engineered_by="agent:example" review_status="agent_reviewed"
  reviewed_by="agent:example" reviewed_at=2026-07-28 removed=-
```

Stamp the registry that ships in the wheel:

```bash
uv run --no-sync python -m dev.registry.conformance stamp 130 2019-y-siguientes \
    --engineered-by "agent:example" --bundled-registry
```

Omit both flags and the command refuses with exit code 2. Point
`--registry-root` at the shipped tree and it also refuses: writing to shipped
data is legal, but it must be stated with `--bundled-registry` so the act is
visible in the command line rather than hidden in a path that happens to
resolve there.

`--reviewed-at` defaults to today. Pass it as `YYYY-MM-DD` to set another date.
Use `--clear-engineered-by` to drop an authorship claim, so a wrong name is
correctable.

The stamp is validated against the real revision schema before anything is
written, and the whole modelo is reloaded through the real loader afterwards. A
manifest the loader would reject is restored to its previous bytes rather than
left on disk.

### Understand the review vocabulary

`--review-status` accepts two values:

- `pending_review` — no review has happened. This is what a revision reads as
  when it declares nothing.
- `agent_reviewed` — an agent has reviewed it. Name the reviewer with
  `--reviewed-by`.

A third value, `operator_reviewed`, exists in the schema and the CLI will not
write it:

```
Invalid value for '--review-status': 'operator_reviewed' is not one of
'pending_review', 'agent_reviewed'.
```

This is deliberate, not an omission. The CLI is driven by agents, and an agent
writing "the operator reviewed this" is exactly the dishonesty the conformance
surface exists to detect. No flag repairs it: a switch asserting operator
identity is as assertable by an agent as the value itself, so it would add the
appearance of assurance and none of the substance.

Record an operator signoff by editing `revision.toml` directly:

```toml
review_status = "operator_reviewed"
reviewed_by = "your name"
reviewed_at = 2026-07-28
```

The schema accepts the value, so the hand-edit is the sanctioned path. Operator
signoff stays a human act on the file.

The refusal applies to the status a write would resolve to, not only the status
you asked for. Passing `--reviewed-by` alone against a revision that already
declares `operator_reviewed` is refused, because re-attributing an existing
signoff destroys a name and date nothing in the tree can reconstruct.

## Re-record the baseline

The committed baseline is what `audit --check` compares against. Move it when
the tree has genuinely changed — after landing grounding work, after adding
revisions, after a translation pass.

```bash
uv run --no-sync python -m dev.registry.conformance audit --record \
    --note "grounded the M303 prorrata casillas; full tree, all suites green"
```

`--note` is required. Without it the command refuses:

```
--record requires --note stating why the baseline moved and under what tree
conditions it was captured; an unexplained re-record is indistinguishable from
silencing a real regression
```

Pass `--baseline PATH` to read or write a different file, which is how you take
a capture without touching the committed one.

### Decide whether `--accept-weakening` applies

A capture is compared against the baseline already on disk, in the same three
directions. A capture that raises a ceiling or lowers a floor is refused unless
you pass `--accept-weakening`.

Pass it when the weakening is real and understood:

- A modelo revision was removed, so a measurement population legitimately fell.
- A defect ceiling must rise because the tree genuinely carries more findings
  and you are recording that fact rather than hiding it.

Do not pass it to get a capture through:

- The run was taken over a half-landed tree, or while another contributor was
  mid-edit. Wait for the tree to settle and capture again.
- A suite is failing and the capture is the quickest way past it. Fix the
  failure.
- You do not know why the counter moved. Find out first.

A lowered floor is the dangerous case, which is why the guard exists. A raised
ceiling shows up on the census and the next honest capture pulls it back. A
floor lowered by a capture taken over a half-read tree is silent forever: every
later run passes the anti-vacuity check against a population it never had to
reach.

Review the recorded diff before you commit it, the same as any other baseline.

## Where the tool lives

The implementation is under `dev/registry/conformance/`. It composes fact
libraries that ship inside the application under `src/cadrumo/`, and the
boundary is one-way: the tool reads the application's public surfaces, and the
application never reads anything under `dev/`.
