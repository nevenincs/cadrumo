---
tags:
  - '#audit'
  - '#quality-gate-zero-closure'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:369fc9f6f6a2b402b01b7d87085f535e53025bd5958cb63de77bc41c61931f66'
related:
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]"
---
# `quality-gate-zero-closure` audit: `Dev tooling product-boundary reconciliation`

## Scope

This review applies the repository's stated boundary: `src/cadrumo` is the tax-filing product, while `dev` exists only to build, inspect, and verify that product. It reviews the accepted blind-green decision and its execution evidence, the current worktree, the six detector ecosystems, their tests and fixtures, `dev/audit/report.py`, `dev/registry/newmodelo/tests/test_manager.py`, the surviving predecessor gates, and the CI routes that decide which evidence is blocking.

The acceptance standard is `aeat-quality-gates`: a gate must exercise the real authority, parser, compiler, resolver, calculation, or serializer named by its contract, with a supported path and a representative failure. For registry declarations, `aeat-registry-authority-flow` additionally requires diagnostics to consume `ValidatedRegistryAuthority` rather than parse source fragments as an independent API. This was a review-only pass; no production or development code was edited by this audit.

## Findings

### mutation-meta-stack | high | the six mutation ecosystems protected development analyzers rather than tax-filing behavior

The campaign proposed `mutmut` to answer whether a test can fail when its subject changes. Its standing configuration instead mutated one newly written detector at a time and judged it with that detector's paired meta-test. The delivered subjects were: `tautological_assertion_scan.py`, a partial interpreter for constant assertion truth; `subsuming_disjunctions.py`, a partial interpreter for string-containment disjunctions; `self_echoing_tokens.py`, a source/data-flow model for CLI tokens echoed into refusals; `locale_bound_assertions.py`, a source/data-flow and child-pytest model for locale-pinned absence assertions; `taxonomy_absence_conformance.py`, a source model backed by hand-authored declaration symbols in product tests; and `gate_verdict_grammar.py`, a source/data-flow model of one import-linter output consumer.

Those mechanisms could show that their own synthetic fixtures killed mutations in their own implementation. They did not mutate or exercise registry compilation, revision selection, calculations, filing admission, persistence, export serialization, or a user-visible tax workflow. The aggregate evidence recorded 227 meta-tests taking 217.31 seconds, more than five thousand lines across scanners, paired gates, and fixtures, and bounded mutation runs ranging from about 58 seconds to more than 1,054 seconds per detector. That is disproportionate to the product risk, and several fixtures existed to distinguish detector implementation branches rather than a supported product contract.

The work did expose a few genuine one-time defects: redundant assertion branches were strengthened, a locale-dependent negative assertion was removed, the import-linter report parser was corrected, and a mock-spy cache test was replaced with observation of real cache identity. Those repairs are product-facing evidence and do not require permanent mutation infrastructure. The current deletion of all six scanner/gate/fixture ecosystems and removal of the `mutmut` dependency/configuration is therefore the correct disposition.

### registry-conformance-priority | high | the real registry conformance suite remains non-blocking while meta-tests had per-push priority

`just test-registry-conformance` exercises the real bundled authority and currently has a documented product-facing failure: the live filing proof authority lacks the protocol method production calls. `.github/workflows/ci-full.yml` still runs that suite with `continue-on-error: true`. By contrast, the now-removed detector tests were placed in `dev/quality/tests` and therefore ran in the blocking per-push `test-dev-ci` lane. This inverted the product-risk order: analyzer self-conformance was blocking, while a known failure at the real filing/registry handoff was advisory.

The complete registry sweep is legitimately expensive and need not run on every push. Its known real failure must nevertheless be repaired, and a green full registry conformance run must become blocking in its scheduled/full lane. A small authority-backed smoke set covering publication, revision selection, stale snapshot refusal, and one real filing/export handoff should be the per-push product signal if the full suite cannot meet that cadence.

### architecture-record-conflict | high | accepted governance still mandates the tooling the codebase now removes

The accepted blind-green ADR still states that `mutmut` is installed and pins all six detector/gate pairs as standing scope. The repurposed quality-gate plan repeats that obligation, lists the removed modules as completed deliverables, and leaves `W08.P28.S121` open specifically to mutation-test the verdict detector. This is a live contradiction, not harmless history: future work following accepted architecture would be required to recreate the deleted stack, and current conformance cannot truthfully satisfy the plan's completion conditions.

The user's explicit product-boundary decision supersedes that mandate. A follow-on architecture disposition must mark the blind-green ADR superseded for the standing mutation/meta-detector decision and retire or close the repurposed W08 plan without claiming its removed mechanisms remain installed. The measurements and one-time repairs should remain historical evidence.

### duplicate-tautology-interpreter | medium | the off-lane inline predecessor remains after the dedicated scanners were deleted

`dev/tests/test_no_tautology.py` is a 296-line second home-grown AST interpreter. It models literal truth, Boolean short-circuiting, constant and chained comparisons, membership, and identity, then tests that model with a large list of fabricated source statements. It is invoked only through `test-ratchets`, not the per-push product lane. Although it scans product tests, it duplicates the deleted tautology scanner's maintenance burden and protects an assertion-syntax taxonomy rather than a tax-product invariant.

Delete this file and its `test-ratchets` recipe entry. Existing Ruff `F` and `SIM` coverage already catches several high-yield shapes. If the live tree is clean, enabling narrow built-in rules such as `PLW0129` and `PLR0124` is a proportionate replacement; do not rebuild the full Python-semantics model locally.

### advisory-report-parser | medium | the health report still owns a second grammar for an authoritative external gate

`dev/audit/report.py` remains useful as a scheduled projection of product health, but its layering dimension still parses individual import-linter verdict lines with `_verdict_of` and independently counts `.importlinter` sections with `_declared_contract_count`. Its new parametrized tests therefore protect the report's interpretation of development-tool output. This is the same duplicate-grammar seam that created the original false status, and it provides no product benefit over the process result: either a completed import-linter run succeeds, or a non-zero run is red and its native output explains whether the cause was a broken contract or an aborted configuration.

Keep the report, but simplify this dimension to three states: unavailable executable/exception/timeout is AMBER; return code zero is GREEN; any non-zero return is RED with a bounded native diagnostic excerpt. Delete the per-contract grammar and independent declaration counter. `just check-imports` remains the authoritative blocking boundary gate.

### authority-backed-consumer-gate | low | application-link protection now exercises the published registry authority

The first `application_link_consumers` prototype was not acceptable: it reparsed raw TOML, selected a contract through an ID suffix, and introduced a standalone scanner, paired test, recipe, and suite row. That prototype is now removed. Its replacement in `dev/registry/tests/test_declaration_invariant_gates.py` loads `ValidatedRegistryAuthority`, walks every typed application link whose consumer names shipped `cadrumo` Python, resolves the public dotted target, and pairs the real-tree sweep with an isolated missing-target control. This is stronger, smaller, and aligned with the registry authority rule. Keep the authority-backed test and do not restore the standalone scanner.

### cache-effect-test | low | the newmodelo cache assertion now observes real behavior

`dev/registry/newmodelo/tests/test_manager.py` no longer proves only that a reset function was called. It primes the public locale-coverage loader, observes that a write changes the cached object identity, and observes that a no-op scaffold preserves the replacement identity. This test can fail when the real cache effect is removed and should remain.

### duplicate-tautology-interpreter-closure | low | the inline predecessor and its recipe entry were removed during reconciliation

Resolved in the reviewed worktree. `dev/tests/test_no_tautology.py` is deleted and `test-ratchets` no longer names it. No replacement local AST interpreter was introduced.

### advisory-report-parser-closure | low | the report now projects import-linter exit status directly

Resolved in the reviewed worktree. `audit_layering` retains the executable/exception/timeout AMBER path, maps any non-zero completed process to RED with a bounded excerpt of native output, and maps zero to GREEN. `_verdict_of`, `_declared_contract_count`, and their parser tests are absent.

### authority-backed-consumer-scope-correction | low | the final application-link gate is intentionally limited to the filed-observation contract

The replacement was narrowed after the broader sweep encountered registry consumers that are semantic labels rather than Python callables. The final gate still consumes `ValidatedRegistryAuthority`, but selects typed portal application links carrying the filed-declarations-observation contract and resolves their callable owners. This is an honest scope for the concrete stale-owner defect and retains the isolated negative control.

### architecture-record-partial-closure | medium | the orphaned mutation step is retired but the standing mandate remains

`W08.P28.S121` is now listed as retired, so the plan no longer presents that deleted detector mutation run as open work. The accepted ADR and the plan's description, completed implementation rows, and verification criteria still state that `mutmut` and the detector mechanisms are installed standing obligations. The high governance-conflict finding therefore remains open in narrower form until the architecture corpus records the user's superseding decision.

### residual-roundtrip-inventory-closure | low | the hardcoded inventory and its CI pin are removed

Resolved after explicit authorization from the workflow owner. `dev/tests/test_roundtrip_coverage.py`, its explicit `ci-full.yml` pytest argument, and the command-pin assertion are deleted atomically. The full-lane step continues to invoke the real ledger, storage, and profile roundtrip suites directly; no shim, duplicate test, shadow inventory, or re-export replaces it.
### historical-shape-detector-closure | low | narrowing and production-metastate parsers are removed

Resolved in the reviewed worktree. The narrowing-delegator and production-metastate gates were custom AST and textual classifiers whose paired tests constructed synthetic Python modules around historical removed shapes. Their underlying product cleanups remain; the detectors, fixtures, tests, recipes, and aggregate-suite rows are deleted.
## Recommendations

1. Keep the current deletion of the six detector modules, all paired gates and mutation-shaped fixtures, the taxonomy declaration residue, the source-inspection revision census, and all `mutmut` dependency/configuration. Do not replace them with another mutation engine or an equivalent local parser.
2. Keep the direct product-test strengthenings found during the campaign, the authority-backed application-link consumer gate, the real newmodelo cache-effect test, and focused gates that directly exercise registry compilation, revision refusal, filing, calculation, persistence, and serialization.
3. Retain the completed deletion of `dev/tests/test_no_tautology.py` and its `test-ratchets` reference. Prefer narrow Ruff rules over a local Python-semantics implementation.
4. Retain the completed simplification of `dev/audit/report.py` layering status to external-tool availability plus exit status, bounded native diagnostic output, and no second verdict grammar or declaration counter.
5. Reconcile governance through a superseding architecture decision and plan retirement so accepted records no longer require the deleted mutation/meta-detector stack.
6. Repair the known real registry-conformance failure, make the full green registry suite blocking in its scheduled/full lane, and promote only a bounded real-authority smoke subset to per-push CI.
7. Minimal verification for this reconciliation is: prove no deleted detector, fixture, mutation dependency, or `PINNED_TAXONOMY_LITERALS` reference remains; run the two authority-backed application-link tests; run the newmodelo cache-effect test; execute `lint-imports` itself; run the real registry closure outcomes; then run Ruff and the type checker over changed development files. Do not rerun or recreate mutation evidence for removed development analyzers.
