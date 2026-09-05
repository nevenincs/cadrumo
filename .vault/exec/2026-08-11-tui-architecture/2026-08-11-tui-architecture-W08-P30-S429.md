---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:77099b314a92ca13040c6aafa3be98b55cdc8bddcd038818850784af58333c94'
step_id: 'S429'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Ground the M200/2024 casilla 00067 label in its pinned official cell, and gate that grounding. The label was absent in every locale, not just es, so this is a capture gap rather than a translation gap. Casilla numbers are reused across Modelo 200 record pages, so the text cannot be chosen by searching for the number; the adjudication ledger's official_label_sha256 identifies the exact record-design cell, and matching that digest is what makes the label grounded rather than merely plausible. Add a gate asserting every pinned label ships verbatim.

## Scope

- `src/cadrumo/locales/*/modelo/schema/200.yml`
- `dev/locales/tests/test_casilla_label_matches_pinned_official_text.py`

## Changes

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

The backlog called this "the missing es label". It is not an es problem: the key
was absent from all four catalogues, and it is one of 199 M200/2024 casillas in
that state. Every one of the 3130 labelled casillas cites aeat-dr-200-2025;
156 of the 199 unlabelled ones cite aeat-dr-200-2024. A cohort was declared
from a second record design and its label capture never ran.

Choosing the text is the part that needed care. Casilla numbers are REUSED
across Modelo 200 record pages -- 00066 is "Entidad patrimonial" on one page and
an AIE/UTE deduction base on another -- so searching the design for the number
finds a cell that is real, official, correctly formatted, and possibly the wrong
box. The adjudication ledger settles it: each entry pins official_label_sha256,
the digest of the exact cell. Hashing the candidates against the pin for 00067
matched one, exactly:

  Agrup. Interes economico y UTES - B) Datos economicos - 8.- Deducciones
  generadas en el periodo impositivo - Inversiones en Canarias (Ley 20/1991) -
  Importe de la deduccion [00067]

en, ca and hu are translated segment-by-segment in the house style the shipped
labels already use. All four resolve; the runtime localization gate reports zero
failures naming this casilla, down from four.

The new gate makes the grounding mechanical rather than a claim in a comment:
every casilla whose label is pinned must ship that pinned text verbatim. Its
teeth are the reason it exists. The injected defect was not nonsense -- it was
"6.- Deduc. evitar doble imposicion: Base de la deduccion [00067]", the label
the casilla's OWN declared section implies, in the right style, taken from a
real line of the same official document. It reads correctly. The gate rejected
it on the digest. Restored by copy; the gate passes on one covered casilla,
which is every casilla that has a pin today.

## Notes

A REAL DEFECT FOUND, NOT FIXED, because fixing it is a filing-grade registry
decision rather than a locale one. c00067.toml declares
section = ['agrupacion_interes_economico_y_utes_datos_economicos',
'6_deduc_evitar_doble_imposicion_base_de_la_deduc'] and a matching
semantic_role, and the adjudication entry carries the same two fields. Its own
cited layout authority disagrees: aeat-dr-200-2024 places 00067 in section 8,
"Inversiones en Canarias (Ley 20/1991) - Importe de la deduccion", and assigns
the section-6 "Deduc. evitar doble imposicion: Base de la deduccion" rows to
00021, 00035, 00043, 00049, 00999 and 01138. The pinned digest agrees with the
design, not with the section field, so the label is safe; the section and
semantic_role are what need adjudicating. Anyone deriving a label from those
fields instead of the pin would write the wrong box's text and it would look
right.

SCOPE OF WHAT REMAINS, measured rather than estimated: 198 casillas still carry
no label. 116 more have a pinned digest that matches a shipped record-design
cell and are mechanically derivable the same way. 79 have no adjudication entry
at all. 3 carry a pin that matches no cell in the shipped design. The 79 and the
3 need adjudication before a label can be grounded; only the 116 are ready.

