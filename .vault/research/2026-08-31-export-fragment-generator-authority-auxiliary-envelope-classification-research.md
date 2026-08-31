---
tags:
  - '#research'
  - '#export-fragment-generator-authority'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:a4023e8f01691b52a3c03f10fb4a8614ff25650315bcd0b285bb1ca0e405781c'
related:
  - "[[2026-08-28-registry-narrow-mechanism-widening-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace export-fragment-generator-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown [label](path) links in the document body.
     - Cite external sources as bare URLs. Cite code, commits, packages, and
       standards as inline backtick locators: `src/module.py:42`, commit
       `abc1234`, `package@1.2.3`, RFC 9110. -->

<!-- DOCUMENT BOUNDARY:
     Research grounds; the ADR decides. Frame the option space with evidence
     and trade-offs; at most name the option the evidence favors and what
     the ADR must settle. Never record the decision here - a decision
     outside the ADR forks and goes stale when the ADR chooses otherwise. -->

# `export-fragment-generator-authority` research: `auxiliary envelope classification is spelling-determined`

<!-- Lead: the question, why it matters to `export-fragment-generator-authority`, and what was
     concluded - the evidence picture, not a decision. -->


## What was asked

Whether the eighteen-byte file closer that Modelo 390's page-zero design prints at row
20 is required in the emitted fichero, given that the generated export tree drops it and
two published Modelo 232 trees drop it too.

## What the design says row 20 is

It is numbered field 15 in the sheet's own `Nº` column, which runs 1 to 15. It sits
inside the field sequence, not below it, and it is eighteen bytes of type `An` whose
content is the constant `"</T3900EEEEPP0000>"`. It closes the opening tag that fields 1
to 6 compose -- seventeen bytes at positions 1 to 17 -- and field 6's own description is
`Tipo y cierre`.

The `***` in the position column has no legend anywhere in the workbook; it occurs
exactly once, at `Pág. 0!B20`. The reading consistent with the document is positional:
field 14 is the variable-length body beginning at 329, so field 15's offset cannot be
stated as a number. Row 21 confirms the shape with `TOTAL | variable | POSICIONES`.

The numbered pages' own twelve-byte terminators do not make it redundant. Those identify
a page, sit at real offsets, and are marked `OBLIGATORIO`. Field 15 is eighteen bytes and
closes the file. Modelo 303 emits both today.

The bundled consolidated corpus does not speak to fichero structure at all, so the
authority here is the design workbook, which the registry already classifies as
`evidence_tier = "layout_authority"`, `authority = "aeat"`, `review_status = "reviewed"`.

## The classification is determined by capitalisation, not by shape

Modelo 303's `DP30300` and Modelo 390's `Pág. 0` are row-for-row identical in structure.
Read directly from the two bundled workbooks:

| | 390 `Pág. 0` | 303 `DP30300` |
|---|---|---|
| row 19 | `B=329  C='variable'` | `B=329  C='Variable'` |
| row 20 | `A=15  B='***'  C=18` | `A=15  B='***'  C=18` |
| row 21 | `A='TOTAL'  C='variable'` | `A='Total'  C='Variable'` |

The only differences are capitalisation, and the year placeholder: 390 and 232 print
`EEEE` where 303 prints `AAAA`.

`record_design.py:1894` tests `raw_length == "Variable"` exactly, and `:1853` tests
`== "Variable"` for the total. Neither folds case. When the body marker is not
registered, the variable-envelope branch returns `None` at its first line and the sheet
falls through to the auxiliary-envelope-header branch, which is closer-less and
total-less by construction.

Causation was tested rather than inferred: loading each workbook, flipping only the case
of those cells in memory, and re-running the real extraction moves both 390 and 232 from
auxiliary header to variable envelope, closer included. 303 is unaffected because it
already reads `Variable`.

So the auxiliary-envelope-header shape is not a second AEAT record shape. It is the same
envelope reached by a different branch because AEAT typed one cell in lower case. The
branch's docstring calls the shape total-less, but 390 does declare a total at row 21; it
reads as total-less through the same comparison.

## The second hard-coded spelling

Even correctly classified, both modelos would be refused by `_CLOSER_RE` in
`dev/registry/pipeline/_variable_envelope.py:126`, which admits `AAAA` or four concrete
digits for the year and nothing else. Its own comment says "TWO official spellings, both
admitted" and reasons that neither is asserted against a filing instance because the
instance supplies the year. `EEEE` is a third spelling of that same placeholder, and the
comment's reasoning covers it, but the pattern does not.

## Scope of the consequence

This is not a Modelo 390 defect. Both published Modelo 232 revisions ship the same
omission from the same cause, and 390 would be the third. A ruling that the closer is
required is repaired once in the shared contract and fixes all three.

## Verification

The capitalisation contrast and the field numbering in this record were read directly
from the two bundled workbooks with `openpyxl`, not taken from a report. The two parser
comparisons and the closer pattern were read at `HEAD`, not in the working tree.

## Open

Whether an accepted filing or a live oracle confirms the closer in emitted bytes. This
record grounds the answer in the AEAT design document, which is the strongest authority
available without filing, and is the same authority every other layout decision rests on.
