---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:a8d9ade2cf7a63e68fe438c468c243599ec4986571aa8ef42496bad6d6d5de89'
related: []
---

# `deadline-window-revision-authority` audit: `s50 cli calendar parity`

## Scope

Audit the S50 CLI payload and all-profile rendering diff for thin-adapter boundaries, canonical overview ownership, schema fidelity, resolver reuse, and regression-test integrity.

## Findings

The repair deletes the competing compact calendar DTOs, validates application-built entries and events through the already-existing complete transport payloads, and uses the existing action resolver for warning remedies. No calculation, registry selection, filing-evidence merge, status, or cadence logic is introduced at the CLI boundary.

### warning-action-json | high | Resolved warning action required JSON-mode serialization

The first review found that a resolved Pydantic action had been inserted directly into a mapping passed to standard-library JSON encoding. The implementation now serializes that already-resolved action with `model_dump(mode="json")`; the finding is resolved.

### warning-action-envelope | high | Resolved warning action was one wire level too shallow

Clean detached verification showed that raw `ResolvedNoticeAction` JSON did not preserve the established declared-action envelope. The follow-up uses typed transport composition over canonical `ActionReference` and `ResolvedActionArgument` primitives, resolves once through the existing catalogue path, and emits the required nested identity plus sibling live CLI path. Both affected real-CLI cases pass and formal re-review accepted the repair; the finding is resolved.

## Recommendations

Accept S50. The two clean-verification regressions now pass; retain the seven-case targeted CLI set as the parity gate.
