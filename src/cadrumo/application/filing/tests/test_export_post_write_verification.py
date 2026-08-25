"""Real-byte proofs for the declaration export post-write tripwire."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest

from ....core import Modelo
from ....domain.calculations.registry import CasillaFieldKind, parse_export_payload
from ....domain.filing import FilingExportError
from .. import GeneralFilingProfileFacts, build_filing_producer_snapshot
from .._export import (
    DeclaracionExportResult,
    DeclaracionVerifyVerdict,
    _verify_written_export,
    export_draft,
    verify_export,
)
from .._producer_snapshot import FilingProducerSnapshot
from ..runtime import RegistrySchemaAccessor
from ._export_support import (
    _approved_modelo_131_historical_registry_draft,
    _schema_provider,
    _typed_producer_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _modelo_131_snapshot() -> FilingProducerSnapshot:
    base = _typed_producer_snapshot()
    return build_filing_producer_snapshot(
        modelo=Modelo.M131,
        taxpayer_tax_id=base.taxpayer_tax_id,
        taxpayer_identity=base.taxpayer_identity,
        presenter=base.presenter,
        model_profile=GeneralFilingProfileFacts(),
        elections=base.elections,
        amendment_evidence=base.amendment_evidence,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )


def _export_modelo_131(output_path: Path) -> tuple[DeclaracionExportResult, RegistrySchemaAccessor]:
    provider = _schema_provider(filing_year=2023, period="4T", modelos=("131",))
    receipt = export_draft(
        _approved_modelo_131_historical_registry_draft(),
        output_path=output_path,
        producer_snapshot=_modelo_131_snapshot(),
        schema_provider=provider,
    )
    return receipt, provider


def test_export_draft_returns_only_after_the_written_bytes_match_the_draft(tmp_path: Path) -> None:
    output_path = tmp_path / "modelo-131.txt"
    receipt, provider = _export_modelo_131(output_path)

    verification = verify_export(
        _approved_modelo_131_historical_registry_draft(),
        file_path=output_path,
        schema_provider=provider,
    )

    assert verification.verdict is DeclaracionVerifyVerdict.MATCH
    assert verification.file_sha256 == receipt.file_sha256
    assert receipt.byte_size == output_path.stat().st_size


def test_post_write_tripwire_refuses_real_casilla_drift_and_preserves_the_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "modelo-131.txt"
    _, provider = _export_modelo_131(output_path)
    draft = _approved_modelo_131_historical_registry_draft()
    layout = provider.get_subview("131").export_layouts[0]
    payload = output_path.read_bytes()
    parsed = parse_export_payload(
        layout,
        payload,
        source_root=provider.source_root,
        sources=provider.sources,
    )
    casilla = next(value for value in parsed.casillas if value.casilla_id == "03")
    record = next(record for record in layout.records if record.id == casilla.record_id)
    field = next(field for field in record.fields if field.id == casilla.field_id)
    assert field.offset is not None
    assert field.length is not None
    assert record is layout.records[0]
    start = field.offset - 1
    end = start + field.length
    original = payload[start:end]
    assert original == casilla.raw.encode(record.encoding)
    replacement = original[:-1] + (b"1" if original[-1:] != b"1" else b"2")
    output_path.write_bytes(payload[:start] + replacement + payload[end:])

    verification = verify_export(draft, file_path=output_path, schema_provider=provider)
    assert verification.verdict is DeclaracionVerifyVerdict.DRIFT
    assert verification.mismatched_casilla_ids == ("03",)

    with pytest.raises(FilingExportError, match=r"post-write verification refused drift.*casillas=03"):
        _verify_written_export(draft, file_path=output_path, schema_provider=provider)

    assert output_path.read_bytes() != payload


def test_export_draft_itself_refuses_a_real_renderer_parser_disagreement(tmp_path: Path) -> None:
    """The call from ``export_draft`` is load-bearing, not merely structural.

    The production renderer writes every ordinary record once. The production
    parser skips an optional record unless a literal or discriminator identifies
    it. A valid registry object containing only an optional casilla record is
    therefore an honest incompatible artefact path: render succeeds, parse
    refuses the trailing bytes, and the post-write tripwire must prevent a
    receipt from escaping.
    """
    base = _schema_provider(filing_year=2023, period="4T", modelos=("131",))
    subview = base.get_subview("131")
    original_layout = subview.export_layouts[0]
    casilla_field = next(
        field
        for record in original_layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.CASILLA and field.casilla_id == "03"
    )
    incompatible_record = original_layout.records[0].model_copy(
        update={
            "id": "post-write-incompatible-record",
            "required": False,
            "repeat": None,
            "binding_record": None,
            "discriminator": None,
            "fields": (casilla_field.model_copy(update={"offset": 1}),),
        },
    )
    incompatible_layout = original_layout.model_copy(
        update={"id": "post-write-incompatible-layout", "records": (incompatible_record,)},
    )
    # export_draft selects its layout from the SNAPSHOT and _render_layout
    # asserts snapshot ownership by identity, so the doctored layout has to be
    # the very object the snapshot's revision carries -- doctoring the subview
    # alone would no longer reach the renderer at all.
    base_snapshot = base.get_snapshot("131")
    incompatible_snapshot = base_snapshot.model_copy(
        update={
            "revision": base_snapshot.revision.model_copy(
                update={"export_layouts": (incompatible_layout,)},
            ),
        },
    )
    provider = RegistrySchemaAccessor(
        collections=base.collections,
        subviews={
            **base.subviews,
            "131": replace(
                subview,
                export_layout_ids=(incompatible_layout.id,),
                export_layouts=(incompatible_layout,),
                completeness_manifest=None,
            ),
        },
        snapshots={**base.snapshots, "131": incompatible_snapshot},
    )
    output_path = tmp_path / "incompatible-modelo-131.txt"

    with pytest.raises(FilingExportError, match=re.escape("application.filing.export.errors.post_write_verification_refused")):
        export_draft(
            _approved_modelo_131_historical_registry_draft(),
            output_path=output_path,
            producer_snapshot=_modelo_131_snapshot(),
            schema_provider=provider,
        )

    assert output_path.is_file()
    assert output_path.stat().st_size > 0


def test_post_write_tripwire_types_an_unreadable_existing_path_as_missing(tmp_path: Path) -> None:
    provider = _schema_provider(filing_year=2023, period="4T", modelos=("131",))
    draft = _approved_modelo_131_historical_registry_draft()
    incompatible_path = tmp_path / "directory-not-a-declaration"
    incompatible_path.mkdir()

    verification = verify_export(draft, file_path=incompatible_path, schema_provider=provider)
    assert verification.verdict is DeclaracionVerifyVerdict.MISSING

    with pytest.raises(FilingExportError, match=re.escape("application.filing.export.errors.post_write_verification_refused")):
        _verify_written_export(draft, file_path=incompatible_path, schema_provider=provider)

    assert incompatible_path.is_dir()
