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

from ......core import Modelo, Period, validated_casilla_id
from ......domain.calculations.registry import bundled_authority, resolve_export_layout
from ......tests.aeat_literal_fixtures import aeat_url
from .._declarations_observations import (
    _observed_headers_from_submitted_file,
    observed_casillas_from_submitted_file,
)
from .._declarations_schema import Declaracion
from .._schema import FiledDeclaracionArtefact

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]


def _snapshot():
    return bundled_authority().snapshot(modelo_id=Modelo.M303.value, filing_year=2025, period="1T")


def _declaration() -> Declaracion:
    """A Declaracion matching the exported fichero's own modelo, year and period.

    The projection cross-checks the parsed draft fields against this, so a
    mismatch would refuse before provenance could be asserted.
    """
    from datetime import UTC, datetime

    return Declaracion(
        modelo="303",
        ejercicio=2025,
        period=Period.from_year_and_code(2025, "1T"),
        expediente_id="2025303PROBE0001",
        estado="ALTA",
        presented_at=datetime(2025, 4, 15, 10, 0, tzinfo=UTC),
        justificante_cell_index=7,
    )


def _artefact(payload: bytes) -> FiledDeclaracionArtefact:
    """The submitted-file artefact wrapper the projection reports against."""
    import hashlib
    from datetime import UTC, datetime

    return FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=aeat_url("www6", "/probe/submitted-file"),
        content_type="text/plain",
        byte_count=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        captured_at=datetime(2025, 4, 15, 10, 5, tzinfo=UTC),
    )


def _exported_fichero(tmp_path: Path, *, declaration_type: str) -> bytes:
    """Produce a real M303 fichero through the production export path.

    Built here rather than borrowed from the export package's own test support:
    that helper is private to another package, and reaching into it would be the
    cross-package private import the hygiene gate forbids. Everything it uses is
    on the public filing facade, so the duplication is a few lines and the
    boundary stays clean.
    """
    from decimal import Decimal

    from ......application.filing import (
        ModeloOperatorProfile,
        build_draft,
        build_runtime_schema_provider,
        export_draft,
    )
    from ......core import Period
    from ......domain.submission import ModeloDraftStatus


    provider = build_runtime_schema_provider(modelos=("303",))
    draft = build_draft(
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Header facts probe"),
        inputs={
            validated_casilla_id("07", surface="probe"): Decimal("10000.00"),
            validated_casilla_id("iva.repercutido.general", surface="probe"): Decimal("2100.00"),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
    )
    draft = draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})

    output = tmp_path / "header-facts.txt"
    export_draft(
        draft,
        output_path=output,
        headers={
            "declaration_type": declaration_type,
            "surnames": "GARCIA LOPEZ",
            "full_name": "GARCIA LOPEZ JUAN",
            "program_version": "A001",
            "presenter_nif": "12345678Z",
            "redeme": "N",
        },
        schema_provider=provider,
    )
    return output.read_bytes()


def test_the_disposition_header_survives_the_projection(tmp_path: Path) -> None:
    """A devolucion fichero's disposition reaches the observation projection.

    ``D`` is the refund disposition, and it is the one that carries the DID
    bank-details page. The test below covers the three that do not.
    """
    payload = _exported_fichero(tmp_path, declaration_type="D")

    headers = _observed_headers_from_projection(payload)

    assert headers.get("declaration_type") == "D"


@pytest.mark.parametrize("code", ["C", "I", "N", "U", "G", "V", "X"])
def test_a_non_refund_fichero_is_parsed_back_and_reports_its_disposition(tmp_path: Path, code: str) -> None:
    """The three dispositions that carry no DID page read back through the layout.

    A devolucion filing carries the bank-details record because AEAT needs an
    account to pay into, so the exporter writes 8188 bytes where a compensacion,
    ingreso or negativa writes 7365. The layout declared that record required, so
    the READER demanded a record the WRITER had correctly omitted and refused the
    shorter payload with "payload ended before export record
    'modelo-303-page-did'".

    The consequence was larger than the disposition: for the three most common
    dispositions, NO field of a real submitted fichero could be read back through
    the layout at all. The record is now declared optional, which is what the
    renderer's own disposition predicate has always assumed, so all four parse.

    Asserted on the property rather than on a byte count: whatever the exporter
    wrote, the projection recovers the disposition it was given.
    """
    payload = _exported_fichero(tmp_path, declaration_type=code)

    headers = _observed_headers_from_projection(payload)

    assert headers.get("declaration_type") == code
    assert headers, "the projection returned nothing, so the payload did not parse"


@pytest.mark.parametrize("code", ["C", "I", "N", "U", "G", "V", "X"])
def test_a_non_refund_fichero_yields_casillas_through_the_layout_not_the_positional_fallback(
    tmp_path: Path,
    code: str,
) -> None:
    """The casillas come from the LAYOUT, which is the only assertion that discriminates.

    Asserting that a value came back cannot show the layout parse works. The
    casilla projection falls back to a positional Modelo 303 read when the layout
    parse raises, and that fallback SUCCEEDS, so a value arrives either way and a
    value-shaped assertion passes over a still-broken parse.

    The two paths are distinguishable by provenance rather than by value: a
    layout-parsed casilla records ``{layout_id}:{record_id}:{field_id}:...`` while
    the positional fallback records ``record:T30303:pos:...``. This asserts the
    layout form POSITIVELY rather than merely asserting the absence of the
    fallback form, so it keeps its meaning once the fallback stops substituting
    and starts refusing: in that world no positional locator can be produced at
    all, and this test still states where the values legitimately came from.
    """
    payload = _exported_fichero(tmp_path, declaration_type=code)
    snapshot = _snapshot()

    observations = observed_casillas_from_submitted_file(
        snapshot=snapshot,
        declaration=_declaration(),
        body=payload,
        artefact=_artefact(payload),
    )

    assert observations, "the projection produced nothing, so neither path ran"
    layout_prefix = f"{resolve_export_layout(snapshot).layout.id}:"
    off_layout = sorted(
        {
            observation.source_locator
            for observation in observations
            if not observation.source_locator.startswith(layout_prefix)
        }
    )
    assert not off_layout, (
        f"casillas did not come through the layout: {off_layout[:3]}. A locator of the form "
        "'record:T30303:pos:...' means the layout parse still failed and the positional "
        "fallback answered in its place."
    )


def _observed_headers_from_projection(payload: bytes) -> dict[str, str]:
    return _observed_headers_from_submitted_file(snapshot=_snapshot(), body=payload)


def test_the_projection_reports_more_than_the_disposition(tmp_path: Path) -> None:
    """Every stated header is carried, not a hand-picked one.

    The value of doing this header-level rather than per-field is that the
    sin-actividad flag, the REDEME marker and the rest arrive with the
    disposition instead of each needing its own change later.
    """
    headers = _observed_headers_from_projection(_exported_fichero(tmp_path, declaration_type="D"))

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

    payload = _exported_fichero(tmp_path, declaration_type="D")
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
    from ......core import Period
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
    from ......domain.calculations.registry import CasillaFieldKind, resolve_export_layout

    resolved = resolve_export_layout(_snapshot())

    matching = [f for f in resolved.fields_by_id.values() if getattr(f, "header_key", None) == "declaration_type"]
    assert len(matching) == 1, "expected exactly one declaration_type field in the layout"
    field = matching[0]
    assert field.kind is CasillaFieldKind.HEADER
    assert field.casilla_id is None
    assert field.offset == 13
    assert field.length == 1
