---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-09'
modified: '2026-07-10'
body_hash: 'sha256:6d58b0fb7353556f03d7f91681ff22ba4102e0852917d3849492ca8fcd76807f'
step_id: 'S05'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
  - "[[2026-07-09-m210-irnr-phase-2-engine-adr]]"
---

# declare the M210 plazo windows as REGISTRY deadline_windows TOML (grounded in the bundled CONSOLIDATED Orden EHA/3316/2010 art 5, in vigor 24/06/2026 - amended by HAC/56/2024 art 4.2 + HAC/623/2026 art 1.2), NOT hand-coded in the read-only _plazo.py resolver. CURRENT LAW (supersedes the stale HAC/56/2024 January wording the earlier spec carried): a-ingresar general = 20 primeros dias de abril/julio/octubre/enero por el trimestre natural anterior (period 1T-4T)

## Scope

- `arrendamiento a-ingresar = 20 primeros dias de ABRIL del ano siguiente`
- `cuota cero = 1-20 enero`
- `a devolver = desde el 1 de febrero (4 anos)`
- `imputadas tipo 02 = presentacion todo el ano natural siguiente (1 enero-31 diciembre`
- `la domiciliacion es 1 abril-23 diciembre). Only the a-ingresar-general quarterly (1T-4T) is a clean (modelo`
- `period) window and is built now`
- `the resultado/tipo-dependent annual plazos are DEFERRED to a resultado/tipo-keyed deadline ADR addendum (a period token cannot express a computed resultado or tipo). period_selector widen (1T-4T) also deferred - pinned EVENT-N by test_modelo_210_registry.py:110`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/deadline_windows/ + src/aeat/_data/registry/aeat/legal/irnr.toml + src/aeat/_data/registry/aeat/modelos/210/revisions/2025/application_links/`

## Description

- Corrected the plan surface: deadline windows are registry data, not `_plazo.py` (a read-only resolver that reads `authority.deadline_windows`); per the registry-authority-flow and schema-central-config rules, and the M216 precedent, they live in registry TOML.
- Grounded the M210 plazos verbatim against the BUNDLED consolidated `orden-eha-3316-2010.html` art 5 (in vigor 24/06/2026; amended by Orden HAC/56/2024 art 4.2 and Orden HAC/623/2026 art 1.2). This corpus cross-check found the earlier spec's dates STALE (the HAC/56/2024 January arrendamiento wording was superseded by HAC/623/2026 to April), so the stale dates were NOT authored.
- Authored the a-ingresar general trimestral windows (1T-4T, filing years 2025 and 2026) in a new `deadline_windows/0001-deadline_windows.toml`: each opens on the 1st and closes on the 20th natural day of the month after the devengo quarter (4T closes the following January).
- Authored the `orden-eha-3316-2010:art-5` legal entry (corpus_ref `#a5`, verbatim `required_text`, honest agent-prepared `reviewed_by` pending operator re-stamp).
- Added the required `deadline` application link to the M210 revision (the registry validator refuses deadline windows without one).
- Added real resolver + continuity tests, including a test proving the ambiguous annual `0A` window is deliberately NOT authored (resolves to None, not a silent-wrong calendar).

## Outcome

- Landed as commit `0c6689e068` (4 files, +200 lines, explicit-pathspec, zero foreign).
- Gates (all `-n0`): `test_extemporaneidad.py` 14 passed (M210 1T -> 2025-04-20, 4T -> 2026-01-20, gap-free continuity, 0A -> None); `test_catalogue_verification.py` + `test_authority.py` 28 passed (legal-grounding corpus check + clean registry load); `test_m210_tipo_renta_codes.py` 16 passed (Slice A, no regression); ruff + ty clean.
- HONESTY CALL: the bare quarterly windows are honest because the period token IS the discriminator — only general a-ingresar carries a quarterly token; every annual/resultado case (cuota-cero, a-devolver, arrendamiento a-ingresar, imputadas) is annual (would carry 0A, which resolves to None). A 1T window therefore can never misrepresent a cuota-cero/a-devolver filer.

## Notes

- DEFERRED (honestly, tracked): the resultado/tipo-dependent annual windows (arrendamiento a-ingresar April; cuota cero 1-20 January; a devolver from 1 February, 4 years; rentas imputadas tipo 02 presentation all of the following calendar year 1 January-31 December) cannot be keyed by a single period token because the deadline window keys on (modelo, period) and the plazo depends on a computed RESULTADO. These are deferred to the resultado/tipo-keyed deadline ADR addendum (m210-plazo-keying ADR `0781535702`).
- DEFERRED: the M210 `period_selector` widen (1T-4T) — blocked by a hard pin `test_modelo_210_registry.py:110` asserting `period_selector.periods == ("EVENT-N",)` (the deliberate `4c81463619` decision). Per the coordinator's condition (b), reported rather than silently changed; the windows resolve without it (the validator confirms no window <-> period_selector coupling), so they are calendar-declared pending work-unit activation.
- CORRECTION (post-landing follow-up): the imputadas tipo-02 PRESENTATION plazo is 1 January-31 December of the following year (todo el ano natural siguiente), NOT 1 April-31 December (that range is the DOMICILIACION direct-debit sub-window). The independent grounding-verify caught this; the wrong figure lived in the `irnr.toml`/`deadline_windows` descriptive prose and the plan-text edit, all corrected in the follow-up commit. No functional impact: the imputadas window was deferred, not shipped.
- LOCK: the commit was gated for an extended window by a recurring 0-byte `index.lock` (statusline `git diff` debris); it was NOT force-removed (coordinator adjudicates locks centrally); an armed explicit-pathspec retry landed it cleanly when the lock cleared.
