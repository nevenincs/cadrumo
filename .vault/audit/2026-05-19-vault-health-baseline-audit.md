---
tags:
  - "#audit"
  - "#vault-health-baseline"
date: "2026-05-19"
modified: '2026-05-19'
related:
  - "[[2026-05-19-code-duplication-sweep-plan]]"
  - "[[2026-05-19-code-duplication-sweep-audit]]"
---

# vault-health-baseline audit: baseline vault check before duplication-sweep cleanup

## Scope

Captures the output of `uv run --no-sync vaultspec-core vault check all` on branch `chore/eliminate-shims`
(worktree `chore-476-restructure-execution`) before any `--fix` is applied. Establishes the
error / warning baseline against which subsequent cluster work for the
`code-duplication-sweep` campaign will be measured. No code or vault edits are made by
this audit; it is read-only inventory. Raw log captured at
`/tmp/vault-check-baseline.log` (698 lines, CLI exit 1).

## Findings

### Totals

`Total: 196 errors, 49 warnings`, split into the five buckets reported by the CLI:

- `structure: 96 errors`: filename-pattern violations on `.vault/audit/`, `.vault/exec/`,
  `.vault/index/` files that embed `W##` / `P###` / `S####` identifiers in
  the filename stem, or that omit the required canonical type suffix.
- `dangling: 96 errors`: wiki-link entries in related frontmatter that resolve
  to non-existent stems. Almost entirely paired with the structure
  errors (renamed or never-created audit-review stubs inside the
  `cli-workflow-redesign` cluster).
- `orphans: 17 warnings`: isolated audit documents with no related and no feature
  siblings (`calc-engine-*`, `cross-domain-handoffs-swarm`, `developer-leak-cycle1-*`, `w85-*`, etc.).
- `features: 32 warnings`: missing feature indexes, stale feature indexes, and a
  few "plan but no ADR" / "exec but no plan" warnings.
- `schema: 4 errors`: all four `2026-05-1{5..8}-linkage-design-audit-plan.md` files lack an ADR reference.

### Errors touching this campaign documents

The `code-duplication-sweep` feature has exactly one finding in the baseline:

- Stale feature index: related has 4 links but the feature has 6
  documents. Fix: `vault feature index -f code-duplication-sweep`.

Cause: the parent-trace audit pass landed two new docs
(`2026-05-19-code-duplication-sweep-audit` and this baseline audit) without re-running vault
feature index. The fix is non-destructive and in-scope - see
Recommendations.

The Spanish-stem authority ADR (`2026-05-19-spanish-stem-terminology-authority-adr`) itself does not
surface in the baseline (well-linked, structurally clean). The
companion `spanish-tax-glossary` reference is flagged as warning-only:

- Missing feature index. Fix: `vault feature index -f spanish-tax-glossary`.

No structure, dangling, or schema errors touch documents owned by
`code-duplication-sweep` or `spanish-stem-terminology-authority`.

### Errors not touching this campaign (informational, no action by this team)

Grouped by owning feature:

- `cli-workflow-redesign`: ~140 errors. Filenames carrying `W##`-`P###`-`S####`
  segments under `.vault/audit/` and `.vault/exec/` violate the canonical filename
  pattern, plus paired dangling links across ~50 summary-exec /
  review-audit docs. Stale feature index (347 links versus 349
  documents). One index file (`.vault/index/W61.index.md`) lives at the wrong
  path.
- `profile-lifecycle-cli`: 12 errors. Exec stubs `P0#-S##.md` lack the required
  `-exec.md` suffix.
- `cli-workflow-redesign-modelo-145`: 2 errors. Audit filenames embed `P###` segments.
- `schema-hardening`: 8 structure errors (audit / reference filenames missing
  canonical suffix). Stale index (11 versus 12 docs).
- `operator-blind`: 4 structure errors. Audit filenames missing `-audit` suffix.
- `live-iva-compensation-wallet`: 2 structure errors. Exec / audit files missing canonical
  suffix. No feature index.
- `linkage-design-audit`: 4 schema errors (plans with no ADR reference) and 1
  missing feature index.
- `restructure-execution`: 1 structure error (`2025-05-22-restructure-execution-phase1-step1.md` has a 2025 prefix and
  no canonical suffix). Stale index. Plan / ADR missing entirely.
- `modelo-036-census-sync`: plan with no ADR; no feature index.
- `developer-leak-cycle1-*` (4 sub-features) plus `developer-leakage-emergency`: 5 orphan audit docs, 5 missing
  feature indexes.
- 15 features missing a feature index only (warning-only):
  `calc-engine-aeat-coverage`, `calc-engine-grounding-swarm`, `calc-engine-session-snapshot`, `catalogue-validation`, `corpus-inventory`, `cross-domain-handoffs-swarm`,
  `export-import-fidelity-swarm`, `iva-compensation-chain`, `linkage-tooling-prior-art`, `modelo-130-relation-regression`, `persistence-boundary-identity-swarm`, `selector-binding-drift-swarm`, `w85-crossdomain-cli`, `w85-persistence-boundary`, `workflow-cli-surface-swarm`.
- 5 stale feature indexes (warning-only): `operator-testimonial`, `audits-resolution`, `cli-workflow-redesign`,
  `code-duplication-sweep` (the campaign one is the only in-scope item), `schema-hardening`.

## Recommendations

### Action items for this campaign

- After the duplication-sweep cluster work merges, run `vault feature index -f code-duplication-sweep`
  to refresh the stale index (4 to 6 entries). Non-destructive;
  expected delta is two new entries pointing at this baseline audit
  and the parent-trace duplication-sweep audit.
- If the Spanish-stem ADR campaign wants a clean glossary-feature
  index, run `vault feature index -f spanish-tax-glossary` separately. Flagged here for the
  glossary owner; out of scope for this audit.

### Out-of-scope recommendations for other feature owners

- `cli-workflow-redesign` owner: ~140 errors. The bulk are filename-format violations
  introduced before the canonical pattern was enforced. Running vault
  check all --fix auto-renames the offending audit / exec files and
  rewrites paired related links, but it would touch ~100 documents -
  should be a deliberate single-PR rename pass owned by the redesign
  team.
- `profile-lifecycle-cli` owner: 12 exec stubs need `-exec.md` suffix; --fix would handle
  these.
- `schema-hardening` owner: 8 audit / reference filenames need canonical
  suffixes. Run `vault feature index -f schema-hardening` afterwards.
- `linkage-design-audit` owner: 4 plans lack an ADR. Either author the ADR
  (`vault add adr -f linkage-design-audit`) or move the plans under a research umbrella.
- `restructure-execution` and `modelo-036-census-sync` owners: missing ADR / plan upstream of
  existing exec / plan documents.
- Owners of the 15 indexless features above: run feature-index per
  feature.
- Owners of the 5 stale indexes (excluding `code-duplication-sweep`): same.
- Owners of the 17 orphan audit docs in `developer-leak-cycle1-*`,
  `calc-engine-*`, `w85-*`, `cross-domain-handoffs-swarm`, etc.: add a related entry
  pointing at the parent ADR / plan, or move into a proper feature
  folder.

### Suggested vault check all --fix runs

Do not run --fix blindly across the whole vault: it will rename ~100
files and rewrite many cross-references in a single pass, mixing
authorship across unrelated campaigns. Suggested scoped runs, each
owned by the named feature team:

- `cli-workflow-redesign` team: vault check all --fix against their cluster (after
  confirming no other team has uncommitted edits to the affected
  docs).
- `profile-lifecycle-cli` team: targeted rename of the 12 exec stubs.
- `schema-hardening` team: targeted rename of the 8 affected filenames.
- All other teams: feature-index runs for missing or stale indexes -
  these are non-destructive and per-feature.
