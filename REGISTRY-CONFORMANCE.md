# Registry conformance

This runbook covers the registry conformance tool for Cadrumo contributors:
what it measures, how to read each of its four commands, how to record a
revision's governance provenance, and how the release closure gate decides.
AEAT is the Spanish tax authority that owns the official modelo structure.

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
| `closure` | The derived cross-authority release report; a gate with `--check`. | 0, or 1 with `--check` when the release predicate is not satisfied. |
| `stamp` | Write one revision's declared governance provenance. | 0, or non-zero on refusal. |

`report` and `coverage` are screens. They print findings and exit 0 whatever
they find, so they never block a lane.

`closure` is a screen by default and a gate with `--check`. Use the bare form
to read the current state; use `--check` when you want a non-zero exit while
any law-selectable revision fails the release predicate.

`report` and `coverage` accept `--json` for the strict payload instead of the
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
unused_axis axis=extraction_profile.confidence.review_required population=43
note n/a means NOT MEASURED or NO CLAIM MADE, never zero, while '-' is a real
  empty list; ...
```

Read the closing `note` before you read any number. `n/a` means not measured or
no claim made — never zero — and `-` means a real empty list. A reader who
takes `n/a` for zero draws the opposite conclusion from the one the row states.

### Read the release closure

```bash
uv run --no-sync python -m dev.registry.conformance closure
uv run --no-sync python -m dev.registry.conformance closure --check
uv run --no-sync python -m dev.registry.conformance closure --offline
```

`closure` joins three application-owned authorities for every registered
revision and reports them as three limbs on one row:

- **temporal_coverage** — every filing year and period the revision's selector
  reaches, through the supported-filing-years horizon, is law-selectable and
  admits a validated snapshot at the revision's declared authority grade.
- **source_connectivity** — the revision's casillas are connected to their
  source domains through evidence that has not expired at the `--as-of` date
  (defaults to today).
- **filing_export** — for a filing-grade revision, each materialised layout
  retains byte-matching official authority and both public conformance and
  encrypted source-owned replay attest the canonical writer. A revision below
  filing grade reports this limb `not_applicable`.

The output is greppable rows: one `closure` summary carrying
`release_eligible`, `satisfied_revisions`, `refused_revisions`,
`join_disagreements` and `blocking_reasons`; one `closure_row` per revision
with each limb's outcome; and one `closure_refusal` per refused limb naming
the reason, the owning disposition and the reconsideration condition.

A limb outcome is one of `satisfied`, `not_applicable`, `refused` or
`unmeasured`. `unmeasured` is a refusal, never a pass: it means no authority
was supplied for that limb, and the release predicate treats it as blocking.

`--offline` evaluates without the live source-connectivity and filing-export
proof authorities. Use it for a cheap read when the live authorities are
unavailable. Because it marks those limbs `unmeasured`, an offline run can
detect a regression but can never approve a release; `closure --offline
--check` exits 1 for every filing-grade revision until the live proof is
supplied.

`--json` prints the strict report payload instead of the rows.

### Decide whether a refusal is yours

Every `closure_refusal` row names an owner disposition. Read the owner before
you act: a `missing_evidence` refusal on `filing_export` belongs to the
export-generation authority and asks for a public conformance vector and a
current replay receipt; a `law_selection_refused` refusal on
`temporal_coverage` belongs to the revision's own manifest and means two
revisions of one modelo claim the same filing year and period token. Do not
resolve a refusal by editing the report's inputs; resolve it at the surface the
disposition names, then re-run.

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

## Where the tool lives

The implementation is under `dev/registry/conformance/`. It composes fact
libraries that ship inside the application under `src/cadrumo/` — the temporal
coverage, source-connectivity and filing-export coverage reports under
`application/registry/` — and the boundary is one-way: the tool reads the
application's public surfaces, and the application never reads anything under
`dev/`.
