---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:b45156eaf28e7128809aa624ba67e19a8bb545ab92cb483e4ad96468fb081492'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-dead-surface-adr]]"
---
# `casilla-schema` audit: `S30 application verification deletion review`

## Scope

Formally reviewed commits `2cb136c892` and `94be71c0ff`, the pending one-line application API-index deletion, and the current S30 execution record against the accepted dead-surface decision and the completed S29 adjudication. The review read both commits in full, repeated semantic discovery over code and decision records, performed an exact residual census, and ran the real registry verifier, deletion gate, living reconciliation selection, import-linter, baseline-integrity tests, Ruff, and whitespace checks.

The core deletion is semantically correct. All seven tracked package and package-test files and all four generated package API stubs are absent, with no alias, shim, replacement package, or importable module. The committed registry diff deletes exactly 83 `cadrumo.application.verification` consumer declarations and 85 corresponding construct references. The live registry retains all 82 verification expectations and its canonical `RegistryVerificationPolicy`. The exact verifier passes over 73 modelos and 94 revisions with 565 surviving application links and no `verification` application-link surface. The living reconcile implementation changed only displaced prose, and its focused 41-test selection passes. The pending `cadrumo.application.rst` change is exactly one direct deletion of the dead subpackage toctree entry.

## Findings

### [ ] import-linter-residual | high | A stale ignored edge aborts the repository layering gate

`.importlinter` still declares `cadrumo.application.verification._verify -> cadrumo.adapters.inbound.declaracion`. The real `lint-imports` command aborts with "No matches for ignored import" before reporting contract results. Two S30-specific ledger assertions also fail because the ignored-import source no longer resolves and remains unreconciled after its matching test-ledger baseline entry was deleted. This is a live configuration reference to the removed surface and means the deletion cannot claim a clean structural or import-boundary gate.

### [ ] complexity-baseline-residual | medium | The active complexity ratchet still names the deleted verifier twice

`dev/audit/complexity_baseline.json` retains `src/cadrumo/application/verification/_verify.py::verify_declaracion` in both its cyclomatic and cognitive sections. The real current-owner baseline test fails because those keys no longer resolve to files, and strict complexity reports the cognitive entry as resolved debt that must be removed. This is an active baseline, unlike the intentionally immutable error-code preimage ledger and historical changelog entry, which correctly retain historical references.

### [ ] verification-claims | medium | The execution record overstates closure and misstates the follow-up history

The S30 execution record says path-scoped Ruff format completed with zero diagnostics, but `ruff format --check` reports `_reconcile_casilla.py` and `_schema.py` would be reformatted. `git diff --check` also reports nine registry TOML files with new blank lines at EOF. The record says two stale baseline corrections remain working-tree changes, but both were committed in follow-up `94be71c0ff`; it discloses only the concurrent `2cb136c892` collision and not the second commit. The record itself also begins with multiple blank lines before its title. Update the record to describe both commits, the post-commit fixes, and the actual verification boundary only after the remaining baseline/configuration defects and formatting failures are resolved.

### [ ] deletion-gate-scope | medium | The new structural gate passes while live deletion residues remain

The three-test gate genuinely proves package-path/import absence and scans product source, API stubs, and registry TOML for the constructed dead strings. It does not scan root configuration or developer baselines, so it passes despite the stale `.importlinter` edge and complexity entries. Extend the property gate to cover the live configuration and baseline homes, or pair it explicitly with their existing strict gates, so a future deleted surface cannot leave the repository layering check disabled while the deletion gate stays green.

### [ ] orphaned-error-locales | low | Four locale entries remain for the deleted error code

The error registry correctly removes `VerificationError` and `INTEGRITY_VERIFICATION`, but `errors.integrity.integrity_verification` remains in all four locale catalogues with no live error registration or other consumer. Remove the orphaned translations as deletion hygiene unless another living error is deliberately retargeted to that exact message key.

### [ ] whitespace-regressions | low | Nine edited registry files acquire redundant terminal blank lines

The committed registry sweep leaves nine `application_links` TOML files with a new blank line at EOF, independently reported by `git diff --check`. Normalize these files so the deletion diff remains mechanical and warning-clean.

## Recommendations

- Do not close S30 or tick its plan step until the HIGH and MEDIUM findings are resolved and the exact gates are rerun.
- Remove the dead `.importlinter` ignored edge and both active complexity-baseline entries; preserve the changelog and immutable error-code preimage ledger as historical evidence.
- Correct the two Ruff formatting defects and nine TOML whitespace warnings, then rerun Ruff format/check, the import-linter gate, the current-owner baseline test, the structural deletion gate, and the exact registry verifier.
- Amend the S30 execution record through the VaultSpec CLI to disclose `2cb136c892` and `94be71c0ff`, replace the stale working-tree claim, remove leading blank lines, and record only reproduced gate results.
- Retain the S29 conclusion: no dead verifier behavior should be copied into living reconcile. Its persisted-revision comparison contract remains intact and its focused behavioral selection is green.

Final verdict: FAIL. The architectural deletion and registry data sweep are correct, but live configuration/baseline residues disable or fail required structural checks, and the execution record's closure claims are not currently accurate.

## Verification

- Semantic code and decision discovery: exit 0; the accepted dead-surface ADR, S29 audit/exec, S30 exec, live reconcile owners, and active complexity gate were the leading relevant clusters.
- Exact deleted-data census: 83 removed consumer declarations and 85 removed construct references; zero current authoritative registry consumer declarations or `verification` application-link surfaces.
- `aeat app registry verify`: exit 0; 73 modelos, 94 revisions, 82 verification expectations, 565 application links.
- Structural deletion gate: 3 passed.
- Living reconcile selection: 41 passed.
- `lint-imports`: exit 1 on the stale deleted-module ignored import before contract evaluation.
- Focused structural/baseline tests: 10 passed and four failed; three failures are S30-owned stale import-linter/complexity references, while the fourth stale `_iva_wallet_gate` ledger row is unrelated concurrent work and is not attributed to S30.
- Ruff check: passed on the sampled changed surface. Ruff format check: failed on two S30-changed files.
- BasedPyright could not provide an isolated green proof in the current shared tree because it reported seven diagnostics in unrelated concurrent ledger-import WIP; those diagnostics are not attributed to S30.
- `git diff --check`: nine S30 registry TOML whitespace warnings.

## Resolution

All S30-owned findings were resolved in the reviewed closeout.

- `import-linter-residual` is closed: `9b733f098e` removes the stale ignored edge. The real import-linter now evaluates all six contracts and reports six kept, zero broken; the two exact S30 ledger assertions pass.
- `complexity-baseline-residual` is closed: the same commit removes both dead verifier entries, and the current-owner baseline assertion passes.
- `verification-claims` is closed: the S30 exec is re-attested, begins directly at its title, names `2cb136c892`, `94be71c0ff`, and the reviewer closeout accurately, and VaultSpec reports clean markdown and modified-stamp checks. The formatter and whitespace claims now reproduce.
- `deletion-gate-scope` is closed by the paired live gates: the three structural tests pass, the exact import/config assertions pass, the complexity owner assertion passes, and import-linter completes rather than aborting. The standalone structural gate remains intentionally focused on shipped source, API docs, and authoritative registry TOML.
- `orphaned-error-locales` is closed: `9b733f098e` removes the exact orphan leaf from all four locale catalogues.
- `whitespace-regressions` is closed: `9b733f098e` removes all nine redundant terminal blank lines, and `git diff --check` over the complete S30 commit range is clean.

The remaining exact-string hits are not live S30 residues: `CHANGELOG.md` is historical release history; `error_code_default_suggestion_preimage.json` is an immutable, Git-proven historical migration ledger; and `.parked-registry` is explicitly non-authoritative parked input outside the verified registry root. None is imported, shipped as the application surface, or consumed by the authoritative registry verifier.

Final verdict: PASS. S30 deletes the complete standalone package and tests without a shim, removes all 83 authoritative consumer rows and 85 construct references, preserves living reconciliation and all 82 registry verification expectations, and now has clean structural, registry, import-boundary, formatting, whitespace, lifecycle-attestation, and exact owned baseline proof.

## Final verification

- Exact owned baseline selection: 6 passed.
- Structural deletion gate: 3 passed in the earlier bounded run.
- Living reconcile selection: 41 passed in the earlier bounded run.
- Import-linter: six contracts kept, zero broken.
- Ruff format/check over the changed Python epicentres: clean.
- Registry verifier: exit 0; 73 modelos, 94 revisions, 82 verification expectations, 565 application links, no `verification` surface.
- Exact deletion census: 83 consumer declarations and 85 construct references removed.
- API index: exactly one deleted dead-package toctree line, committed in `1c1ad9396a`.
- `git diff --check` over `2cb136c892^..9b733f098e`: clean.
- VaultSpec feature check: structure, frontmatter, markdown, links, exec mapping, schema, modified stamp, and encoding clean. Its two remaining warnings concern the pre-existing feature index and S02 body, not S30.
