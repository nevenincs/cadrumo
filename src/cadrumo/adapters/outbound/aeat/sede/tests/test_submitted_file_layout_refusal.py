"""A submitted fichero the export layout cannot read is refused, never guessed.

This projection used to absorb a layout parse failure for Modelo 303 and fall
through to a positional page-03 reader: five result casillas lifted from
hardcoded byte offsets, returned with the same shape and the same confidence as
a layout read. Nothing in the result said which path produced it.

That silence hid a real defect. The layout declared the refund-only DID record
required while the exporter writes it only on a devolucion, so for the
compensacion, ingreso and negativa dispositions NO field of a real fichero
parsed at all -- and every casilla an operator saw was a positional guess. The
record is now declared optional on both revisions and all four dispositions
parse, which makes the absorbing branch more dangerous rather than less: its
trigger is now rare, so the next time it fires it would be masking a genuine
layout failure on a path that still produces plausible numbers.

The refusal is therefore the behaviour under test, and the positive control
below is what separates "refuses on failure" from "refuses always".

See Also:
    :func:`~adapters.outbound.aeat.sede.observed_casillas_from_submitted_file`
        The projection whose failure mode these tests pin.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from ......core import Modelo, Period, validated_casilla_id
from ......core.errors import build_error_envelope
from ......domain.calculations.registry import bundled_authority, resolve_export_layout
from .._declarations import _record_submitted_file_extraction_error
from .._declarations_observations import _observed_casillas_from_submitted_file
from .._declarations_schema import Declaracion
from .._errors import SedeParseError
from .._schema import FiledDeclaracionArtefact

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

# The two revisions AEAT's published designs bind, exercised through the filing
# year that selects each: a change that only works on the current revision is a
# change that silently stops reading the older filings the carry depends on.
_YEARS_BY_REVISION = {"2009-y-siguientes": 2022, "2025": 2025}


def _snapshot(filing_year: int):
    return bundled_authority().snapshot(modelo_id=Modelo.M303.value, filing_year=filing_year, period="1T")


@cache
def _exported_draft_and_payload(*, filing_year: int, declaration_type: str):
    """Produce a real M303 fichero plus the draft it was written from.

    Returned together deliberately: the draft's own casilla values are the
    authority the read-back is compared against, which makes this a
    writer-to-reader roundtrip over the layout rather than a claim about what
    the figures ought to be.

    Cached because the draft build plus export is the expensive half of every
    case here and the result is a pure function of the two arguments; the
    parametrisation would otherwise rebuild the same fichero repeatedly.
    """
    from ......application.filing import (
        ModeloDraftStatus,
        ModeloOperatorProfile,
        build_draft,
        build_runtime_schema_provider,
        export_draft,
    )

    period = Period.from_year_and_code(filing_year, "1T")
    provider = build_runtime_schema_provider(filing_year=filing_year, period=period, modelos=("303",))
    draft = build_draft(
        modelo="303",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Layout refusal probe"),
        inputs={
            validated_casilla_id("07", surface="probe"): Decimal("10000.00"),
            validated_casilla_id("iva.repercutido.general", surface="probe"): Decimal("2100.00"),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
    )
    draft = draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})
    with TemporaryDirectory() as scratch:
        output = Path(scratch) / f"m303-{filing_year}-{declaration_type}.txt"
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
        return draft, output.read_bytes()


def _declaration(filing_year: int) -> Declaracion:
    return Declaracion(
        modelo="303",
        ejercicio=filing_year,
        period=Period.from_year_and_code(filing_year, "1T"),
        expediente_id=f"{filing_year}303000000001",
        estado="ALTA",
        presented_at=dt.datetime(filing_year, 4, 10, 9, 0, tzinfo=dt.UTC),
    )


def _artefact(payload: bytes) -> FiledDeclaracionArtefact:
    return FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url="https://www6.aeat.es/probe",  # type: ignore[arg-type]
        content_type="text/plain",
        byte_count=len(payload),
        sha256="0" * 64,
        captured_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
    )


def _project(payload: bytes, *, filing_year: int):
    return _observed_casillas_from_submitted_file(
        snapshot=_snapshot(filing_year),
        declaration=_declaration(filing_year),
        body=payload,
        artefact=_artefact(payload),
    )


@pytest.mark.parametrize(("revision_id", "filing_year"), sorted(_YEARS_BY_REVISION.items()))
@pytest.mark.parametrize("declaration_type", ["D", "C", "I", "N"])
def test_a_real_fichero_is_read_through_the_layout_on_every_disposition(
    revision_id: str,
    filing_year: int,
    declaration_type: str,
) -> None:
    """The positive control: a parseable fichero still yields its fields.

    Without this, "refuses on a layout failure" is indistinguishable from
    "refuses always", and the deleted fallback would have been replaced by a
    surface that reads nothing at all.

    The locator assertion is the discriminating one, and it is stated
    POSITIVELY: every observation must carry the resolved layout's own id as its
    provenance. Asserting the absence of one known bad prefix would decay to
    nothing now that the guessing path cannot produce a locator at all, whereas
    requiring the layout form keeps saying where the values legitimately came
    from. The prefix is read from the resolved layout rather than written out,
    so renaming the layout cannot make this pass vacuously.

    What this case adds over the sibling coverage on the header-facts surface is
    the refund disposition, the older revision, and the roundtrip below.
    """
    draft, payload = _exported_draft_and_payload(filing_year=filing_year, declaration_type=declaration_type)
    snapshot = _snapshot(filing_year)
    assert snapshot.revision.id == revision_id, "the filing year no longer selects this revision"
    layout_prefix = f"{resolve_export_layout(snapshot).layout.id}:"

    observed = _project(payload, filing_year=filing_year)

    assert observed, "the projection returned nothing, so the layout read the payload as empty"
    off_layout = sorted({c.source_locator for c in observed if not c.source_locator.startswith(layout_prefix)})
    assert not off_layout, f"an observation carries provenance from outside the layout: {off_layout[:3]}"
    # Writer-to-reader roundtrip: the draft that produced the bytes is the
    # authority for what the bytes say, so this pins the layout read without
    # asserting any figure the engine also computed. Scored over every casilla
    # the draft populated rather than one named box, because which boxes a
    # revision derives from these inputs differs between the two revisions and
    # a single-box assertion would encode one revision's shape as the contract.
    observed_by_id = {casilla.casilla_id: casilla.value for casilla in observed}
    drafted_amounts = {
        value.casilla_id: value.value
        for value in draft.values
        if isinstance(value.value, Decimal) and value.casilla_id in observed_by_id
    }
    assert drafted_amounts, "no drafted amount survived the read-back, so this comparison is vacuous"
    mismatched = {
        casilla_id: (amount, observed_by_id[casilla_id])
        for casilla_id, amount in drafted_amounts.items()
        if Decimal(observed_by_id[casilla_id]) != amount
    }
    assert not mismatched, f"the read-back disagrees with what the exporter was given: {mismatched}"


@pytest.mark.parametrize(("revision_id", "filing_year"), sorted(_YEARS_BY_REVISION.items()))
def test_a_payload_the_layout_cannot_read_is_refused_rather_than_guessed(
    revision_id: str,
    filing_year: int,
) -> None:
    """A layout parse failure surfaces as a refusal naming what failed.

    Truncation is the same failure class the DID defect produced -- the parser
    runs out of payload before a record it was told to expect -- so this
    reproduces the condition that used to degrade silently, on a payload that
    is otherwise a genuine exporter product.
    """
    _, payload = _exported_draft_and_payload(filing_year=filing_year, declaration_type="C")
    truncated = payload[: len(payload) // 2]

    with pytest.raises(SedeParseError) as caught:
        _project(truncated, filing_year=filing_year)

    error = caught.value
    context = error.context or {}
    assert context["operation"] == "submitted_file_layout_parse"
    assert context["modelo"] == Modelo.M303
    assert context["revision"] == revision_id
    assert context["period"] == "1T"
    # The reason is the parser's own, and it names the concrete layout element
    # the read stopped on -- which record ran out of payload, or which literal
    # envelope field disagreed. A refusal that says only "parse failed" hands
    # the next reader nothing, which is the other shape of masking, so the
    # assertion is on the presence of a layout identifier rather than on one
    # wording the parser happens to use for one truncation point.
    reason = str(context["reason"])
    assert "modelo-303-" in reason, f"the refusal names no layout element it failed on: {reason!r}"
    assert reason in str(error), "the message drops the reason the context carries"
    assert "could not be read through its export layout" in str(error)


def test_a_refusal_is_recorded_before_the_declaration_pdf_fallback_is_considered() -> None:
    """The adapter retains its own parser reason and leaves fallback ordering intact."""
    filing_year = 2025
    _, payload = _exported_draft_and_payload(filing_year=filing_year, declaration_type="C")
    with pytest.raises(SedeParseError) as caught:
        _project(payload[: len(payload) // 2], filing_year=filing_year)

    metadata = {"tipo_solicitud": "", "observaciones": ""}
    _record_submitted_file_extraction_error(metadata, caught.value)
    assert metadata["submitted_file_extraction_error"] == str(caught.value)
    assert "modelo-303-" in metadata["submitted_file_extraction_error"]

    from .. import _declarations as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    recorded_at = source.index("_record_submitted_file_extraction_error(metadata, exc)")
    fallback_at = source.index("if not casillas and declaration_pdf_body is not None:")
    assert recorded_at < fallback_at, "the layout refusal must be recorded before the PDF fallback is evaluated"


@pytest.mark.parametrize(("revision_id", "filing_year"), sorted(_YEARS_BY_REVISION.items()))
def test_the_refusal_carries_an_actionable_next_step(
    revision_id: str,
    filing_year: int,
) -> None:
    """The refusal resolves to a suggestion rather than to ``None``.

    A bare exception on an operator-reachable path is a different kind of
    masking: the operator learns that something failed and nothing about what
    to do, so the failure gets worked around instead of fixed.
    """
    del revision_id
    _, payload = _exported_draft_and_payload(filing_year=filing_year, declaration_type="C")

    with pytest.raises(SedeParseError) as caught:
        _project(payload[: len(payload) // 2], filing_year=filing_year)

    # The remediation TEXT is still produced at the raise site; only its delivery was
    # retired, so the claim stays checkable against the live value rather than being
    # deferred. This module's whole subject is that an operator-reachable refusal must
    # say what to do: declaring the omitted record OPTIONAL is the fix, as against
    # reading the payload by byte offset, which is the degradation this file keeps out.
    remediation = caught.value.suggestion
    assert remediation, "the refusal produces no remediation text at all"
    assert "optional" in remediation, f"the remediation does not point at the fix: {remediation!r}"

    # Delivery ground truth, so this cannot be read as proving the operator receives it.
    # Default suggestions were retired as the authority and ``FAIL_SEDE_PARSE`` is not
    # yet converted to a catalogue action identity, so the envelope carries no next step
    # today. Its conversion is the adapters part-one step, behind the migration contract.
    assert build_error_envelope(caught.value).action is None


def test_the_projection_holds_no_modelo_303_positional_reader() -> None:
    """Anchors the removal itself.

    The absorbing branch and its offset table are gone rather than disabled, so
    a later change cannot re-enable a degradation path by flipping a condition.
    If a positional reader is reintroduced, this fails at the moment it lands
    rather than the moment it silently fires.
    """
    from .. import _declarations_observations as module

    source = Path(module.__file__).read_text(encoding="utf-8")

    assert "T30303" not in source, "a Modelo 303 page-03 offset reader is back in the projection module"
    assert not hasattr(module, "_observed_modelo_303_casillas_from_submitted_file")
    assert not hasattr(module, "_is_modelo_303_page_03_fallback")
