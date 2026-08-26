---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:fdb788c10d891db3fe0e0df61b66f7f2a4d007e60766f6aefb248f5acf5c542f'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
  - "[[2026-08-11-tui-interface-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---

# `casilla-schema` audit: `W04.P10.S34 TUI review`

## Scope

Fresh-context formal review of W04.P10.S34 against the accepted casilla read-model and TUI architecture decisions, the live plan and execution record, the complete implementation, test and facade files, and the locale changes in commit `0c5fb5253d`. The review checked dependency direction, public-facade consumption, read-only rendering, canonical-record coverage, localization, S35 separation, real encrypted-storage Textual pilots, named outliers, responsive evidence, test integrity, vault honesty, and shared-worktree preservation.

Verdict: **CHANGES REQUESTED / FAIL**. The implementation is mechanically green and read-only, but it cannot close S34 while it adds new Textual code to the legacy package prohibited by the accepted TUI decisions and while its finding and responsive acceptance proofs remain incomplete.

Focused evidence: the seven integration pilots passed in 37.81 seconds; focused Ruff passed; focused BasedPyright reported zero errors, warnings, or notes; all 23 referenced translation keys resolve in Catalan, English, Spanish, and Hungarian. The full locale scaffold remains red only on the unrelated catalogue drift already itemized in the S34 execution record. No fake, mock, stub, patch, monkeypatch, skip, xfail, mirrored business rule, repository access, write path, filter state, or current S35 control was found in the owned implementation. No production, test, locale, plan, or execution file was changed by this review.

## Findings

### legacy-tui-placement | critical | The new screen violates the accepted canonical TUI root

- [ ] `src/cadrumo/adapters/inbound/tui/_modelo_work_review_screen.py:21` introduces new Textual types under the legacy inbound-adapter package, and `src/cadrumo/adapters/inbound/tui/__init__.py:53` plus lines 115-116 publicly export the screen and host. D0, D10, and D11 of the accepted `2026-08-11-tui-architecture-adr` make `src/cadrumo/entrypoints/tui/` the exclusive home for Textual code, reserve Modelo review under `modelo.view`, and prohibit Textual classes outside that root. The accepted `2026-08-11-tui-interface-adr` likewise requires the inbound TUI adapter to disappear and forbids public screen internals in the canonical root facade. The older S34 plan row still naming the legacy path is now inconsistent with those accepted decisions; following that stale locator grows the migration inventory instead of satisfying the governing architecture.

### lossy-finding-rendering | medium | Finding meaning and canonical expectation identity are dropped

- [ ] `src/cadrumo/adapters/inbound/tui/_modelo_work_review_screen.py:204` renders the raw dotted `message_locale_key` inside grounding JSON instead of resolving the operator-facing localized message, and lines 211-224 omit the canonical optional `expectation_id` entirely. The CLI's established projection resolves the localized message, while the canonical `ModeloVerificationFinding` model carries expectation identity for precise registry-rule traceability. `src/cadrumo/adapters/inbound/tui/tests/test_modelo_work_review_screen.py:104` constructs no expectation id and line 167 asserts only the kind token, so an internal untranslated key and lost expectation identity both pass unnoticed.

### responsive-proof | medium | Size-labelled pilots do not prove a usable responsive surface

- [ ] `src/cadrumo/adapters/inbound/tui/tests/test_modelo_work_review_screen.py:148`, line 189, and line 216 launch real pilots at `80x24`, `160x48`, and `120x36`, but assertions inspect backing row counts and selected model-derived cell tokens only. They do not prove visible layout, clipping, access to the last canonical row and wide columns, horizontal or vertical navigation, focus behavior, or frame content. All named outliers run only at the widest size, and there is no locale or light/dark matrix. These tests would remain green if the narrow terminal were visually unusable, so they do not satisfy the accepted TUI responsive proof.

### s35-control-regression | low | The no-filter assertion excludes only one control type

- [ ] `src/cadrumo/adapters/inbound/tui/tests/test_modelo_work_review_screen.py:175` rejects only Textual `Input`. A premature S35 filter built with `Select`, `SelectionList`, `Checkbox`, `RadioSet`, `Button`, or another interactive control would pass this gate. Current whole-file inspection found no such filtering or write control, so this is a regression-proof gap rather than a present behavior defect.

### transitional-placement-curation | resolved | Placement is a sanctioned transitional receipt

The follow-up `2026-08-12-casilla-schema-s34-tui-architecture-curation-audit` establishes the accepted dependency sequence: casilla-schema delivers and closes this surface in the legacy owner, then the blocked TUI architecture campaign performs the consumer-complete migration and legacy deletion. This re-review accepts that curation and does not reopen the historical placement finding.

### lossy-finding-rendering | resolved | Localized message and expectation identity are preserved

The repaired `ModeloWorkReviewScreen._mount_findings` now gives `expectation_id` and the resolved `tr(message_locale_key, **message_facts)` result their own columns while retaining structured facts and grounding. The blocked real-storage pilot supplies a non-null validated expectation id, resolves a Spanish fixture message with the canonical fact interpolation, asserts both values reach the table, and asserts the internal dotted key does not.

### responsive-proof | resolved | Real pilots prove usable narrow, normal and wide geometry

The repaired pilots exercise M100 2024 at `80x24`, `120x36`, and `160x48`, checking compositor geometry, header and table visibility, focus, horizontal travel, outer vertical scrolling, last-column cursor, and access to the final canonical row. A separate M720 pilot covers all four supported locales across narrow and wide widths and proves a compositor-observed dark-to-light theme change. The named M720, M200 2024, M100 2024/2025, and M349 coverage remains intact.

### s35-control-regression | resolved | Likely filter and mutation control families are absent

The blocked pilot now rejects `Input`, `Select`, `SelectionList`, `Checkbox`, `RadioSet`, and `Button`. Whole-file inspection confirms S34 still carries no filtering state, mutation action, repository access, or policy derivation.

### execution-receipt-history | medium | The repaired execution record misstates the initial commit boundary and one gate result

The current S34 execution record says commit `0c5fb5253d` landed the initial screen, tests, facade exports, locale leaves, **and execution record**. Git proves `0c5fb5253d` contains only the seven code/test/locale files; the execution record and initial audit landed later in `4e7de18d4b`. Its repaired atomicity note acknowledges later review and uncommitted repairs but does not correct that explicit false attribution. It also claims focused Ruff format passed, while the exact focused `ruff format --check` reports that `src/cadrumo/adapters/inbound/tui/__init__.py` would be reformatted. Ruff lint and strict BasedPyright do pass. Because the delegated review may not edit the execution record, this remains the only open finding and keeps the verdict at CHANGES REQUESTED until the receipt is corrected through the VaultSpec CLI and the claimed format gate is made truthful or rerun green.

Re-review verification: nine real encrypted-storage/Textual pilots passed in 55.00 seconds; focused Ruff lint passed; focused BasedPyright reported zero errors, warnings, or notes; 25 literal screen keys resolve in Catalan, English, Spanish, and Hungarian; scoped diff-check passed; feature-scoped VaultSpec checks carry only the known stale feature-index and old S02 body warnings. No fake, mock, stub, patch, monkeypatch, skip, xfail, mirrored business logic, staging, commit, or unrelated edit was introduced by the review.

### execution-receipt-history | resolved | Commit boundaries and focused gate evidence are now truthful

The corrected execution record distinguishes `0c5fb5253d` as the code, test, facade, and locale commit; `4e7de18d4b` as the initial execution-record and review-audit commit; and `bcc1c6bca0` as the architecture-curation audit commit. Its atomicity note explicitly records the pending repair/closure commit and the one-Step/one-atomic-commit violation without rewriting shared history. The exact receipt-only recheck reports all three touched Python files already formatted, Ruff lint clean, and scoped `git diff --check` clean. The prior receipt-honesty finding is closed.

Final verdict: **PASS**. No open S34 findings remain. The accepted curation owns the transitional placement; localized finding identity and text, responsive real-pilot proof, and S35-control exclusion are verified; and the execution receipt now matches Git history and the reproducible focused gates. This PASS authorizes normal S34 lifecycle closure while preserving the recorded non-atomic history and later consumer-complete migration obligation.

## Recommendations

1. Resolve `legacy-tui-placement` before further S34 implementation: reconcile the stale S34 plan locator through the plan-owning VaultSpec verb, then land the real Modelo view and its tests in the accepted `cadrumo.entrypoints.tui.modelo.view` ownership slice without a compatibility facade. If sequencing still blocks that root, keep S34 open rather than adding new legacy surface.
2. Resolve `lossy-finding-rendering` by rendering the localized finding message from `message_locale_key` plus its typed facts and preserving `expectation_id` in the review surface; add a non-English real-pilot case carrying a non-null expectation id.
3. Resolve `responsive-proof` with assertions over actual rendered frames and navigation at `80x24`, `120x36`, and `160x48`, exercising the named outliers across the supported locales and both themes to the proportional boundary required by the accepted TUI decisions.
4. Resolve `s35-control-regression` with a structural assertion that rejects the full interactive filtering and mutation control family while still allowing the S34 navigation bindings and read-only table interaction.
5. Re-run the seven focused pilots, Ruff, strict BasedPyright, targeted locale resolution, the applicable TUI import-boundary gate, and feature-scoped vault checks before requesting re-review. Keep W04.P10.S34 unchecked until every open finding is closed or formally deferred by an accepted authority.
