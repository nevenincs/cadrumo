"""The amend command gives the operator a way to state three answers, not two.

For M184, M232, M347 and M349 the per-counterpart rows ARE the declaration, and
the authority refuses an amendment that says nothing about them: a
complementaria COMPLETES the return it corrects while a sustitutiva REPLACES it
(LGT art. 122.2 para. 2), so silence would be read differently by each. The
command had no way to break that silence, so amending any of those four was
refused outright.

An argv surface can express absence naturally -- an option simply not passed --
but it cannot express "explicitly none" with the same option, because a
repeatable ``--row`` that is never repeated is indistinguishable from one the
operator never reached for. So the nil declaration gets its own flag, and
passing both is refused as a contradiction rather than resolved by a precedence
rule the operator would have to learn.

These tests drive the real resolver and read the real catalogues. The catalogue
half matters because ``tr`` does NOT raise on a missing key -- it humanises the
last dotted segment -- so an unworded option would render English-looking text
in every locale and nothing would fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
import yaml

from ....domain.modelos.row_models import Modelo347ContraparteRow
from .._modelo import _resolve_amendment_detail_rows
from .._modelo_core_command_specs import MODELO_CORE_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")
_LOCALES_ROOT = Path(__file__).resolve().parents[3] / "locales"
_AMEND_ROW_KEYS = (
    "row_help",
    "amend_no_detail_rows_help",
    "amend_rows_contradiction",
)
_ROW_SPEC = "contraparte nif=B12345674 nombre=Acme importe_Q1=1000.00 clave_operacion=B pais_codigo=ES"


def _amend_spec() -> object:
    """The live amend command declaration, found by token rather than index."""
    return next(spec for spec in MODELO_CORE_COMMAND_SPECS if spec.key == "app_modelo_work_amend")


def test_no_row_flags_at_all_says_nothing_rather_than_declaring_none() -> None:
    """The state the authority refuses for the four, and the ordinary one elsewhere.

    This is the default an operator reaches by not thinking about rows, so it
    must be the state that gets refused rather than the one that files a nil
    declaration on their behalf.
    """
    assert _resolve_amendment_detail_rows((), declared_none=False) is None


def test_the_nil_flag_declares_an_empty_set_rather_than_silence() -> None:
    """The positive statement: this period had no rows.

    Distinct from the case above by identity, not just value -- an empty tuple
    and ``None`` are the two answers the authority tells apart.
    """
    resolved = _resolve_amendment_detail_rows((), declared_none=True)

    assert resolved == ()
    assert resolved is not None


def test_a_row_spec_is_parsed_into_the_typed_domain_row() -> None:
    """The positive control: the refusals above must not be a resolver that refuses everything."""
    resolved = _resolve_amendment_detail_rows((_ROW_SPEC,), declared_none=False)

    assert resolved is not None
    assert len(resolved) == 1
    row = resolved[0]
    assert isinstance(row, Modelo347ContraparteRow)
    assert row.nif == "B12345674"


def test_several_rows_are_carried_in_the_order_given() -> None:
    """Repetition is how an operator declares more than one counterparty."""
    other = _ROW_SPEC.replace("B12345674", "B12345675").replace("Acme", "Beta")

    resolved = _resolve_amendment_detail_rows((_ROW_SPEC, other), declared_none=False)

    assert [row.nif for row in resolved or ()] == ["B12345674", "B12345675"]


def test_declaring_none_while_also_giving_rows_is_refused() -> None:
    """Two contradictory answers is not a precedence question.

    Silently letting one win would file whichever the code happened to prefer,
    and the operator would have no way to tell which.
    """
    with pytest.raises(typer.BadParameter):
        _resolve_amendment_detail_rows((_ROW_SPEC,), declared_none=True)


def test_a_malformed_row_spec_is_refused_at_the_boundary() -> None:
    """Row grammar is parsed here, so a bad spec fails before any authority runs."""
    with pytest.raises(typer.BadParameter):
        _resolve_amendment_detail_rows(("not_a_row_type nif=B12345674",), declared_none=False)


def test_the_command_declares_both_row_options() -> None:
    """An option the resolver honours but argv cannot supply is unreachable."""
    declarations = {
        declaration for option in _amend_spec().parameters for declaration in getattr(option, "declarations", ())
    }

    assert "--row" in declarations
    assert "--no-detail-rows" in declarations


def test_the_nil_declaration_is_a_flag_rather_than_a_value_option() -> None:
    """``--no-detail-rows`` takes no argument; a value would invite ``=false``.

    A flag that accepted a value would give the operator a second way to say
    "no" that this command does not read.
    """
    flag = next(
        option
        for option in _amend_spec().parameters
        if "--no-detail-rows" in getattr(option, "declarations", ())
    )

    assert flag.is_flag is True
    assert flag.name == "no_detail_rows"


@pytest.mark.parametrize("locale", _LOCALES)
def test_both_row_options_are_worded_in_this_locale(locale: str) -> None:
    """An unworded key renders a humanised token, not a translation."""
    catalogue = yaml.safe_load((_LOCALES_ROOT / locale / "cli.yml").read_text(encoding="utf-8"))
    work = catalogue["cli"]["app"]["modelo"]["work"]

    missing = [key for key in _AMEND_ROW_KEYS if not str(work.get(key, "")).strip()]

    assert not missing, f"{locale} has no wording for: {missing}"
