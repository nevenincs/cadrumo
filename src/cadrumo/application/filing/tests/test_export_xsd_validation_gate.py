"""A rendered declaration validates against AEAT's own published schema.

Every structural defect this campaign closed -- a missing mandatory attribute,
an element emitted where the schema does not declare it, a comunidad filed as a
domain token -- was found by an ad-hoc probe and, until this module, nothing
standing would have caught the next one. This is that gate: it renders a
realistically populated Modelo 100 declaration and validates it against the
bundled record-design XSD, asserting zero errors.

Two things make an XSD gate easy to get wrong, and both are guarded here.

**A clean count can mean the validator never looked.** ``xs:sequence``
validation stops at the first thing it cannot place, so a declaration missing
its identity block reports nothing about anything downstream -- zero errors for
a document that was never examined. A renderer-level call is exactly how that
happens: ``dictionary_values`` is the COMPOSER's channel, and omitting it drops
``DatosIdentificativos`` wholesale. So the fixture is composed the way the export
service composes it, and :func:`test_the_declaration_reaches_every_block_under_test`
asserts the blocks exist before any count is believed.

**An oracle that cannot fail proves nothing.**
:func:`test_the_schema_rejects_a_declaration_missing_a_mandatory_attribute`
removes a required attribute from the very document the gate passes and asserts
the schema reports it, so "zero errors" is known to mean the validator ran,
compiled, and was looking at this document.

Two blanks are deliberately NOT treated as exporter defects, because they are
input gaps tracked elsewhere and a gate that confused them for regressions would
be turned off within a week. ``BaseLiquidableRes`` is ``minOccurs="1"`` and only
renders when a base-liquidable casilla carries a value, and ``@titular`` renders
only from a titular casilla. The fixture populates both, so what remains under
test is the exporter's structure rather than the fixture's thinness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from defusedxml import ElementTree as DefusedElementTree
from lxml import etree

from ....domain.calculations.registry.tests.record_design_xsd_support import (
    compile_record_design_schema,
)
from ....domain.filing import ModeloValue, ModeloValueKind
from ....domain.user_profile import load_user_profile_schema
from ...modelo import compose_legal_full_name, resolve_profile_export_values
from .._export_xml_dictionary import _xml_dictionary_xsd_source, render_xml_dictionary_layout
from .test_export import _approved_modelo_100_xml_dictionary_draft, _schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILING_YEAR = 2024
_HEADERS = {"surnames": "GARCIA LOPEZ", "name": "MARIA"}

# AEAT publishes no value for the Aux VERSION field anywhere in the bundled
# corpus, so the export refuses rather than inventing one and no declaration
# renders without a declared value. The gate supplies one to get past that door;
# it is testing the body, not the refusal, which test_export_aux_declaration owns.
_AUX_VERSION = "1.00"


@dataclass(frozen=True)
class _Fact:
    path: str
    value: object


@dataclass(frozen=True)
class _Record:
    facts: tuple[_Fact, ...]


# A single common-regime filer. Every value is a real member of the closed set
# its profile field declares, so the resolver exercises the same conversions a
# live profile would rather than a shape invented for the test.
_PROFILE_FACTS = (
    _Fact("identity.tax_id", "12345678Z"),
    _Fact("renta_taxpayer.birth_date", date(1980, 3, 15)),
    _Fact("renta_taxpayer.sex", "M"),
    _Fact("renta_taxpayer.marital_status", "1"),
    _Fact("filing_export.declaration_type", "1"),
    _Fact("tax_residence.ccaa", "andalucia"),
)

# Casillas whose absence is an INPUT gap rather than an exporter defect, listed
# with what each one makes render. Populating them is what keeps a failure of
# this gate attributable to the exporter.
_INPUT_CASILLAS = (
    ("0001", "2"),  # a titular casilla -> TomaDatosAmpliada/@titular
    ("0435", "20000.00"),  # base imponible general -> BaseLiquidableRes
    ("0500", "18000.00"),  # base liquidable general
    ("0505", "18000.00"),  # base liquidable general sometida a gravamen
)

_REQUIRED_BLOCKS = (
    "./Aux",
    "./DatosIdentificativos/Declarante",
    "./DatosEconomicos/TomaDatosAmpliada",
    "./DatosEconomicos/Resultados/BaseLiquidableRes",
)


def _rendered_declaration_bytes() -> bytes:
    """Render a populated declaration through the composer's own value channel."""
    provider = _schema_provider(filing_year=_FILING_YEAR, period="0A", modelos=("100",))
    subview = provider.get_subview("100")
    layout = subview.export_layouts[0].model_copy(update={"aux_version": _AUX_VERSION})

    draft = _approved_modelo_100_xml_dictionary_draft()
    draft = draft.model_copy(
        update={
            "values": (
                *draft.values,
                *(
                    ModeloValue(
                        casilla_id=casilla_id,
                        value=Decimal(amount),
                        kind=ModeloValueKind.LITERAL,
                        source="export schema gate",
                    )
                    for casilla_id, amount in _INPUT_CASILLAS
                ),
            ),
        },
    )

    # The same two-step the work-unit export service performs: registry-declared
    # profile bindings first, then the declarante's own identity from the
    # APPROVED DRAFT so it cannot disagree with the figures it was approved for.
    values: dict[str, object] = dict(
        resolve_profile_export_values(
            subview.profile_export_bindings,
            bucket_id="export-schema-gate",
            profile_record=_Record(facts=_PROFILE_FACTS),
            schema=load_user_profile_schema(),
        ),
    )
    values["DPNIF_D"] = draft.profile_tax_id
    values["DP_APENOM_D"] = compose_legal_full_name(
        surnames=_HEADERS["surnames"],
        name=_HEADERS["name"],
    )

    return render_xml_dictionary_layout(
        layout,
        draft=draft,
        headers=dict(_HEADERS),
        dictionary_values=values,
        schema_provider=provider,
    )


def _compiled_schema() -> etree.XMLSchema:
    """Compile the same XSD the layout names, through the shared repair oracle."""
    provider = _schema_provider(filing_year=_FILING_YEAR, period="0A", modelos=("100",))
    layout = provider.get_subview("100").export_layouts[0]
    source = _xml_dictionary_xsd_source(layout, provider.sources)
    assert provider.source_root is not None
    return compile_record_design_schema(Path(provider.source_root) / Path(source.corpus_path))


def test_the_declaration_reaches_every_block_under_test() -> None:
    """The document was actually built, so a clean validation means something.

    Sequence validation stops at the first unplaceable element, so a declaration
    that never rendered its identity block validates "clean" for everything after
    it. This runs first and fails loudly rather than letting the gate below pass
    vacuously.
    """
    root = DefusedElementTree.fromstring(_rendered_declaration_bytes())

    missing = [path for path in _REQUIRED_BLOCKS if root.find(path) is None]

    assert missing == [], f"the fixture never rendered {missing}; any error count below is vacuous"


def test_a_populated_declaration_validates_against_the_official_schema() -> None:
    """The gate: AEAT's own schema accepts what this exporter writes."""
    schema = _compiled_schema()
    document = etree.fromstring(_rendered_declaration_bytes())

    schema.validate(document)
    errors = [f"line {entry.line}: {entry.message}" for entry in schema.error_log]

    assert errors == [], "the exported declaration no longer satisfies AEAT's schema:\n" + "\n".join(errors)


def test_the_schema_rejects_a_declaration_missing_a_mandatory_attribute() -> None:
    """The oracle discriminates, so the assertion above is not vacuous.

    Removes ``@nif`` -- one of the attributes this campaign added -- from the
    document the gate just accepted, and requires the schema to say so. If this
    ever passes, the validator is not looking at this document and the gate above
    proves nothing.
    """
    schema = _compiled_schema()
    document = etree.fromstring(_rendered_declaration_bytes())

    block = document.find("./DatosEconomicos/TomaDatosAmpliada")
    assert block is not None and "nif" in block.attrib
    del block.attrib["nif"]

    assert not schema.validate(document)
    assert any("nif" in entry.message for entry in schema.error_log)
