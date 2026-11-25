"""A ``--descendiente`` refusal is rendered with the copy for its own cause.

The ``invalid_flag`` copy tells the operator that every row must declare
``NACIMIENTO``. Rendered for any other refusal it names a cause that did not
happen, so it is reserved for refusals the parser attributes to ``NACIMIENTO``;
everything else, including a refusal that names no key, takes ``invalid_row``.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.descendant_relacion import DescendantRelacion
from .....core.errors.hierarchy import ProfileAnswerTypeError
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.contribuyente.descendant import DescendantInfo
from .....domain.contribuyente.descendant_facts import parse_descendiente_flag
from .....tests.env_scope import output_language_scope
from ..descendiente import ambiguous_relacion_indices, ambiguous_relacion_notice, descendiente_refusal_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_INVALID_ROW = "cli.config.profile.descendiente.invalid_row"
_INVALID_FLAG = "cli.config.profile.descendiente.invalid_flag"


def test_an_unattributed_refusal_names_no_field() -> None:
    assert descendiente_refusal_key(ProfileAnswerTypeError("x")) == (_INVALID_ROW, {})


def test_a_birth_date_refusal_keeps_the_nacimiento_copy() -> None:
    error = ProfileAnswerTypeError("x", context={"key": "NACIMIENTO"})

    assert descendiente_refusal_key(error) == (_INVALID_FLAG, {"key": "NACIMIENTO"})


def test_another_attributed_refusal_names_its_own_key() -> None:
    error = ProfileAnswerTypeError("x", context={"key": "DISCAPACIDAD"})

    assert descendiente_refusal_key(error) == (_INVALID_ROW, {"key": "DISCAPACIDAD"})


def test_the_guarderia_spend_conflict_keeps_its_dedicated_copy() -> None:
    """Driven through the real parser so the mapper reads the context it actually raises."""
    with bundled_indexed_authority().operation(), pytest.raises(ProfileAnswerTypeError) as raised:
        parse_descendiente_flag("NACIMIENTO=2021-04-15,GASTOS_GUARDERIA=2400,GASTOS_GUARDERIA_MENSUAL=5-7:200")

    assert descendiente_refusal_key(raised.value) == (
        "cli.config.profile.descendiente.guarderia_spend_shapes_conflict",
        {"key": "GASTOS_GUARDERIA_MENSUAL"},
    )


@pytest.mark.parametrize(
    "locale,descendant_word,blood_word,custody_word",
    [
        ("en", "grandchild", "blood", "judicial"),
        ("es", "nieto", "consanguinidad", "judicial"),
        ("ca", "net", "consanguinitat", "judicial"),
        ("hu", "unokától", "vér szerinti", "bíróság"),
    ],
)
def test_relationship_advisory_matches_the_actual_ambiguous_axis(
    locale: str, descendant_word: str, blood_word: str, custody_word: str
) -> None:
    with bundled_indexed_authority().operation():
        ambiguous = DescendantInfo(birth_date=date(filing_year_envelope().horizon, 1, 1), meses_madre_trabajo=(1,))
        judicial = DescendantInfo(
            birth_date=date(filing_year_envelope().horizon, 1, 1),
            meses_madre_trabajo=(1,),
            relacion=DescendantRelacion.from_registry("guarda_y_custodia_judicial"),
        )
        assert ambiguous_relacion_indices([ambiguous, judicial], index_offset=4) == (4,)

    message = tr("cli.config.profile.descendiente.ambiguous_relacion_advisory", locale=locale, indices="4")
    with output_language_scope(OutputLanguage(locale)):
        assert ambiguous_relacion_notice((4,)).message == message
    assert "4" in message and descendant_word in message and blood_word in message
    assert "81.1" in message and custody_word not in message
    assert "%{indices}" not in message
