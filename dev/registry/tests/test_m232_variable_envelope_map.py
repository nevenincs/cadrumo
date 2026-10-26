"""Source-pinned M232 envelope map joins for both official design editions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.application.filing.export_envelope import (
    FilingEnvelopeOccurrence,
    FilingEnvelopeRenderResult,
    assemble_filing_envelope_payload,
)
from cadrumo.core.hashing import content_hash_hex, sha256_hex
from cadrumo.core.modelo import Modelo
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

from ..compiler.loader import load_modelo_directory, load_shared_catalogues
from ..pipeline.joined_record_design import join_record_design_semantics
from ..pipeline.record_design_intermediate import (
    RecordDesignIntermediateRelativeSuffixMarker,
    load_record_design_intermediate,
)
from ..pipeline.semantic_map import load_semantic_map
from ..pipeline.variable_envelope import FilingEnvelopeProvenance, compile_filing_envelope_definition

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DESIGNS = (
    ("2016", "2016-2017", "aeat-dr-232-2016", "fb6802dcf8746e69331b67873cb2e5cae90c3343c69b4f4d430aecde3c56b6ad", 22),
    (
        "2018",
        "2018-y-siguientes",
        "aeat-dr-232-2018",
        "a61485dfc480393ec1dfc926142fd0b6a9386e28e60746da3dfbf2fdaf3bffff",
        21,
    ),
)


@pytest.mark.parametrize(("epoch", "revision", "source_ref", "source_sha256", "total_row"), _DESIGNS)
def test_m232_complete_source_join_and_envelope(
    epoch: str, revision: str, source_ref: str, source_sha256: str, total_row: int
) -> None:
    root = bundled_path("registry", "aeat")
    catalogues = load_shared_catalogues(root)
    modelo = load_modelo_directory(root / "modelos" / "232")
    inspection = RegistryRevisionInspection.from_revision(
        modelo=modelo,
        revision=modelo.revisions[revision],
        source_root=bundled_path(),
        sources=catalogues.sources,
        legal_ref_ids=frozenset(catalogues.legal),
    )
    intermediate = load_record_design_intermediate(
        bundled_path(), dict(catalogues.sources), source_ref=source_ref, filing_year=int(epoch), design_epoch=epoch
    )
    semantic = load_semantic_map(Path(__file__).resolve().parents[1] / "mappings" / "modelo_232" / epoch)
    joined = join_record_design_semantics(semantic, intermediate, inspection)

    assert joined.source.source_sha256 == source_sha256
    assert len(joined.records) == 2
    assert len(joined.fields) == 250
    assert tuple(record.semantic_record.export_record_id for record in joined.records) == (
        "m232-operaciones-vinculadas",
        "m232-paraisos-fiscales",
    )
    contract = joined.variable_envelope_contract
    assert contract is not None
    assert contract.parser_envelope.prefix_extent == 328
    assert contract.parser_envelope.body_source_row == 19
    assert isinstance(contract.parser_envelope.closing, RecordDesignIntermediateRelativeSuffixMarker)
    assert contract.parser_envelope.closing.source_row == 20
    assert contract.parser_envelope.total_source_row == total_row
    terminator = contract.parser_envelope.terminator
    if epoch == "2016":
        assert terminator is not None
        assert (
            terminator.source_row,
            terminator.source_cell,
            terminator.ordinal,
            terminator.offset,
            terminator.length,
            terminator.aeat_type,
            terminator.normalized_description,
            terminator.validation,
            terminator.content,
        ) == (
            21,
            "A21",
            16,
            "***",
            2,
            "An",
            "Fin de Registro. Constante CRLF( Hexadecimal 0D0A, Decimal 1310)",
            None,
            None,
        )
    else:
        assert terminator is None
    declaration = compile_filing_envelope_definition(
        contract.semantic,
        contract.parser_envelope,
        modelo="232",
        source=joined.source,
        body_record_ids=("m232-operaciones-vinculadas", "m232-paraisos-fiscales"),
    )
    assert declaration.record_identity == "DR23200"
    assert declaration.prefix_extent == 328
    assert len(declaration.prefix_fields) == 13
    assert declaration.record_terminator == ("crlf" if epoch == "2016" else None)
    provenance = FilingEnvelopeProvenance(
        schema_version=2,
        revision_id=revision,
        layout_id="source-only-layout",
        semantic_sha256="0" * 64,
        envelope=declaration,
        envelope_sha256=content_hash_hex(declaration.model_dump(mode="json")),
    )
    if epoch == "2016":
        changed_provenance = provenance.model_dump(mode="json")
        changed_provenance["envelope"]["record_terminator"] = None
        with pytest.raises(ValueError, match="provenance digest does not match"):
            FilingEnvelopeProvenance.model_validate_json(json.dumps(changed_provenance))

    # Static source proof deliberately does not grant the historical 2016
    # coordinate a runtime snapshot below the registry's support floor.
    period = Period.from_year_and_code(int(epoch), "0A")
    prefix = b" " * 328
    closer = f"</T2320{epoch}0A0000>".encode("ascii")
    occurrence = FilingEnvelopeOccurrence(
        record_id="m232-operaciones-vinculadas", occurrence=1, payload=b"body", payload_sha256=sha256_hex(b"body")
    )
    suffix, payload = assemble_filing_envelope_payload(
        declaration, prefix=prefix, occurrences=(occurrence,), closer=closer
    )
    assert suffix == (b"\r\n" if epoch == "2016" else b"")
    result = FilingEnvelopeRenderResult(
        draft_id="source-only-envelope-proof",
        revision_id=revision,
        layout_id="source-only-layout",
        modelo=Modelo("232"),
        period=period,
        envelope=declaration,
        occurrences=(occurrence,),
        prefix=prefix,
        closer=closer,
        terminator=suffix,
        payload=payload,
        payload_sha256=sha256_hex(payload),
        total_length=len(payload),
    )
    assert result.payload.endswith(closer + suffix)
    with pytest.raises(ValueError, match="terminator"):
        FilingEnvelopeRenderResult.model_validate({**result.model_dump(), "terminator": b"" if suffix else b"\r\n"})
    wrong_payload = payload[:-2] if suffix else payload + b"\r\n"
    with pytest.raises(ValueError, match="exact prefix, occurrences, closer, and terminator"):
        FilingEnvelopeRenderResult.model_validate(
            {
                **result.model_dump(),
                "payload": wrong_payload,
                "payload_sha256": sha256_hex(wrong_payload),
                "total_length": len(wrong_payload),
            }
        )

    stale_source = joined.source.model_copy(update={"source_sha256": "0" * 64})
    with pytest.raises(RegistryValidationError):
        compile_filing_envelope_definition(
            contract.semantic,
            contract.parser_envelope,
            modelo="232",
            source=stale_source,
            body_record_ids=("m232-operaciones-vinculadas", "m232-paraisos-fiscales"),
        )
    if epoch == "2018":
        historical = load_record_design_intermediate(
            bundled_path(),
            dict(catalogues.sources),
            source_ref="aeat-dr-232-2016",
            filing_year=2016,
            design_epoch="2016",
        )
        with pytest.raises(RegistryValidationError, match="unreviewed trailing record terminator"):
            compile_filing_envelope_definition(
                contract.semantic,
                contract.parser_envelope.model_copy(update={"terminator": historical.variable_envelopes[0].terminator}),
                modelo="232",
                source=joined.source,
                body_record_ids=("m232-operaciones-vinculadas", "m232-paraisos-fiscales"),
            )


def test_unterminated_existing_envelope_keeps_its_committed_canonical_digest() -> None:
    manifest_path = (
        bundled_path("registry", "aeat")
        / "modelos"
        / "303"
        / "revisions"
        / "2025"
        / "export"
        / "_generation.provenance.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original = manifest["variable_envelope_contract"]
    typed = FilingEnvelopeProvenance.model_validate_json(json.dumps(original))
    assert typed.envelope_sha256 == "08b5515d8f59cffca4b8a4752eaf97077489872a3f1f1c663b1a6504159a9485"
    assert typed.model_dump(mode="json") == original
    assert "record_terminator" not in typed.envelope.model_dump(mode="json")


@pytest.mark.parametrize("mutation", ("row", "cell", "ordinal", "length", "description", "missing"))
def test_m232_2016_terminator_refuses_changed_source_marker(mutation: str) -> None:
    root = bundled_path("registry", "aeat")
    catalogues = load_shared_catalogues(root)
    intermediate = load_record_design_intermediate(
        bundled_path(), dict(catalogues.sources), source_ref="aeat-dr-232-2016", filing_year=2016, design_epoch="2016"
    )
    envelope = intermediate.variable_envelopes[0]
    marker = envelope.terminator
    assert marker is not None
    changes = {
        "row": {"source_row": 22},
        "cell": {"source_cell": "A22"},
        "ordinal": {"ordinal": 17},
        "length": {"length": 1},
        "description": {"normalized_description": "Fin de Registro. LF"},
        "missing": None,
    }
    selected = changes[mutation]
    changed = envelope.model_copy(
        update={"terminator": None if selected is None else marker.model_copy(update=selected)}
    )
    semantic = load_semantic_map(Path(__file__).resolve().parents[1] / "mappings" / "modelo_232" / "2016")
    with pytest.raises(RegistryValidationError, match="terminator differs"):
        compile_filing_envelope_definition(
            semantic.variable_envelopes[0],
            changed,
            modelo="232",
            source=intermediate.source,
            body_record_ids=("m232-operaciones-vinculadas", "m232-paraisos-fiscales"),
        )
