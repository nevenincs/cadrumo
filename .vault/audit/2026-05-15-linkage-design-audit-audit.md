---
tags:
  - '#audit'
  - '#linkage-design-audit'
date: '2026-05-15'
modified: '2026-05-15'
related:
  - "[[2026-05-15-linkage-design-audit-plan]]"
  - "[[2026-05-15-linkage-design-audit-research]]"
  - "[[2026-05-15-linkage-design-audit-reference]]"
---



# `linkage-design-audit` audit: `Wave 1 close-out: type-system uniformity`

## Scope

Wave 1 of the linkage-design epic. Enrolled the entire AEAT codebase into
its own type system. Goal: zero `dict[str, Any]`, `Mapping[str, Any]`,
`: Any`, `-> Any`, `cast()`, and `# ty: ignore` / `# noqa` suppressions
in non-external-boundary code. Cross-checker dual gate (`ty` strict +
`pyright` standard with selected strict rules) wired into CI.

Plan: 12 Phases (P01-P12), 54 Steps, L2 tier. All Steps closed.

## Findings

### Headline numbers

- Suppression sites: **432 → 160** (-63%). Residual breakdown:
  - 96 `external-api` (out of scope; adapter boundary against
    untyped external APIs — Google Drive/Sheets, Playwright,
    `tomllib`).
  - 64 internal-leak categories, of which roughly 50 are
    documented-irreducible per agent reports (pydantic v2 dunder
    compatibility shims, stdlib protocol matches, frozen-model
    mutation in tests). The remaining ~14 sites can be picked up
    in a ratchet workstream.
- `ty check` → **0 diagnostics** across `src/aeat/`.
- `pyright` real-bug tier in `src/aeat/domain` and
  `src/aeat/application` → **0 errors**. Real-bug rules covered:
  `reportReturnType`, `reportCallIssue`, `reportArgumentType`,
  `reportAttributeAccessIssue`, `reportIncompatibleMethodOverride`,
  `reportUnhashable`, `reportUnsupportedDunderAll`,
  `reportIndexIssue`, `reportTypedDictNotRequiredAccess`,
  `reportUnnecessaryComparison`, `reportOptionalMemberAccess`,
  `reportConstantRedefinition`, `reportGeneralTypeIssues`.
- `pyright` deferred (annotation-completeness ratchet):
  `reportMissingParameterType` (153), `reportPrivateUsage` (99 in
  tests), `reportUnusedFunction` (27 in tests), and the entire
  Unknown-family — captured as a tracked workstream after the
  linkage-design epic stabilises.

### Phase-by-phase

- **P01 (inventory + tooling)** — `scratch/suppression_inventory.py`
  and `scratch/pydantic_audit.py` (the latter Wave 2 prep). Master
  catalogues at `scratch/out/`.
- **P02 (external-API stub acquisition)** — installed
  `google-api-python-client-stubs` (v1.36, community-maintained,
  Discovery-doc-generated); emptied the over-conservative
  `allowed-unresolved-imports` list because Playwright, Typer,
  Rich, and BS4 all ship `py.typed`; reduced one `dict[str, Any]`
  site at the `tomllib` boundary inside
  `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`.
- **P03 (test deliberate-suppressions)** — 14 test files cleaned;
  inline `# ty: ignore` / `# noqa: B010/E731` replaced with
  `pytest.raises`, named functions, or local-variable setattr
  patterns.
- **P04 (domain)** — 81 sites across 26 files cleared; canonical
  shapes (`Dialect`, `WorkUnit`, `FilingRecord` types) used to
  replace `Any`.
- **P05 (application)** — 70 sites across 28 files cleared;
  `TYPE_CHECKING` Protocol bridges and typed pydantic models
  used.
- **P06 (adapter-internal)** — 86 sites across 31 files cleared;
  `@runtime_checkable` Protocols, `TypedDict(total=False)` for
  Playwright `BrowserContextKwargs`, `TYPE_CHECKING` guards used.
- **P07 (core/)** — 20 sites cleared. `core/json_contract.py`
  internals typed (the wider adoption of `SchemaEnvelope` at CLI
  emit sites is Wave 3 work).
- **P08 (entrypoints/)** — 7 sites cleared.
- **P09 (dunder-override investigation)** — 5 sites investigated;
  3 replaced with typed patterns (TypedDict at test-helper level,
  TYPE_CHECKING for log SiteHealthStatus, `inspect()` for
  SQLAlchemy `_table_`); 2 documented as irreducible (PEP 562
  module `__getattr__`, `TextIOWrapper.reconfigure` kwargs
  protocol).
- **P10 ('other' bucket)** — 12 unclassified sites resolved; 11
  cleaned inline (locale-tree typed alias `LocaleNode`); 1
  intentionally kept at `cli_runner` delegation boundary with
  rationale.
- **P11 (dual-checker strictness gate)** — `pyright 1.1.409`
  installed; `pyrightconfig.json` configured for standard mode
  globally with explicit per-package rule promotions in
  `executionEnvironments` for `src/aeat/domain` and
  `src/aeat/application`. The 408 calibrated findings were
  triaged into "real bug" (251, all resolved in S47) and
  "annotation ratchet" (deferred). `just typecheck` runs ty +
  pyright together; CI invokes it on Ubuntu and Windows.
- **P12 (regression gates)** — four `semgrep` rules in
  `.semgrep/rules/` enforce the policy at the source-pattern
  level: `no-any-annotation`, `no-dict-str-any`,
  `no-cast-in-domain`, `justify-ty-ignore`. CI invokes semgrep on
  Ubuntu runners (semgrep requires Unix `resource` module).
  Windows contributors use the `scratch/suppression_inventory.py`
  Python script as a faster local-dev proxy.

### Notable byproducts

- Wave 2 foundation: 781 `BaseModel` subclasses inventoried by
  `scratch/pydantic_audit.py`. 56 candidate name duplicates and
  79 candidate field-set duplicates surfaced; 253 cross-package
  similarity pairs identified for Wave 2 consolidation.
- Documented-irreducible cases catalogued at
  `scratch/out/dunder_overrides.md`,
  `scratch/out/other_sites.md`, and
  `scratch/out/pyright_deferred.md`.
- 92.2% of pydantic models now declare `extra=forbid`, 93.6%
  `strict`, 97.6% `frozen`. The remaining models are mostly test
  fixtures and protocols where these settings do not apply.

## Recommendations

1. **Ratchet workstream for annotation completeness.** Defer
   `reportMissingParameterType` (153 sites), `reportUnknown*`
   family, and `reportMissingTypeArgument` (9 sites) to a tracked
   ratchet workstream. Track count downward over time without
   making it gating in CI.
2. **Begin Wave 2.** The `scratch/pydantic_audit.py` output is
   the authoritative consolidation target list. Highest-priority
   triads from the linkage research record: three CCAA enums,
   three CasillaSchema shapes, two ledger-observation layers
   (renta vs IVA), evidence-record family
   (`Justificante`/`Attachment`/`FilingDraft`).
3. **Promote** documented-irreducible suppressions into a single
   shared utility module so the rationale lives in one place and
   semgrep rule exceptions stay narrow.
4. **Pre-existing structural gaps** flagged during Wave 1 but out
   of its scope: `BrowserSessionFactory` vs `BrowserSessionLike`
   Protocol mismatch in `src/aeat/adapters/outbound/aeat/auth/__init__.py`;
   `SheetCellAddress` constructor signature drift in
   `src/aeat/application/storage/calc_sheets/_engine.py`. Both
   resolved during Wave 1 close-out; document the patterns in the
   relevant adapter/application ADRs.
5. **Coverage metric foundation.** The Issue Taxonomy v1
   reference document now has zero numerator entries for T-11
   coverage (down from 0 / 28 inventory rows). T-04
   (multi-shape) coverage moves with Wave 2; T-09 (typed-ID
   existence checks) coverage moves with Wave 3.
