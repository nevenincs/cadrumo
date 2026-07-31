---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:a7c923c8893ebcf40a1ec354c1b1fb7156c6b57c18e173585d86a58e1bd9d7dc'
step_id: 'S13'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# build the pure manager composing the src fact facades plus ModeloLocaleManager coverage rows, with typed payload models and a self-labelling no-validate degraded mode

## Scope

- `dev/registry/conformance/manager.py`

## Description

- Add `dev/registry/conformance/` with a package docstring stating the verb set and the
  screen-first posture, and `manager.py` holding every pure fold and renderer.
- Compose from public top-level facades only: `cadrumo.application.registry` for the
  conformance profile and its row type, `cadrumo.domain.calculations.registry` for the
  oracle inventory and its gap model, `cadrumo.core` and `cadrumo.core.external_constants`
  for the closed value sets, and `cadrumo.locales` for schema-local translation coverage.
  Nothing dots into a private module and nothing recomputes a fact the shipped composer
  already owns.
- Declare the strict frozen payload models: one flattened row per modelo revision, the
  registry-wide report envelope, the per-axis coverage row carrying its own caveat, the
  per-locale summary, the oracle attribution-gap row, and the ratchet baseline split into
  shrink-only ceilings and anti-vacuity floors.
- Add the locale axis by sweeping every directory-mode modelo once through
  `ModeloLocaleManager.coverage_records` and indexing by revision, auditing every output
  language except Spanish because the official registry casilla label is itself the
  Spanish authority and a Spanish row would read zero forever.
- Render greppable `record key=value` lines for the report, the per-axis coverage, and the
  ratchet comparison, with a trailing reading note on every rendering.
- Memoise the registry fold and the locale sweep per process and expose a reset the
  governance writer will call, so a post-write read never serves the pre-write tree.

## Outcome

Four decided-law properties are structural rather than advisory in the rendered output.

Absence stays absence. `None` renders as `n/a` and an empty list renders as `-`; the two
are distinct tokens and neither is `0`. The degraded read proves it: `required_coverage_gap_tiers`
reads `-` under the validating authority (measured, no gaps) and `n/a` under the degraded
loader (never measured), on the same revision.

Coverage is labelled as coverage. Every independent-check axis carries a `caveat` field
that rides in the JSON payload as well as the text, so a consumer reading `0.0460`
programmatically cannot miss it. A caveat that does not apply is omitted rather than
rendered `n/a`, because an axis needing no caveat has not failed to measure one.

No grade is synthesised. The report carries the individual signals only; there is no
composite score, letter, or percentage-of-conformance anywhere.

The degraded label rides per row. `registry_validated` is emitted on every rendered row,
not only the summary, so a filtered or re-sorted view cannot present a degraded row as
validated authority.

Two double-count hazards are closed by naming. `modelo_scope_classification_findings` is
folded at modelo scope for the registry total and named for its scope on the row, because
the shipped composer warns that summing it across revision rows multiplies each finding by
the revision count. `labels_required_per_locale` is named for its scope because
`labels_translated` is summed across locales, and the unnamed pair rendered a fraction
greater than one (`required=20 translated=60`) in the first draft.

Verification, validated read against the real bundled registry (elapsed 33.8 s cold):

```
summary registry_validated=true revisions=90 modelos=73 engineered_by_declared=0
independent_check_coverage=0.0460 reconciled_casillas=1261 independently_checked_casillas=58
reconciles_nothing_rows=39 grounding_findings=0 modelo_scope_classification_findings=24
required_coverage_gap_rows=0 coverage_unmeasured_rows=0 unattributed_oracle_payloads=1
unmatched_oracle_evidence=0 bundled_oracle_payloads=21 scope_diagnostics=0
unattributed_scope_diagnostics=0 locale_unavailable_modelos=0
census review_status=agent_reviewed revisions=0
census review_status=operator_reviewed revisions=0
census review_status=pending_review revisions=90
```

Every figure reconciles with the shipped composer's own run: 90 rows, 73 modelos, all 90
`pending_review`, zero `engineered_by`, registry-wide independent-check coverage 0.0460, 39
rows reconciling nothing, 24 modelo-scope classification findings, 5 dead axes, 1
unattributed oracle payload.

Degraded read on the same tree, showing the label and the three withheld axes:

```
summary registry_validated=false revisions=90 modelos=73 ... coverage_unmeasured_rows=90 ...
row modelo=130 revision=2019-y-siguientes registry_validated=false ...
  required_coverage_gap_tiers=n/a modelo_authorization=n/a
  modelo_authorization_evidence_class=n/a latest_revision_probed=n/a
  support_probe_describes_this_revision=n/a
note ... DEGRADED READ: rows are stamped registry_validated=false and the evidence-tier
coverage, support-probe, and authorization axes were not consulted at all.
```

`ruff check`, `ruff format --check`, and `ty check` are clean on the package.

## Notes

The mandatory semantic-discovery probe was WAIVED for this campaign by explicit operator
direction: the search index is broken and the service is stopped, and starting or
reindexing it was forbidden. Grounding was done by whole-file reads of the shipped
composer, both fact-builder modules, the locale manager, and all three precedent dev CLIs,
plus targeted `rg` passes for the exact export surfaces. Recorded so the waiver is visible
rather than assumed.

A peer campaign is mid-flight on Step S30 in the same worktree: the M303 prorrata oracle
payload is STAGED as a rename to carry its filing year and is FURTHER modified in the
working tree (two lines added, five removed, the scenario-input split). Nothing was touched.
This materially moves two counters this surface reports — a first validated read taken
before the rename returned 1 unattributed payload and 0 grounding findings, and a degraded
read taken afterwards returned 0 unattributed payloads and 3 grounding findings, which is
the attribution effect the fact-lifts audit predicted for a rename landing ahead of the
split. The consequence is deferred to the ratchet baseline step, which must state the tree
conditions it was captured under rather than presenting a moving measurement as a fixed one.

The locale sweep costs about 11 s and the validated registry fold about 9 s, so a cold full
report is roughly 20 s. Both are memoised per process, which matters for the behaviour tests
that invoke several verbs.
