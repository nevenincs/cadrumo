"""One-shot transformer that adds prior-quarter carry-forward to modelo 131.

Mirrors the modelo 130 pattern: each revision's casilla 11 (Resultados
negativos de trimestres anteriores) is converted from manual to bound,
a saldo-negativo-fin-periodo computed casilla is added, plus binding,
formula, relation, and dependency_classification.

Run once: ``uv run python scripts/_apply_131_carry_forward.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "registry" / "aeat" / "modelos" / "131.toml"

REVISIONS = ("2019-2023", "2024", "2025", "2026")


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    for rev in REVISIONS:
        text = _convert_casilla_11(text, rev)
        text = _insert_carry_forward_block(text, rev)
        text = _extend_construct(text, rev)

    TARGET.write_text(text, encoding="utf-8")
    print(f"Updated {TARGET} across revisions: {REVISIONS}")


def _convert_casilla_11(text: str, rev: str) -> str:
    pattern = re.compile(
        r'(\[\[revisions\."'
        + re.escape(rev)
        + r'"\.casillas\]\]\n'
        + r'id = "11"\n'
        + r'number = "11"\n'
        + r'label = "Resultados negativos de trimestres anteriores"\n'
        + r'section = \["total_liquidacion"\]\n'
        + r'data_type = "money"\n'
        + r'required = false\n)'
        + r'input_kind = "manual"\n'
    )
    replacement = (
        r'\1'
        + 'input_kind = "bound"\n'
        + f'binding = "modelo-131-{rev}-resultados-negativos-anteriores"\n'
        + 'constraints = { sign = "non_negative", legal_refs = ["rd-439-2007:art-110"], '
        + 'source_refs = ["aeat-modelo-131-instructions"] }\n'
    )
    new_text, count = pattern.subn(replacement, text)
    if count != 1:
        raise RuntimeError(f"casilla 11 conversion in revision {rev!r} matched {count} times (expected 1)")
    return new_text


def _insert_carry_forward_block(text: str, rev: str) -> str:
    """Insert carry-forward casilla + binding + formula + relation + classification.

    We anchor the insertion to the line right before the construct block for
    each revision so the new declarations land in the casillas/bindings/formulas/
    relations/dependency_classifications sections (TOML doesn't care about
    array-of-table ordering within the same revision).
    """

    construct_marker = f'[[revisions."{rev}".constructs]]'
    insertion = _carry_forward_block(rev)
    if construct_marker not in text:
        raise RuntimeError(f"construct marker missing for revision {rev!r}")
    if insertion.strip() in text:
        return text
    return text.replace(construct_marker, insertion + construct_marker, 1)


def _carry_forward_block(rev: str) -> str:
    return f"""# -----------------------------------------------------------------------------
# Prior-quarter negative-result carry-forward (RD 439/2007 art. 110.5)
# revision {rev}.
# -----------------------------------------------------------------------------

[[revisions."{rev}".casillas]]
id = "saldo-negativo-fin-periodo"
number = "saldo-negativo-fin-periodo"
label = "Saldo negativo trasladable a periodos posteriores (max 0, -casilla 10)"
section = ["computed_carry_forward"]
data_type = "money"
required = false
input_kind = "computed"
formula = "modelo-131-{rev}-saldo-negativo-fin-periodo"
constraints = {{ sign = "non_negative", legal_refs = ["rd-439-2007:art-110"], source_refs = ["aeat-modelo-131-instructions"] }}
legal_refs = ["rd-439-2007:art-110", "rd-439-2007:art-95"]
source_refs = ["aeat-modelo-131-instructions", "aeat-dr-131-{rev}-v101"]

[[revisions."{rev}".bindings]]
id = "modelo-131-{rev}-resultados-negativos-anteriores"
source = "previous_filing"
selector = {{ source_modelo = "131", source_output = "saldo-negativo-fin-periodo" }}
aggregation = {{ op = "copy" }}
legal_refs = ["rd-439-2007:art-110", "rd-439-2007:art-95"]
source_refs = ["aeat-modelo-131-instructions"]

[[revisions."{rev}".bindings.source_citations]]
source_ref = "aeat-modelo-131-instructions"
required_text = ["Resultados negativos"]

[[revisions."{rev}".formulas]]
id = "modelo-131-{rev}-saldo-negativo-fin-periodo"
target = "saldo-negativo-fin-periodo"
expression = {{ op = "max", args = [
    {{ literal = "0" }},
    {{ op = "negate", args = [{{ casilla = "10" }}] }},
] }}
rounding = "money-2"
legal_refs = ["rd-439-2007:art-110", "rd-439-2007:art-95"]
source_refs = ["aeat-modelo-131-instructions", "aeat-dr-131-{rev}-v101"]

[[revisions."{rev}".formulas.source_citations]]
source_ref = "aeat-modelo-131-instructions"
required_text = ["Resultados negativos"]

[[revisions."{rev}".relations]]
id = "modelo-131-{rev}-rel-self-prior-quarter-negative"
kind = "previous_period"
dependency_role = "direct_calculation"
source_modelo = "131"
source_revision_selector = {{ filing_year_delta = 0 }}
source_output = "saldo-negativo-fin-periodo"
target_binding = "modelo-131-{rev}-resultados-negativos-anteriores"
period_alignment = {{ mode = "previous_quarter" }}
source_period_offset_from_target = -1
target_periods = ["2T", "3T", "4T"]
aggregation = {{ op = "copy" }}
legal_refs = ["rd-439-2007:art-110", "rd-439-2007:art-95"]
source_refs = ["aeat-modelo-131-instructions"]

[[revisions."{rev}".dependency_classifications]]
id = "modelo-131-{rev}-dep-self-prior-quarter"
source_modelo = "131"
treatment = "factual_evidence"
target_constructs = ["modelo-131-{rev}-objective-estimation-instalment"]
relation_refs = ["modelo-131-{rev}-rel-self-prior-quarter-negative"]
legal_refs = ["rd-439-2007:art-110", "rd-439-2007:art-95"]
source_refs = ["aeat-modelo-131-instructions"]

"""


def _extend_construct(text: str, rev: str) -> str:
    """Add the new symbols + relations + dependency_classifications to the construct."""

    cas_pattern = (
        r'(\[\[revisions\."'
        + re.escape(rev)
        + r'"\.constructs\]\][\s\S]*?)casillas = \["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15"\]'
    )
    text = re.sub(
        cas_pattern,
        r'\1casillas = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "saldo-negativo-fin-periodo"]',
        text,
        count=1,
    )
    # Add the new formula id immediately after modelo-131-{rev}-resultado
    text = text.replace(
        f'    "modelo-131-{rev}-resultado",\n]',
        f'    "modelo-131-{rev}-resultado",\n    "modelo-131-{rev}-saldo-negativo-fin-periodo",\n]',
        1,
    )
    # Add bindings + relations + dependency_classifications under the construct.
    parameters_line_pattern = (
        r'(\[\[revisions\."'
        + re.escape(rev)
        + r'"\.constructs\]\][\s\S]*?)(parameters = \[[^\]]*\])\n'
    )
    addendum = (
        r'\1\2\n'
        + f'bindings = ["modelo-131-{rev}-resultados-negativos-anteriores"]\n'
        + f'relations = ["modelo-131-{rev}-rel-self-prior-quarter-negative"]\n'
        + f'dependency_classifications = ["modelo-131-{rev}-dep-self-prior-quarter"]\n'
    )
    text = re.sub(parameters_line_pattern, addendum, text, count=1)
    return text


if __name__ == "__main__":
    main()
