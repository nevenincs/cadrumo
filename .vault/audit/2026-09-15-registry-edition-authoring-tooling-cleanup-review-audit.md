---
tags:
  - '#audit'
  - '#registry-edition-authoring'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:dcf1e4d5643b1eef9d5073dfd9086f31c5d5a67349142f9509acdc49718fb5aa'
related:
  - "[[2026-09-09-registry-edition-authoring-adr]]"
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---
# `registry-edition-authoring` audit: `registry tooling cleanup review`

## Scope

Reviewed the registry-development cleanup at `74c7fe36` plus the current working tree against the accepted edition-authoring decision and implementation plan. The review covered registry recipes, the generic edition converter, source-tree installation, new-modelo and new-edition scaffolding, deleted-command caller closure, focused regression tests, synchronized authoring-command references, and the absence of changes under the live registry data tree and published authority surfaces.

## Findings

### registry-tooling-cleanup-review | high | The checklist tells authors to inherit an edition-specific completeness attestation

`dev/registry/newmodelo/checklist.py` says to author a `completeness_manifest` delta only where the inherited declaration differs. The accepted decision and the canonical loader explicitly exclude this family from inheritance because it is a derived claim about the current edition's formula closure and its presence is itself a capability attestation. Following the generated checklist can therefore omit the current edition's required closure declaration while giving the contributor the false impression that the baseline supplies it. No scaffold test pins the non-inheritance guidance.

### registry-tooling-cleanup-review | high | The manager API still fabricates applicability coordinates from the revision identifier

`NewModeloScaffoldManager.plan` and `scaffold` retain optional `valid_from` and `year_from` inputs and silently turn a leading four-digit revision token into January 1 and the same filing year. The CLI correctly requires both coordinates, but the exported manager remains a supported direct development surface and existing tests exercise the inferred path. A caller can therefore create plausible, ungrounded temporal declarations despite the cleanup requirement to derive or require real applicability coordinates.

### registry-tooling-cleanup-review | medium | A backfilled edition is hydrated from a later edition

`_latest_existing_edition` selects the maximum declared `valid_from` across all siblings without considering the new edition's requested `valid_from`. A seeded 2024 new-edition plan in a modelo containing only a 2025 edition emitted both storage baselines as `2025`. Storage ancestry is independent of legal continuity, but it is still declaration reuse: hydrating a historical edition from a later payload reverses the authoring direction and can import declarations that did not exist at the requested applicability boundary. The existing test covers lexical-versus-date ordering for a forward 2025 edition but has no backfill refusal or bounded-selection case.

### registry-tooling-cleanup-review | medium | Apply documentation overstates the converter's blocking gate

The module and `migrate_modelo` contracts in `dev/registry/edition_delta_migration.py` say `--apply` installs only when the gate has no findings, including no unchecked export editions. Both apply paths actually filter findings through `_is_source_finding`, while the outcome model classifies export and authority observations as later publication-readiness findings. Source application in the presence of those independent observations appears intentional, but the stale contract makes a source-only green signal read like full publication readiness. The intended split needs to be stated explicitly and pinned by a focused test with a non-source finding.

### registry-tooling-cleanup-review | low | Scaffold prose still describes legal predecessor inference and contains a broken instruction

`NewModeloScaffoldManager.plan` says it offers the newest edition as `predecessor`, although the implementation deliberately emits only storage baselines and no legal continuity claim. The checklist also begins the storage-baseline instruction with the malformed phrase `Declare Select`. These are small defects, but both occur in the contributor-facing explanation of the exact legal-versus-storage distinction this cleanup is meant to establish.

## Recommendations

- Correct checklist item 6 to require a complete, edition-owned completeness manifest and add a test that fails if scaffold/checklist prose suggests inheritance or delta omission for this family.
- Make applicability coordinates mandatory at the manager boundary as well as the CLI boundary, or accept a separately grounded typed coordinate object; remove the year-token inference tests and add refusal tests for omitted coordinates.
- Pass the requested applicability boundary into baseline selection and choose only a justified earlier candidate, or fail closed when no unambiguous earlier storage baseline exists. Add backfill, equal-date variant, and no-earlier-edition cases.
- Align the converter's module and function contracts with the source-application/publication-readiness split, and add a non-source-finding apply test so the distinction cannot drift again.
- Correct the manager docstring and malformed checklist sentence while preserving the rule that storage ancestry never manufactures legal continuity.
- After correction, rerun the focused scaffold, installer, converter-assessment, registry-collapse and modelo-100 integration tests; exercise live CLI help and every retained recipe with `just --dry-run`; then run the owning registry aggregate and a final deleted-symbol/reference sweep.

