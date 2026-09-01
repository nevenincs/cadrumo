"""The Modelo 232 coded fields resolve to ONE declaration of each code set.

Modelo 232 declares an operación vinculada twice in this codebase, and both
declarations are load-bearing: :class:`~Modelo232VinculadaRow`
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

from ..core.directory_scan import scan_directory
from ..core.modelo_232_codigos import MetodoValoracion, TipoOperacionVinculada, TipoVinculacion
from ..domain.calculations.registry.detail_record_bindings import RelatedPartyOperationObservation
from ..domain.modelos.row_models import Modelo232VinculadaRow

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
        assert declaring == {"core/modelo_232_codigos.py"}, (
            f"{code_set.__name__} is declared in {sorted(declaring)}; the single home is core/modelo_232_codigos.py"
        )


def _detect_in(sources: dict[str, str], codes: frozenset[str], tmp_path: Path) -> set[str]:
    """Run the real detector over a synthetic tree of ``{filename: source}``."""
    for name, text in sources.items():
        (tmp_path / name).write_text(text, encoding="utf-8", newline="\n")
    return _modules_declaring_the_literal_set(codes, root=tmp_path)


_VINCULACION_CODES = frozenset(str(member) for member in TipoVinculacion if str(member))


def test_a_second_declaration_of_the_vinculada_set_is_still_detected(tmp_path: Path) -> None:
    """The gate must keep catching what it exists to catch.

    Re-keying a detector to remove a false positive is only half a change: the
    half that matters is that the true positive still fires. Both real shapes
    are planted — an enum class re-spelling the table under a different name,
    and a ``Literal`` alias — because a duplicate arrives under a different name
    or it would be an import.
    """
    detected = _detect_in(
        {
            "enum_copy.py": (
                "from enum import StrEnum\n\n\n"
                "class VinculacionKind(StrEnum):\n"
                + "".join(f'    K{code} = "{code}"\n' for code in sorted(_VINCULACION_CODES))
            ),
            "literal_copy.py": (
                "from typing import Literal\n\n"
                "_CODES = Literal[" + ", ".join(f'"{code}"' for code in sorted(_VINCULACION_CODES)) + "]\n"
            ),
        },
        _VINCULACION_CODES,
        tmp_path,
    )

    assert detected == {"enum_copy.py", "literal_copy.py"}


def test_a_wider_catalogue_drawn_from_the_same_alphabet_is_not_a_duplicate(tmp_path: Path) -> None:
    """The false positive this gate shipped with, planted so it cannot return.

    ``RetencionClave`` is the Modelo 190/193 clave de percepción ``A``-``L``
    (Orden EHA/3127/2009) and the Modelo 347 clave de operación runs ``A``-``I``
    (Orden EHA/3012/2008). Both are independently grounded AEAT catalogues that
    merely share an alphabet with the vinculación table, and under containment
    both were reported as re-declaring it. Deleting either to satisfy the gate
    would have removed correctly-grounded law.
    """
    wider = sorted(_VINCULACION_CODES | {"I", "J", "K", "L"})
    detected = _detect_in(
        {
            "retencion_clave.py": (
                "from enum import StrEnum\n\n\n"
                "class RetencionClave(StrEnum):\n" + "".join(f'    {code} = "{code}"\n' for code in wider)
            ),
        },
        _VINCULACION_CODES,
        tmp_path,
    )

    assert detected == set()


def test_the_not_declared_sentinel_does_not_hide_the_canonical_home(tmp_path: Path) -> None:
    """The canonical enum carries a ``""`` member the key does not.

    Comparing raw literal sets would make the ONE module that should match the
    one that does not, emptying the detector and turning the assertion into a
    vacuous pass. This pins the asymmetry rather than leaving it to a comment.
    """
    detected = _detect_in(
        {
            "canonical.py": (
                "from enum import StrEnum\n\n\n"
                "class TipoVinculacion(StrEnum):\n"
                '    NO_DECLARADO = ""\n' + "".join(f'    L{code} = "{code}"\n' for code in sorted(_VINCULACION_CODES))
            ),
        },
        _VINCULACION_CODES,
        tmp_path,
    )

    assert detected == {"canonical.py"}


def _modules_declaring_the_literal_set(codes: frozenset[str], *, root: Path | None = None) -> set[str]:
    """Return modules whose source enumerates ``codes`` as a literal collection.

    Reads the AST rather than the text so a docstring listing the codes for
    documentation — which the row model legitimately does — is not counted as a
    declaration.

    *root* exists so the detector can be aimed at a synthetic tree in the proofs
    below. A detector that can only be run against the real source can be shown
    to be quiet, never to be *right*, and quiet is exactly what a mis-keyed
    detector looks like.
    """
    declaring: set[str] = set()
    source_root = root if root is not None else _SRC_ROOT
    for path in scan_directory(source_root, pattern="*.py", recursive=True):
        if "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - not source we own
            continue
        if any(_node_enumerates(node, codes) for node in ast.walk(tree)):
            declaring.add(path.relative_to(source_root).as_posix())
    return declaring


def _node_enumerates(node: ast.AST, codes: frozenset[str]) -> bool:
    """Return whether ``node`` enumerates EXACTLY ``codes`` as a literal collection.

    Equality, not containment, and the distinction is the whole discriminating
    power of this gate. A duplicate declaration re-spells THE SAME table; a
    module enumerating a superset is declaring a DIFFERENT, larger one.

    Containment made the gate unable to tell those apart, and single-letter AEAT
    claves are where that bites hardest, because a bare ``A``-``H`` key is
    satisfied by any wider catalogue drawn from the same alphabet. It reported
    :class:`~core.RetencionClave` (Modelo 190/193 clave de percepción ``A``-``L``,
    Orden EHA/3127/2009) and the Modelo 347 ``clave de operación`` ``A``-``I``
    (Orden EHA/3012/2008) as re-declarations of the vinculación table, and the
    two-digit operation key matched the twenty-one-member standard period codes.
    Six modules across the three code sets, none of them a duplicate — and the
    obvious way to silence that red is to delete a correctly-grounded catalogue.

    Falsy literals are dropped from the compared set because the key itself
    drops them: the canonical enums carry a ``""`` not-declared sentinel that is
    not one of the AEAT codes, so leaving it in would make the true home the one
    module that failed to match.
    """
    literals = _string_literals_enumerated_by(node)
    if literals is None:
        return False
    return codes == {literal for literal in literals if literal}


def _string_literals_enumerated_by(node: ast.AST) -> set[str] | None:
    """The string literals this node enumerates, or ``None`` if it enumerates none.

    ``None`` rather than an empty set, so "this node is not a collection" stays
    distinguishable from "this node is an empty collection" at the comparison
    above.
    """
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        return {e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    if isinstance(node, ast.Subscript):  # Literal["A", "B", ...]
        sliced = node.slice
        elts = sliced.elts if isinstance(sliced, ast.Tuple) else []
        return {e.value for e in elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    if isinstance(node, ast.ClassDef):
        return {
            stmt.value.value
            for stmt in node.body
            if isinstance(stmt, ast.Assign | ast.AnnAssign)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        }
    return None
