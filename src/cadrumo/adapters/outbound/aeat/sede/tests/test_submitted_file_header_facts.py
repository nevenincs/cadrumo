"""The submitted fichero's header facts survive the observation projection.

AEAT states the result disposition as a HEADER field in its diseño de registro
for Modelo 303 -- ``tipo de declaración`` at offset 13, one byte, carrying the
code directly -- and the sin-actividad flag as another header at offset 391. The
export layout models both as headers, and the payload parser returns both.

Before this projection existed, ``parsed.fields`` had exactly one consumer: a
context check reading only ``DRAFT``-kind fields to confirm modelo, year and
period. Every header field was parsed and then discarded, so the disposition
code AEAT hands over in one byte of a file the capture already fetches and
already parses was thrown away on the way to the observation set.

These tests exercise a REAL fichero produced by the production export path, not
a hand-built byte string: a synthetic payload cannot reach the parser at all,
because the layout carries literal envelope fields that refuse anything the
exporter did not write.

See Also:
    :class:`~core.ResultDisposition`
        The code set the ``declaration_type`` header carries.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core import Modelo
from .....core.resources import bundled_path
from .....domain.calculations.registry import bundled_authority
from .._declarations_observations import _observed_headers_from_submitted_file

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]


def _snapshot():
    return bundled_authority().snapshot(modelo_id=Modelo.M303.value, filing_year=2025, period="1T")


def _exported_fichero(tmp_path: Path, *, declaration_type: str) -> bytes:
    from ....aeat.export._formats.tests._fichero_boe_roundtrip_support import (
        _export_approved_303_fichero,
        _m303_headers,
    )

    return _export_approved_303_fichero(
        tmp_path,
        filename="header-facts.txt",
        headers=_m303_headers(declaration_type=declaration_type, redeme="N"),
    ).payload


@pytest.mark.parametrize("code", ["C", "I", "D", "N"])
def test_the_disposition_header_survives_the_projection(tmp_path: Path, code: str) -> None:
    """Whatever disposition the fichero carries is what the projection reports.

    Parametrised over four codes rather than asserted once, so a projection that
    returned a constant -- or that read the wrong offset and happened to find a
    plausible letter -- cannot pass.
    """
    payload = _exported_fichero(tmp_path, declaration_type=code)

    headers = _observed_headers_from_projection(payload)

    assert headers.get("declaration_type") == code


def _observed_headers_from_projection(payload: bytes) -> dict[str, str]:
    return _observed_headers_from_submitted_file(snapshot=_snapshot(), body=payload)


def test_the_projection_reports_more_than_the_disposition(tmp_path: Path) -> None:
    """Every stated header is carried, not a hand-picked one.

    The value of doing this header-level rather than per-field is that the
    sin-actividad flag, the REDEME marker and the rest arrive with the
    disposition instead of each needing its own change later.
    """
    headers = _observed_headers_from_projection(_exported_fichero(tmp_path, declaration_type="C"))

    assert len(headers) > 1, f"only {sorted(headers)} survived, so the projection is not header-general"
    assert "declaration_type" in headers


def test_no_header_is_reported_as_a_casilla(tmp_path: Path) -> None:
    """The header facts stay out of the casilla channel.

    A header is not a casilla: AEAT omits boxes 72 and 73 from the record design
    precisely because it encodes these elections as headers instead. Giving them
    a synthetic casilla id would put this registry and the official structure in
    disagreement about the concept's kind, which is the defect this projection
    exists to avoid rather than introduce.
    """
    from .._declarations_observations import _observed_casillas_from_submitted_file
    from .._schema import FiledDeclaracionArtefact

    payload = _exported_fichero(tmp_path, declaration_type="C")
    headers = _observed_headers_from_projection(payload)
    assert headers

    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url="https://www6.aeat.es/probe",  # type: ignore[arg-type]
        content_type="text/plain",
        byte_count=len(payload),
        sha256="0" * 64,
        captured_at=__import__("cadrumo.core.time", fromlist=["now"]).now(),
    )
    casillas = _observed_casillas_from_submitted_file(
        snapshot=_snapshot(),
        declaration=_declaration_for(payload),
        body=payload,
        artefact=artefact,
    )

    casilla_ids = {casilla.casilla_id for casilla in casillas}
    assert casilla_ids, "the casilla projection returned nothing, so this test proves nothing about separation"
    assert not (casilla_ids & set(headers)), "a header key leaked into the casilla channel"


def _declaration_for(payload: bytes):
    from .....core import Period
    from .._declarations_schema import Declaracion

    del payload
    return Declaracion(
        modelo="303",
        ejercicio=2025,
        period=Period.from_year_and_code(2025, "1T"),
        expediente_id="2025303000000001",
        estado="ALTA",
        presented_at=__import__("datetime").datetime(2025, 4, 10, 9, 0, tzinfo=__import__("datetime").UTC),
    )


def test_an_unparseable_payload_yields_no_headers_rather_than_raising() -> None:
    """A header read that cannot parse must not take the casilla projection down.

    The casilla projection is the caller's primary result and reports its own
    failure; a header read is additive. Returning empty is the behaviour that
    keeps a fichero whose casillas parse from losing them because a header did
    not.
    """
    assert _observed_headers_from_projection(b"not a fichero") == {}


def test_the_layout_models_the_disposition_as_a_header_not_a_casilla() -> None:
    """Anchors the premise: the registry agrees with AEAT about the concept's kind.

    If someone later re-models the disposition as a casilla, this fails and the
    projection above becomes the wrong shape -- which is exactly the moment a
    reader needs to be told, rather than discovering it through a silently
    changed observation set.
    """
    from .....domain.calculations.registry import CasillaFieldKind, resolve_export_layout

    resolved = resolve_export_layout(_snapshot())

    matching = [f for f in resolved.fields_by_id.values() if getattr(f, "header_key", None) == "declaration_type"]
    assert len(matching) == 1, "expected exactly one declaration_type field in the layout"
    field = matching[0]
    assert field.kind is CasillaFieldKind.HEADER
    assert field.casilla_id is None
    assert field.offset == 13
    assert field.length == 1
