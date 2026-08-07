"""The Modelo 232 coded fields resolve to ONE declaration of each code set.

Modelo 232 declares an operación vinculada twice in this codebase, and both
declarations are load-bearing: :class:`~domain.modelos.Modelo232VinculadaRow`
carries the operator's ``--row vinculada`` input, and
``RelatedPartyOperationObservation`` carries what the registry's
``related_party_operation`` binding family resolves. They are declared
counterparts — the row model's own docstring asserts the field-by-field parity —
so a code set spelled separately on each side is free to drift on one.

It had drifted. The two coded fields were bare strings on the observation and
carried a fabricated catalogue on the row: tipo de vinculación enumerated as
``"1"``-``"16"`` where AEAT's Tabla A is ``A``-``H``, método de valoración as
the OECD abbreviations where Tabla B is ``1A``-``1E``, and tipo de operación up
to ``"20"`` where Orden HFP/816/2017 art. 3.1.f enumerates eleven claves. Half
of those codes are wider than the fixed-width field that must hold them.

This gate fixes the shape of the fix rather than the values: both models must
resolve to the same ``core`` enums, and neither may re-declare a code set
locally. The values themselves are grounded by the refusal tests beside each
model.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import get_type_hints

import pytest

from ..core import MetodoValoracion, TipoOperacionVinculada, TipoVinculacion
from ..domain.calculations.registry._detail_record_bindings import RelatedPartyOperationObservation
from ..domain.modelos import Modelo232VinculadaRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The counterpart field pairs, as the row model's parity docstring declares
#: them, with the code set both sides must resolve to.
_COUNTERPART_FIELDS = (
    ("tipo_operacion", "operation_kind_code", TipoOperacionVinculada),
    ("metodo", "transfer_pricing_method_code", MetodoValoracion),
)

_SRC_ROOT = Path(__file__).resolve().parents[1]


def test_counterpart_coded_fields_resolve_to_the_same_core_code_set() -> None:
    """The CLI row and the registry observation must be typed by one enum each."""
    row_hints = get_type_hints(Modelo232VinculadaRow)
    observation_hints = get_type_hints(RelatedPartyOperationObservation)
    for row_field, observation_field, code_set in _COUNTERPART_FIELDS:
        assert row_hints[row_field] is code_set, row_field
        assert observation_hints[observation_field] is code_set, observation_field


def test_the_row_model_types_every_coded_field_from_core() -> None:
    """Tipo de vinculación has no observation counterpart but the same home."""
    assert get_type_hints(Modelo232VinculadaRow)["tipo_vinculacion"] is TipoVinculacion


def test_each_code_set_is_declared_exactly_once_in_the_tree() -> None:
    """No module may re-spell a DR23200 table that ``core`` already declares.

    Keyed on the code VALUES rather than the enum name, because a second
    declaration would arrive under a different name — that is what makes it a
    duplicate rather than an import.
    """
    for code_set in (TipoVinculacion, TipoOperacionVinculada, MetodoValoracion):
        codes = frozenset(str(member) for member in code_set if str(member))
        declaring = _modules_declaring_the_literal_set(codes)
        assert declaring == {"core/_modelo_232_codigos.py"}, (
            f"{code_set.__name__} is declared in {sorted(declaring)}; "
            f"the single home is core/_modelo_232_codigos.py"
        )


def _modules_declaring_the_literal_set(codes: frozenset[str]) -> set[str]:
    """Return modules whose source enumerates ``codes`` as a literal collection.

    Reads the AST rather than the text so a docstring listing the codes for
    documentation — which the row model legitimately does — is not counted as a
    declaration.
    """
    declaring: set[str] = set()
    for path in _SRC_ROOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - not source we own
            continue
        if any(_node_enumerates(node, codes) for node in ast.walk(tree)):
            declaring.add(path.relative_to(_SRC_ROOT).as_posix())
    return declaring


def _node_enumerates(node: ast.AST, codes: frozenset[str]) -> bool:
    """Return whether ``node`` is a literal collection or enum body covering ``codes``."""
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        literals = {e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        return codes <= literals
    if isinstance(node, ast.Subscript):  # Literal["A", "B", ...]
        sliced = node.slice
        elts = sliced.elts if isinstance(sliced, ast.Tuple) else []
        literals = {e.value for e in elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        return codes <= literals
    if isinstance(node, ast.ClassDef):
        literals = {
            stmt.value.value
            for stmt in node.body
            if isinstance(stmt, ast.Assign | ast.AnnAssign)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        }
        return codes <= literals
    return False
