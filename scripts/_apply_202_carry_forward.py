"""One-shot transformer adding prior-period chaining to modelo 202.

Mod. 40.3 LIS casilla 30 "Pagos fraccionados de periodos anteriores en
Territorio Comun" is the cumulative sum of casilla 34 ("Cantidad a
ingresar") across all prior pago-fraccionado periods in the ejercicio.

Each revision gets:
* casilla 30 converted manual -> bound (non_negative constraint)
* a previous_filing binding source_modelo=202 output=casilla 34
* two relations: 2P picks up sum of (1P) casilla 34, 3P picks up sum
  of (1P, 2P) casilla 34
* a dependency_classification 202 -> 202 (factual_evidence)
* construct extended with the new binding + relations + classification
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "registry" / "aeat" / "modelos" / "202.toml"

REVISIONS = (
    ("2025-y-siguientes", "modelo-202-foundation"),
    ("2023-2024", "modelo-202-2023-2024-foundation"),
    ("2019-2022", "modelo-202-2019-2022-foundation"),
)

LEGAL = '["ley-27-2014:art-40", "ley-27-2014:art-29", "ley-27-2014:art-30", "ley-27-2014:art-105"]'


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    for rev, construct_id in REVISIONS:
        text = _convert_casilla_30(text, rev)
        text = _insert_carry_forward_block(text, rev, construct_id)
        text = _extend_construct(text, rev, construct_id)
    TARGET.write_text(text, encoding="utf-8")
    print(f"Updated {TARGET}")


def _convert_casilla_30(text: str, rev: str) -> str:
    pattern = re.compile(
        r'(\[\[revisions\."' + re.escape(rev) + r'"\.casillas\]\]\n'
        r'id = "30"\n'
        r'number = "30"\n'
        r'label = "Mod\. 40\.3 LIS — Pagos fraccionados de periodos anteriores en Territorio Comun"\n'
        r'section = \[[^\]]*\]\n'
        r'data_type = "money"\n'
        r'required = false\n)'
        r'input_kind = "manual"\n'
    )
    replacement = (
        r'\1'
        'input_kind = "bound"\n'
        f'binding = "modelo-202-{rev}-pagos-fraccionados-anteriores"\n'
        'constraints = { sign = "non_negative", legal_refs = ["ley-27-2014:art-40"], '
        'source_refs = ["aeat-modelo-202-instructions"] }\n'
    )
    new_text, count = pattern.subn(replacement, text)
    if count != 1:
        raise RuntimeError(f"casilla 30 conversion in revision {rev!r} matched {count} times (expected 1)")
    return new_text


def _insert_carry_forward_block(text: str, rev: str, construct_id: str) -> str:
    construct_marker = f'[[revisions."{rev}".constructs]]'
    insertion = _carry_forward_block(rev, construct_id)
    if construct_marker not in text:
        raise RuntimeError(f"construct marker missing for revision {rev!r}")
    block_head = f'[[revisions."{rev}".bindings]]\nid = "modelo-202-{rev}-pagos-fraccionados-anteriores"'
    if block_head in text:
        return text
    return text.replace(construct_marker, insertion + construct_marker, 1)


def _carry_forward_block(rev: str, construct_id: str) -> str:
    return f"""# -----------------------------------------------------------------------------
# Prior-period cumulative pagos-fraccionados carry-forward (LIS art. 40)
# revision {rev}. Casilla 30 picks up the sum of casilla 34
# (Cantidad a ingresar) across all prior pago periods in the ejercicio.
# -----------------------------------------------------------------------------

[[revisions."{rev}".bindings]]
id = "modelo-202-{rev}-pagos-fraccionados-anteriores"
source = "previous_filing"
selector = {{ source_modelo = "202", source_output = "34" }}
aggregation = {{ op = "sum" }}
legal_refs = {LEGAL}
source_refs = ["aeat-modelo-202-instructions"]

[[revisions."{rev}".bindings.source_citations]]
source_ref = "aeat-modelo-202-instructions"
required_text = ["pagos fraccionados"]

[[revisions."{rev}".relations]]
id = "modelo-202-{rev}-rel-self-pagos-2p"
kind = "previous_period"
dependency_role = "direct_calculation"
source_modelo = "202"
source_revision_selector = {{ filing_year_delta = 0 }}
source_output = "34"
target_binding = "modelo-202-{rev}-pagos-fraccionados-anteriores"
period_alignment = {{ mode = "prior_pagos_cumulative" }}
source_periods = ["1P"]
target_periods = ["2P"]
aggregation = {{ op = "sum" }}
legal_refs = {LEGAL}
source_refs = ["aeat-modelo-202-instructions"]

[[revisions."{rev}".relations]]
id = "modelo-202-{rev}-rel-self-pagos-3p"
kind = "previous_period"
dependency_role = "direct_calculation"
source_modelo = "202"
source_revision_selector = {{ filing_year_delta = 0 }}
source_output = "34"
target_binding = "modelo-202-{rev}-pagos-fraccionados-anteriores"
period_alignment = {{ mode = "prior_pagos_cumulative" }}
source_periods = ["1P", "2P"]
target_periods = ["3P"]
aggregation = {{ op = "sum" }}
legal_refs = {LEGAL}
source_refs = ["aeat-modelo-202-instructions"]

[[revisions."{rev}".dependency_classifications]]
id = "modelo-202-{rev}-dep-self-prior-pagos"
source_modelo = "202"
treatment = "factual_evidence"
target_constructs = ["{construct_id}"]
relation_refs = [
    "modelo-202-{rev}-rel-self-pagos-2p",
    "modelo-202-{rev}-rel-self-pagos-3p",
]
legal_refs = {LEGAL}
source_refs = ["aeat-modelo-202-instructions"]

"""


def _extend_construct(text: str, rev: str, construct_id: str) -> str:
    construct_pattern = re.compile(
        r'(\[\[revisions\."' + re.escape(rev) + r'"\.constructs\]\]\n'
        r'id = "' + re.escape(construct_id) + r'"\n'
        r'[\s\S]*?\n)'
        r'(application_links = \[)'
    )
    addendum = (
        r'\1'
        f'bindings = ["modelo-202-{rev}-pagos-fraccionados-anteriores"]\n'
        f'relations = ["modelo-202-{rev}-rel-self-pagos-2p", "modelo-202-{rev}-rel-self-pagos-3p"]\n'
        f'dependency_classifications = ["modelo-202-{rev}-dep-self-prior-pagos"]\n'
        r'\2'
    )
    new_text, count = construct_pattern.subn(addendum, text, count=1)
    if count != 1:
        raise RuntimeError(f"construct extension for revision {rev!r} matched {count} times (expected 1)")
    return new_text


if __name__ == "__main__":
    main()
