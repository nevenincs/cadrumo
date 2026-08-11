"""An exported boolean casilla verifies against the draft it was written from.

Both dictionary row types that carry a boolean must survive the write-then-read
cycle as the same boolean. They differ only in the tokens AEAT spells them with --
``LGC`` rows carry ``0``/``1`` and ``S_N`` rows carry ``NO``/``SI`` -- and a
spelling difference must not decide whether verification agrees.

It did. The reader returned a real boolean for one row type and the raw text for
the other, so comparing an ``S_N`` casilla against its draft put ``True`` on one
side and ``"SI"`` on the other and reported drift on a file that matched. The
verdict is asserted here rather than the parser's return value, because the verdict
is what an operator acts on and it cannot be satisfied by the reader agreeing with
itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import CasillaId, Period
from ....domain.calculations.registry import RegistrySnapshotRef
from ....domain.filing import (
    ModeloCasillaProvenance,
    ModeloDraft,
    ModeloValue,
    ModeloValueKind,
)
from ....domain.submission import ModeloDraftStatus
from .._export import DeclaracionVerifyVerdict, verify_export
from .._export_xml_dictionary import render_xml_dictionary_layout
from ..runtime import RegistrySchemaAccessor, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILING_YEAR = 2024
# 0002 sits on an ``LGC`` row (the XSD's ``tipo_logico``); 0619 sits on an ``S_N``
# row (``tipo_SINO_Exclusivo``). Both are boolean casillas, so the pair differs in
# nothing but the dictionary type -- which is what makes a divergence between them
# attributable to the type alone.
_LGC_CASILLA: CasillaId = "0002"
_SINO_CASILLA: CasillaId = "0619"


def _provider() -> RegistrySchemaAccessor:
    return build_runtime_schema_provider(
        modelos=("100",),
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, "0A"),
    )


def _write_declared_export(provider: RegistrySchemaAccessor, *, draft: ModeloDraft, output: Path) -> None:
    """Render and write through a layout that declares its ``Aux`` block.

    The shipped Modelo 100 layouts leave ``aux_version`` undeclared, because AEAT
    publishes no authoritative value for the declaration's mandatory
    ``Aux/VERSION`` element, so the export write door refuses them. The boolean
    row-type asymmetry under test here is independent of that gap; declaring the
    value through the registry's own model keeps the question answerable.
    """
    layout = provider.get_subview("100").export_layouts[0].model_copy(update={"aux_version": "1.00"})
    output.write_bytes(
        render_xml_dictionary_layout(
            layout,
            draft=draft,
            headers={"surnames": "APELLIDO UNO APELLIDO DOS", "name": "NOMBRE"},
            schema_provider=provider,
        ),
    )


def _draft(provider: RegistrySchemaAccessor, *, marker: bool) -> ModeloDraft:
    collection = provider.get_collection("100")
    period = Period.from_year_and_code(_FILING_YEAR, "0A")
    values = tuple(
        ModeloValue(
            casilla_id=casilla_id,
            value=marker,
            kind=ModeloValueKind.LITERAL,
            source="registry input",
        )
        for casilla_id in (_LGC_CASILLA, _SINO_CASILLA)
    )
    provenance = {
        casilla.casilla_id: ModeloCasillaProvenance(
            casilla_id=casilla.casilla_id,
            formula_id=casilla.formula,
            legal_refs=casilla.legal_refs,
            source_refs=casilla.source_refs,
        )
        for casilla in collection.all()
    }
    stamped = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
    return ModeloDraft(
        draft_id=f"modelo-100-boolean-row-verify-{marker}",
        modelo="100",
        period=period,
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(
            modelo="100",
            revision_id=str(_FILING_YEAR),
            modelo_year=_FILING_YEAR,
            period="0A",
        ),
        status=ModeloDraftStatus.APROBADO,
        values=values,
        binding_values=(),
        casilla_provenance=tuple(provenance[value.casilla_id] for value in values),
        findings=(),
        created_at=stamped,
        updated_at=stamped,
        schema_version=collection.schema_version,
    )


@pytest.mark.parametrize("marker", [True, False])
def test_both_boolean_row_types_verify_against_the_draft(tmp_path: Path, marker: bool) -> None:
    provider = _provider()
    draft = _draft(provider, marker=marker)
    output = tmp_path / f"modelo-100-boolean-{marker}.xml"
    _write_declared_export(provider, draft=draft, output=output)

    result = verify_export(draft, file_path=output, schema_provider=provider)

    assert result.verdict is DeclaracionVerifyVerdict.MATCH
    assert result.mismatched_casilla_ids == ()


def test_the_two_row_types_are_spelled_differently_in_the_file(tmp_path: Path) -> None:
    """The pair really does exercise two spellings, not one type twice.

    Without this the test above would still pass if both casillas happened to land
    on the same dictionary type, and would then prove nothing about the asymmetry
    it exists to defend.
    """
    provider = _provider()
    output = tmp_path / "modelo-100-boolean-spellings.xml"
    _write_declared_export(provider, draft=_draft(provider, marker=True), output=output)

    rendered = output.read_text(encoding="utf-8")

    assert "<AUTORTP>1</AUTORTP>" in rendered
    assert "<CEDIDO1>SI</CEDIDO1>" in rendered
