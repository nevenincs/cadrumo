---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:a341e9bce335b4319534b6e0d21a847af5a878aeeba43b56709b79c028e778bb'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S03 XML dictionary casilla identity review`

## Scope

Formal read-only review of the unstaged `W01.P02.S03` change in `_export_parse.py`, `test_export_parse.py`, and `test_conformance_profile.py` against the `casilla-schema` research, plan, canonical-derivations ADR precondition, registry-authority rule, and quality gates. The review tested the accepted identity grammar, the resolved source-applicability boundary, the real bundled Modelo 100 dictionaries for 2020 through 2025, conformance accounting, and the absence of test doubles or mirrored business logic. Unrelated shared worktree changes were excluded.

The parser remains numeric-only by default. The new branch is enabled only when the resolved dictionary source declares `applies_from` in 2024 or later, and it accepts only a single uppercase ASCII letter through the anchored `^[A-Z]$` grammar. Numeric identities keep their prior behavior at every year. Empty, starred, lowercase, multi-letter, mixed alphanumeric, decimal-like, punctuation, and non-ASCII letter values remain non-casilla rows.

The authority chain is truthful. The M100 2023, 2024, and 2025 dictionary sources declare `applies_from` as 2023-01-01, 2024-01-01, and 2025-01-01 respectively. The regression tests load the real bundled registry and its official dictionary sources rather than copied rows. A direct production-path census found no letter identities in 2020-2023 and exactly `A`, `C`, `D`, `E`, `F`, `G`, `H`, `I`, `J`, and `M` in both 2024 and 2025, with no other nonnumeric identity.

## Findings

No actionable findings.

The implementation does not admit a general alphanumeric grammar: direct probes reject `AA`, `A1`, `1A`, lowercase `a`, and a non-ASCII letter even when the letter branch is enabled. The real-source conformance comparison preserves the four pre-2024 dictionary counts and increases both 2024 and 2025 dictionary and divergence counts by exactly ten, exposing the official letter identities as extras rather than dropping them. The focused tests import production parser and loader surfaces directly; they introduce no fake, mock, stub, patch, monkeypatch, skip, xfail, or duplicated calculation/parser logic.

## Recommendations

No changes requested. Preserve the source-owned applicability gate and the anchored one-letter grammar when later dictionary revisions are added; do not replace either with a broad alphanumeric parser or an honor-system identity allowlist.

## Verification

- Focused parser and conformance tests: 43 passed in 36.49 seconds on the reviewer run.
- Scoped Ruff: exit 0, all checks passed.
- Scoped BasedPyright: exit 0, zero errors, warnings, and notes.
- Scoped `git diff --check`: exit 0.
- Production-path bundled census: 2020-2023 expose zero letter identities; 2024 and 2025 each expose the same ten official single-letter identities and no other nonnumeric form.

Verdict: **PASS.** `W01.P02.S03` implements the narrow revision-aware identity correction requested by the plan, preserves pre-2024 numeric-only behavior, makes the ten official current-year identities visible to conformance reporting, and adds truthful real-authority regressions without compatibility restoration.
