"""The typed channel reaches the formatter with the value's Python type intact.

:func:`~application.filing._export_xml_dictionary._format_xml_dictionary_value`
decides a row's rendering from the *Python type* of the value it is handed: a
``bool`` becomes ``SI``/``NO`` on an ``S_N`` row and ``1``/``0`` on every other,
a :class:`~datetime.date` becomes ``d/m/yyyy``. Anything else is written through
as text. So a value that arrives already flattened to a string renders as that
string -- ``"true"`` where AEAT's dictionary requires ``SI`` -- and nothing on
the export path detects it, because the artefact is never schema-validated
before it reaches AEAT.

The date rows are the exception, and only since the text they accept came to be
checked against AEAT's ``tipo_Fecha`` pattern: a flattened date is refused there
rather than written. That narrows what a flattened channel can silently ship; it
does not remove the need for the channel to stay typed, which is what the rest
of this module gates.

The declaration header mapping is ``dict[str, str]`` by contract, which is why
the identity fields it carries cannot be the route for a typed one. This module
gates the separate channel that can: that a ``bool`` and a ``date`` survive the
whole render, and -- through
:func:`test_a_flattened_channel_writes_the_wrong_tokens` -- that the gate would
notice if they stopped. Without that mutation proof the assertions below would
still pass if the channel were flattened tomorrow, because the ``X`` string rows
that make up most of the identity block are unaffected either way.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from xml.etree import ElementTree

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ....domain.calculations.registry import xml_dictionary_entries
from ....domain.filing import FilingExportValidationError
from .._export_xml_dictionary import render_xml_dictionary_layout
from ..runtime import RegistrySchemaAccessor
from ._export_support import _schema_provider
from .test_export import _approved_modelo_100_xml_dictionary_draft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Real Modelo 100 2024 rows, one per type branch the formatter discriminates.
# ``PH18`` is an XML attribute rather than an element, so it also exercises the
# attribute write path; the other two are elements.
_SINO_FIELD = "PH18"
_LOGICAL_FIELD = "RESIDENTEUE"
_DATE_FIELD = "DPFNAC_D"

_SINO_PATH = "/Declaracion/DatosIdentificativos/Hijos/@PH18"
_LOGICAL_PATH = "/Declaracion/DatosIdentificativos/Conyuge/RESIDENTEUE"
_DATE_PATH = "/Declaracion/DatosIdentificativos/Declarante/DPFNAC_D"

_BIRTH_DATE = date(1980, 1, 2)


def _provider_declaring_aux() -> RegistrySchemaAccessor:
    """Return an M100 provider whose layout declares the mandatory ``Aux`` block.

    The shipped Modelo 100 layouts leave ``aux_version`` undeclared -- AEAT
    publishes no authoritative value for the declaration's mandatory
    ``Aux/VERSION`` element anywhere in the bundled corpus -- so the export write
    door refuses them, and no production M100 artefact can be written today. The
    substitution here is the same one every other XML-dictionary test in this
    package makes, lifted onto the subview so the layout the renderer selects is
    the declared one.
    """
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    subview = provider.get_subview("100")
    declared = subview.export_layouts[0].model_copy(update={"aux_version": "1.00"})
    return dataclasses.replace(
        provider,
        subviews={**provider.subviews, "100": dataclasses.replace(subview, export_layouts=(declared,))},
    )


def _render(dictionary_values: dict[str, object]) -> ElementTree.Element[str]:
    provider = _provider_declaring_aux()
    payload = render_xml_dictionary_layout(
        provider.get_subview("100").export_layouts[0],
        draft=_approved_modelo_100_xml_dictionary_draft(),
        headers={"surnames": "SURNAME BLANK", "name": "STATE"},
        dictionary_values=dictionary_values,
        schema_provider=provider,
    )
    root = DefusedElementTree.fromstring(payload)
    assert root is not None
    return root


def _text_at(root: ElementTree.Element[str], absolute_path: str) -> str | None:
    """Return the text or attribute value written at ``absolute_path``, if any."""
    parts = [part for part in absolute_path.strip("/").split("/") if part]
    current: ElementTree.Element[str] | None = root
    for index, part in enumerate(parts):
        if index == 0 and part == root.tag:
            continue
        if part.startswith("@"):
            return None if current is None else current.get(part[1:])
        if current is None:
            return None
        current = next((child for child in current if child.tag == part), None)
    return None if current is None else current.text


def test_the_dictionary_still_declares_the_types_these_assertions_depend_on() -> None:
    """Anti-rot: the three rows below must still carry the types the gate assumes.

    Every assertion in this module is about how one declared type renders. If
    AEAT re-typed one of these rows -- or the registry's reading of the
    dictionary changed -- the assertions would keep passing while testing
    something else, so the declared types are pinned against the bundled
    dictionary rather than assumed.
    """
    provider = _provider_declaring_aux()
    layout = provider.get_subview("100").export_layouts[0]
    declared = {
        entry.field_id: entry.data_type
        for entry in xml_dictionary_entries(layout, source_root=provider.source_root, sources=provider.sources)
        if entry.field_id in {_SINO_FIELD, _LOGICAL_FIELD, _DATE_FIELD}
    }

    assert declared == {_SINO_FIELD: "S_N", _LOGICAL_FIELD: "LGC", _DATE_FIELD: "FEC"}


@pytest.mark.parametrize(
    ("marked", "expected_sino", "expected_logical"),
    [(True, "SI", "1"), (False, "NO", "0")],
)
def test_a_boolean_reaches_the_formatter_as_a_boolean(
    *,
    marked: bool,
    expected_sino: str,
    expected_logical: str,
) -> None:
    """Both boolean spellings AEAT declares are produced from one ``bool``.

    The two rows differ only in declared type, so a channel that preserved the
    type would render them differently and a channel that flattened it could
    not. ``False`` is asserted alongside ``True`` because a resolver testing the
    value for truth rather than for presence would drop it silently, and a
    dropped ``NO`` reads at AEAT as an unanswered question rather than a
    negative answer.
    """
    root = _render({_SINO_FIELD: marked, _LOGICAL_FIELD: marked})

    assert _text_at(root, _SINO_PATH) == expected_sino
    assert _text_at(root, _LOGICAL_PATH) == expected_logical


def test_a_date_reaches_the_formatter_as_a_date() -> None:
    """A ``date`` renders in AEAT's unpadded ``d/m/yyyy`` form."""
    root = _render({_DATE_FIELD: _BIRTH_DATE})

    assert _text_at(root, _DATE_PATH) == "2/1/1980"


def test_a_flattened_channel_writes_the_wrong_tokens() -> None:
    """Mutation proof: stringifying the channel breaks every assertion above.

    The strings used here are the ones the canonical profile-fact projection
    produces -- lowercase ``true``/``false`` for booleans, ISO for dates -- so
    this is the exact failure a resolver built on that projection would ship,
    not a synthetic corruption.

    The two failures now surface differently, which is the point of the split
    below. A flattened boolean still RENDERS, as a token neither declared type
    accepts, and nothing downstream questions it. A flattened date is REFUSED at
    the row, because the date rows validate text against AEAT's own ``tipo_Fecha``
    pattern. Both prove the channel must stay typed; only the second one tells
    the operator so.
    """
    flattened = _render({_SINO_FIELD: "true", _LOGICAL_FIELD: "true"})

    assert _text_at(flattened, _SINO_PATH) == "true"
    assert _text_at(flattened, _LOGICAL_PATH) == "true"

    typed = _render({_SINO_FIELD: True, _LOGICAL_FIELD: True})
    for path in (_SINO_PATH, _LOGICAL_PATH):
        assert _text_at(flattened, path) != _text_at(typed, path)

    with pytest.raises(FilingExportValidationError, match="not in the form AEAT accepts"):
        _render({_DATE_FIELD: _BIRTH_DATE.isoformat()})
    assert _text_at(_render({_DATE_FIELD: _BIRTH_DATE}), _DATE_PATH) == "2/1/1980"


def test_the_renderer_writes_no_identity_field_it_is_not_given() -> None:
    """The two hardcoded identity escapes are gone, not merely bypassed.

    The renderer used to answer ``DPNIF_D`` from the draft and ``DP_APENOM_D``
    from the header name parts by field id, which is the one thing a renderer
    must not know. With no channel supplied neither row can be written, so a
    reintroduced escape fails here rather than being masked by the export
    service that now supplies both through the channel.
    """
    root = _render({})

    assert _text_at(root, "/Declaracion/DatosIdentificativos/Declarante/DPNIF_D") is None
    assert _text_at(root, "/Declaracion/DatosIdentificativos/Declarante/DP_APENOM_D") is None
