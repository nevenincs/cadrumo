---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:29badc5d5e4cd418b50db725e703ba80d6099697e1a8f6e96c9b0efe0f61567a'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace secure-storage-performance-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `secure-storage-performance-hardening` audit: `W02.P03.S11 registration metadata review`

## Scope

Reviewed the W02.P03.S11 registration-metadata implementation against the
accepted command-scoped-loading decision and the preceding S09/S10 contracts.
The review covered the generated command and complete live-node projection,
source identities, deterministic Spanish/English generation, options and
arguments, help, hidden/deprecated flags, callback policy parity, the four
explicitly unimplemented identities, metadata-only operator discovery,
MCP/HITL reconciliation, tamper gates, and installed-package inclusion. The
review inspected only the Step-owned implementation and tests; unrelated
shared-worktree changes were excluded.

## Findings

### operator-surface-gap-reconciliation | high | Explicitly unimplemented schemas break live operator-surface parity

`test_live_operator_surface_reconciles_raw_click_paths_callbacks_and_mcp_policy_by_identity`
fails because `command_schema_refs()` publishes all 300 generated schema
identities while the materialized Click surface contains 296 implemented
identities. The exact mismatch is the four entries in
`DECLARED_UNIMPLEMENTED_SURFACES`: `config.profile.export`,
`config.profile.import`, `config.profile.rename`, and
`config.profile.subject_access_request`. The production operator inventory
filters these identities, but its authoritative live reconciliation test and
MCP/HITL compatibility contract still treat every schema reference as
callable. S11 therefore does not yet preserve the existing exact-set consumer
contract or provide one coherent meaning for the public schema-reference
projection.

### unresolved-prefix-evidence | medium | Metadata lookup drops the successfully resolved command prefix

`test_unresolved_leaf_retains_key_and_click_path_evidence` fails for
`app.not-a-real-command`: the former live resolver reported `resolved_cli_path`
as `("app",)`, while the metadata path reports an empty tuple. This weakens the
typed `SchemaResolutionError` used to diagnose an unknown or stale MCP command
identity. The complete generated node projection already contains sufficient
path information to derive the longest recognized prefix without importing a
handler subtree, so losing this evidence is not required by metadata-only
discovery.

## Recommendations

Resolve `operator-surface-gap-reconciliation` by making the callable schema
projection and its consumers agree explicitly on the 296 implemented versus
four declared-gap identities, then rerun the real operator-surface and MCP/HITL
reconciliation lanes. Do not silently advertise the four absent verbs or
delete their stated-gap evidence merely to satisfy the equality.

Resolve `unresolved-prefix-evidence` by deriving the longest known CLI prefix
from the generated complete-node projection and retaining it in
`VerbLeafResolutionFailure`; prove the unknown nested-key case remains
metadata-only.
