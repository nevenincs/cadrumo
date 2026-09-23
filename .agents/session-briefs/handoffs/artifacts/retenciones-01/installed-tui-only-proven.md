# Installed TUI-only 2025 withholding journey, run 3: proven (2026-09-23)

A complete 2025 professional and urban-rent filing year was driven entirely through public installed-TUI controls, with a fresh encrypted store. No CLI step ran anywhere. The export oracle and the fresh reopen each ran as their own installed child. No AEAT submission was made. "Filed" means a local filing record, not official submission, confirmation or payment.

## Pinned identities

- **Source commit:** `393da09995`. It contains the create-or-reopen route with its pinned-authority fix (`a8c5b42266`) and the work_create locale keys (`81037765b3`).
- **Wheel:** built from a detached checkout of that commit. SHA-256 `779c7119044d1a224a09d3d0e31f6f318f41d903e29d846a22150a1845b92e82`. Executable `aeat.exe` in a fresh venv.
- **Installed `cadrumo/__init__.py` SHA-256:** `930e3f61c79bd2e3ff1f8aa11d1abd5d16bfbaab360ea739ae41f519f71b0ae7`.
- **Launcher SHA-256:** `2bcd144d71966656b03831cf965654c2b6fb46a9f7c7c8ceb6b4ae697fb261bd`, identical in source and installed.
- **Served authority:** the wheel-embedded one, `logical_generation` `4fa84c26a651ebd7a60499c4b5edb1a682329d07c8663336f82df1fa6720dd15`. It uses store format v1 with the v1 reader shipped in the same wheel. It predates the worktree's format-v2 cutover and is unaffected by it.
- **Acceptance driver:** `dev/acceptance/retenciones/installed_tui_withholding.py`, SHA-256 `97bed086a2ce8c3340f81e2dc0526eea751ca986467cdf48acafe00b14ca7476`.

## What was proven, in order, in one installed child

- **Registration and profile.** Profile registration and setup through Profile Manager: the withholding payer answers, plus the 2025 1T/3T/4T no-activity attestations for Modelo 111 and Modelo 115.
- **Ledger.** Two received invoices.
- **Withholding.** The Withholding route with its year selector. A visible refusal of a professional capture missing the payer-supplied territorial detail (`refused: invalid_withholding_evidence`). Then professional and urban-rent capture.
- **Declarations create-or-reopen.** Created 111 2T and 115 1T, 2T, 3T and 4T. Re-submitting 111 2T reported "Reopened" and created no second unit. 111 0A was refused with a visible reason: the period is undeclared for that modelo. Created 180 0A and 190 0A.
- **Periodic lifecycle, 17 steps.** Calculate and verify every source period; export 111 2T and 115 2T; file each source period locally.
- **Annual lifecycle, 6 steps.** Calculate, verify and export 180 and 190.

## Independent export validation

This ran in its own installed child against the served layouts (`export-validation.json`, status `proven`). Record structure, counts and financial meaning matched the independent oracle for:

| Modelo | Period | Bytes | SHA-256 |
|---|---|---|---|
| 111 | 2T | 1346 | `4665365b…6ed61f` |
| 115 | 2T | 846 | `f6130a22…75f926` |
| 180 | 0A | 1000 | `0e7d54c3…5a8694` |
| 190 | 0A | 1000 | `b03a4efc…6bafc7` |

The 180 and 190 files are byte-identical to the `annual4` exports, which the TUI→CLI path produced and independently validated from the same synthetic inputs. That is cross-frontend parity.

## Fresh-process reopen

A new installed child logged in through the visible Login screen (`reopen.json`, status `proven`). It read back the 111 and 115 withholding evidence, all 7 declarations, and exactly 5 local filing records: 111 2T and 115 1T through 4T.

## Boundaries of this proof

The stale-context and history boundary covered here is the fresh-process reuse, refusal and filing-history readback. It does not cover a correction after filing. Items outside this run are listed as `modelo_123_counting` and `later_year_modelo_193_export`. The Modelo 123 count authority is still missing (see the m123 evidence record), and there is no official later-year 193 design. `historical_profile_context` is `current_profile_at_run`, meaning the historical year ran under the profile as it stands today.

## Records

- Receipts copied here: `installed-tui-only-run3/{tui-only,export-validation,reopen}.json`.
- Earlier attempts remain failure evidence: `installed-tui-only-run1-failure.md`, and run 2. Run 2's journey child proved the journey, but its parent-side validation used the shared tree's newer reader against the v1 store and failed with `AuthorityStoreFormatError`. Validation now runs in the installed interpreter.