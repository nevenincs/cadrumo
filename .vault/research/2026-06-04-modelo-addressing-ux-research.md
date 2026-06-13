---
tags:
  - '#research'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-03-cli-workflow-redesign-epic-adr]]'
  - '[[2026-06-04-cli-workflow-redesign-epic-research]]'
---

# `modelo-addressing-ux` research: `human modelo addressing for CLI work surfaces`

This research investigated whether the modelo CLI can stop exposing raw work-unit and calculation-revision identifiers as the normal operator path, while preserving the existing internal content-addressed model. The trigger was the educational flow requiring operators to copy a work-unit id, then a calculation-revision id, then switch back to the work-unit id for export.

## Findings

The current tutorial and quickstart flows require the operator to track two different 64-character identifiers during the first filing journey. The command sequence is internally coherent but externally hostile: `work calculate` consumes a work-unit id, `work verify` and `work file` consume a calculation-revision id, and `modelo export` consumes a work-unit id while optionally selecting an exportable calculation revision.

The documentation surface reflects the same problem in several places. `docs/tutorials/index.md`, `docs/getting-started.md`, and `docs/how-to/quickstart.md` all instruct the operator to copy ids between steps. The generated CLI reference also documents raw `work_unit_id` and `calculation_revision_id` arguments as required for core lifecycle verbs.

The domain distinction is clear in code. A `WorkUnit` is the stable filing workspace keyed by bucket, modelo, filing year, period, and registry revision. A `CalculationRevision` is one immutable calculation attempt under that work unit. Multiple calculation revisions can exist under one work unit; recalculation produces a new content-addressed revision rather than mutating the prior result.

The existing domain already carries the pointer fields needed for friendlier addressing. `WorkUnit.current_calculation_revision_id` advances on successful calculation, `WorkUnit.filed_calculation_revision_id` advances on filing, and `WorkUnit.current_filing_record_id` points at the current filing record. These pointers let the application distinguish latest draft/current calculation and filed answer without asking the operator to paste the underlying hash.

The current CLI has partial mitigations, not an abstraction. `work list` exists, several help strings accept unambiguous id prefixes, and `work verify` or `work file` now hints when the user passed a work-unit id where a calculation-revision id was required. That is a good error recovery path, but it still makes the operator learn the internal id taxonomy.

The application services are intentionally id-centric and should remain so. `create_work_unit`, `calculate_modelo_revision`, `verify_modelo_revision`, `file_modelo_revision`, and `export_modelo_revision` operate on stable ids and enforce content-addressing invariants. The friendlier model should be introduced as an application/CLI addressing layer above these services, not by weakening the stored id contracts.

The project already has precedent for this exact kind of resolver. `modelo export` accepts a work-unit id and, when no explicit revision is supplied, selects the most recent filed revision or verified-complete revision. `work resume` accepts either a workflow run id or a work-unit id and resolves the latter to the latest persisted run for the work unit's modelo and period. Both are operator-friendly resolution layers over stricter internal records.

The prior CLI persona audit recorded the same failure mode: inconsistent id arguments where `calculate` takes a work-unit id and `verify`, `file`, and related operations take a calculation-revision id. That audit classified it as a UX defect, and existing regression tests cover the current hint-based mitigation.

## Candidate Abstraction

Introduce a typed operator-facing modelo target, for example `ModeloWorkSelector`, with fields:

- `modelo`
- `filing_year`
- `period`
- optional registry `revision_id`
- optional `bucket_id`
- optional `calculation_selector`, such as `current`, `latest-draft`, `latest-verified`, `filed`, or an explicit calculation-revision id

The default resolution should be command-specific:

- `work calculate --modelo 130 --year 2026 --period 1T` resolves or creates the active work unit for the target model period, then calculates it.
- `work verify --modelo 130 --year 2026 --period 1T` resolves the work unit, then verifies `current_calculation_revision_id` if it points at a draft; if no current draft exists, it refuses with a clear message.
- `work file --modelo 130 --year 2026 --period 1T` resolves the work unit, then files the current verified-complete revision. If there are multiple verified-complete candidates and the pointer does not disambiguate, it refuses and lists choices.
- `modelo export --modelo 130 --year 2026 --period 1T --output ...` resolves the same way export already does from work-unit id: prefer filed, otherwise latest verified-complete, never default to a superseded revision.
- Read-only verbs such as `work status`, `work history`, `work revisions`, and `work revision` accept the human target while keeping explicit ids as advanced disambiguators.

The CLI should keep raw id arguments as advanced escape hatches where they are genuinely useful for audit, JSON consumers, and exact replay. The common path should not require them.

## Ambiguity Rules

The resolver must fail loudly when the human target is not unique. Ambiguity can happen if more than one non-discarded work unit exists for the same bucket, modelo, year, and period but different registry revision ids. The error should list the candidate registry revisions, display names, states, and short id prefixes, then require `--revision` or explicit id.

The resolver must not silently cross buckets. By default it should resolve only inside the active profile bucket. `--bucket-id` can remain an advanced explicit override where existing commands already support it.

The resolver must not silently select a non-draft revision for verify. Verify is a draft-to-verified transition; if the current pointer names a filed or already verified revision, the command should say the target has no current draft and suggest recalculating or selecting an explicit revision.

The resolver must not silently export superseded filings. The existing export behavior is correct: default to current filed or verified-complete, and require explicit id for superseded records.

## Implementation Path

First, add application-layer query helpers, not CLI-only string hacks. A focused module such as `application.modelo._selectors` can resolve work units by bucket, modelo, filing year, period, and optional registry revision, returning a typed result or typed ambiguity/error. The helper should use existing repositories and domain models.

Second, add resolver helpers for command-specific calculation revision selection. These helpers can consume a resolved `WorkUnit` and the calculation-revision catalogue, applying verbs' rules for `current`, `draft`, `verified`, `filed`, or `exportable`.

Third, adjust CLI commands to accept both existing id form and human target flags. For example, keep `aeat app modelo work calculate <work-unit-id>` working, but allow `aeat app modelo work calculate --modelo 130 --year 2026 --period 1T`. Once the human-target path is tested and documented, tutorials should switch to the human form.

Fourth, update JSON payloads to keep emitting the real ids. The abstraction is for addressing, not for hiding audit metadata from machine consumers. Operators see readable target fields first; ids remain in structured output.

Fifth, add real-behavior CLI tests that create profiles and work units through the production CLI, calculate, verify, export, and assert the human-target path never requires pasted hashes. Tests should cover no match, ambiguous registry revision, no current draft, current verified, filed/exportable preference, and active-bucket isolation.

## Risks

The largest product risk is silently operating on the wrong revision. That is mitigated by command-specific selection rules, explicit ambiguity refusals, and never defaulting to superseded records.

The largest architectural risk is inventing a parallel model of work units outside the domain. The resolver should return existing `WorkUnit` and `CalculationRevision` objects and should live at the application boundary, keeping domain content-addressing unchanged.

The largest testing risk is writing tautological tests that mirror the resolver logic. The tests should drive the real CLI over an isolated storage root and inspect persisted state through the real repositories after each command.

## Recommendation

Proceed with an ADR for a `modelo-addressing-ux` application/CLI abstraction. The design should preserve internal ids and content-addressing, but demote them from the ordinary operator path. The operator's default target should be modelo, year, period, and active profile bucket; the engine resolves that to the current work unit and the command-appropriate calculation revision.

The first implementation slice should be narrow: human-target addressing for `work calculate`, `work verify`, and `modelo export`. Those three commands cover the tutorial's worst copy/paste loop and prove the resolver pattern before touching the rest of the work subgroup.
