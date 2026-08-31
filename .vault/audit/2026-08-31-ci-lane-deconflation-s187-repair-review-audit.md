---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:cd2cd0ef9c5adb54d7db02dc5b4bdc64f1c440cc6b6f52ab04ff6b3933147340'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
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

# `ci-lane-deconflation` audit: `Review P05 S187 private-import repair`

## Scope

Independent final review of P05.S187 source commit `fa87bac54a`, HIGH audit `68be5278bebdaae6a6df099e736a97e0b896b83e`, and repair `49a3cb56d85ea2b636c1f5f7958114f148be61da`: parity-test resource import, direct materialisation ownership, row-materialisation cycle boundary, and reproducible repair evidence.

## Findings

No triaged findings. Repair `49a3cb56d85ea2b636c1f5f7958114f148be61da` changes only the S187 execution record and the exact parity-test import, restoring public `core.resources` for `bundled_path`. An immutable grep confirms the parity test contains no `core.resources._boundary` import; static inspection confirms it retains its direct `Modelo349OperadorTotalsParity` and `compute_modelo_349_operador_totals_parity` import from `_invoice_row_materialization.py`.

The original extraction remains sound: `_invoice_row_materialization.py` is a cohesive private M347/M349 materialisation sibling; `invoice_bindings.py` is its direct production consumer and injects the M347 threshold predicate. The sibling's `InvoiceObservation` import is type-checking-only and its resolver import is local to the parity calculation, avoiding an initialization cycle without a facade. Direct public-resource/materialisation import smoke passed. The repair record carries literal executable ruff, format, and focused five-test commands with `5 passed in 17.28s` and exit 0; the original 49-test evidence and 894/577 size measurements remain intact.

## Recommendations

Approve P05.S187 after the private-import repair.
