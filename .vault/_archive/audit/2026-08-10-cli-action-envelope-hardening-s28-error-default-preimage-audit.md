---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:c418a44ed9df6bd6e6dff3b9b3a85ecdccef66e7c7f1cc82e66bf0e539ade36b'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-W05-P08-S28]]"
---
# `cli-action-envelope-hardening` audit: `S28 error-code default preimage independent review`

## Scope

Independent review of `W05.P08.S28` after the registered `ErrorCode.default_suggestion` field and its registry declarations were deleted. The review covered the policy-free runtime schema, locale-derived text prefixes, the exact historical preimage evidence, owner partitioning, focused error-envelope contracts, and the campaign reference linkage.

## Findings

### historical-preimage-ledger | high | initial deletion evidence did not retain every former declaration

The source deletion in `7f40a9388e897574e18aa50d674403152cb4cc83` removed the live `default_suggestion` authority but did not leave an auditable row for every deleted declaration. The closing remediation pins the full parent commit `930ef9f4017a23cccaf4990d287beb014fc9723c` and AST-extracts all 612 former declarations from the nine registry shards. The checked-in non-runtime ledger records the exact old expression source and source location, so repeated `None` and repeated command literals remain distinct. It requires the exclusive shard owners `S50` through `S57` and `S64`; `S28` owns no downstream migration row.

### runtime-policy-boundary | low | no policy authority was reintroduced while closing the evidence gap

The live `ErrorCode` model rejects the retired field and has no action or no-recovery projection field. Error envelopes accept only already-resolved typed actions. Category text prefixes resolve from registered locale keys rather than an English fallback, and the selected `en`, `es`, `ca`, and `hu` catalogues cover every category.

### independent-review-disposition | low | pass after remediation

The exact AST ledger gate, its source-mutation refusal tests, focused envelope and CLI contract coverage, targeted formatting and lint, strict typing, and feature-scoped Vault checks all passed. The HIGH historical-evidence finding is closed; no unresolved S28-specific finding remains.

## Recommendations

- Keep the historical preimage ledger separate from `dev/cli_action_census_dispositions.toml`; the latter is the fail-closed current-universe adjudication authority and must continue rejecting stale compatibility rows.
- Use the immutable extractor and its source-location identity whenever downstream Steps `S50` through `S57` and `S64` consume a former registry default. Do not reconstruct the source list from aggregate counts or textual command matching.
- Preserve the `ErrorCode` policy-free boundary. Any recoverable result must be produced by a typed application verdict and resolved against the live command/input surface; permanent or safety outcomes remain explicit typed terminal results.
