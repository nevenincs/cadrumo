"""Anti-legacy proof for the canonical filing producer boundary."""

from __future__ import annotations

import inspect
from hashlib import sha256
from importlib import import_module

import pytest

from ....core.filing_producer_key import FilingProducerKey
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations import registry
from ....domain.calculations.registry.export_semantics import ExportComputedKey, ExportDraftAttribute
from ....domain.calculations.registry.schema_exports import (
    FilingEnvelopeDefinition,
    FilingEnvelopePrefixFieldDeclaration,
    FilingEnvelopePrefixRole,
)
from .. import _export as export_module
from .. import record_renderer as record_renderer_module
from .._export import export_draft, render_filing_envelope
from .._producer_ownership import filing_producer_ownership
from ..export_envelope import FilingEnvelopeOccurrence, FilingEnvelopeRenderRequest, FilingEnvelopeRenderResult
from ..export_producer import _SHARED_SNAPSHOT_PRODUCER_KEYS

modelo_export_module = import_module("cadrumo.application.modelo.export")

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_snapshot_resolver_is_exhaustive_over_the_core_producer_vocabulary() -> None:
    ownership = filing_producer_ownership(shared_snapshot_keys=_SHARED_SNAPSHOT_PRODUCER_KEYS)
    assert set(ownership) == set(FilingProducerKey)
    assert all(owner.strip() for owner in ownership.values())


def test_legacy_header_surfaces_are_deleted_instead_of_normalised() -> None:
    assert not hasattr(registry, "ExportHeaderKey")
    assert not hasattr(export_module, "_normalise_export_headers")
    assert not hasattr(modelo_export_module, "compose_export_headers")
    assert "headers" not in inspect.signature(export_draft).parameters
    assert "producer_snapshot" in inspect.signature(export_draft).parameters


@pytest.mark.parametrize(
    "legacy_token",
    (
        "presenter_nif",
        "presenter_tax_id",
        "complementaria",
        "previous_receipt",
        "name",
        "program_version",
        "aeat_seal",
    ),
)
def test_historical_header_spellings_are_not_enum_members_or_values(legacy_token: str) -> None:
    assert legacy_token not in FilingProducerKey.__members__
    assert legacy_token not in {member.value for member in FilingProducerKey}
    with pytest.raises(ValueError):
        FilingProducerKey(legacy_token)


def test_draft_vocabulary_has_no_profile_or_taxpayer_identity_fallback() -> None:
    assert set(record_renderer_module._DRAFT_VALUE_PRODUCERS) == set(ExportDraftAttribute)
    assert set(record_renderer_module._COMPUTED_VALUE_PRODUCERS) == set(ExportComputedKey)
    assert "profile_tax_id" not in {member.value for member in ExportDraftAttribute}


#: Modelo 303 prints the shared envelope grammar in its thirteen-row spelling:
#: every role except the composed opening tag, which is the ALTERNATIVE spelling
#: of the six rows this design prints separately.
_M303_PREFIX_ROLES: tuple[FilingEnvelopePrefixRole, ...] = tuple(
    role for role in FilingEnvelopePrefixRole if role is not FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG
)


def _m303_envelope_definition() -> FilingEnvelopeDefinition:
    return FilingEnvelopeDefinition(
        source_ref="aeat-dr-303-2023",
        source_sha256="a" * 64,
        record_identity="DP30300",
        prefix_extent=328,
        prefix_fields=tuple(
            FilingEnvelopePrefixFieldDeclaration(role=role, length=length)
            for role, length in zip(
                _M303_PREFIX_ROLES,
                (2, 3, 1, 4, 2, 5, 5, 70, 4, 4, 9, 213, 6),
                strict=True,
            )
        ),
        body_record_ids=("m303-declaration",),
        product_identity_requirement="aeat-product-software-identity-v1",
        closer_derivation="relative-closer-v1",
        total_derivation="emitted-byte-total-v1",
    )


def test_filing_envelope_public_facade_exposes_one_closed_request() -> None:
    assert render_filing_envelope is export_module.render_filing_envelope
    assert tuple(inspect.signature(render_filing_envelope).parameters) == ("request",)
    assert set(FilingEnvelopeRenderRequest.model_fields) == {
        "registry_snapshot",
        "layout",
        "draft",
        "producer_snapshot",
        "prior_domiciliation_election",
        "product_software_identity",
    }


def test_m303_envelope_occurrence_and_result_validate_emitted_byte_evidence() -> None:
    period = Period.from_year_and_code(2023, "4T")
    envelope = _m303_envelope_definition()
    occurrence = FilingEnvelopeOccurrence(
        record_id="m303-declaration",
        occurrence=1,
        payload=b"body",
        payload_sha256=sha256(b"body").hexdigest(),
    )
    prefix = b" " * 328
    closer = b"</T303020234T0000>"
    payload = prefix + occurrence.payload + closer
    result = FilingEnvelopeRenderResult(
        draft_id="draft-303",
        revision_id="2023",
        layout_id="generated-modelo-303-2023-fichero",
        modelo=Modelo.M303,
        period=period,
        envelope=envelope,
        occurrences=(occurrence,),
        prefix=prefix,
        closer=closer,
        payload=payload,
        payload_sha256=sha256(payload).hexdigest(),
        total_length=len(payload),
    )

    assert result.payload == prefix + b"body" + closer
    assert result.total_length == len(result.payload)
    zero_payload = prefix + closer
    zero_result = FilingEnvelopeRenderResult(
        draft_id="draft-303",
        revision_id="2023",
        layout_id="generated-modelo-303-2023-fichero",
        modelo=Modelo.M303,
        period=period,
        envelope=envelope,
        occurrences=(),
        prefix=prefix,
        closer=closer,
        payload=zero_payload,
        payload_sha256=sha256(zero_payload).hexdigest(),
        total_length=len(zero_payload),
    )
    second_occurrence = FilingEnvelopeOccurrence(
        record_id="m303-declaration",
        occurrence=2,
        payload=b"second-body",
        payload_sha256=sha256(b"second-body").hexdigest(),
    )
    many_payload = prefix + occurrence.payload + second_occurrence.payload + closer
    many_result = FilingEnvelopeRenderResult(
        draft_id="draft-303",
        revision_id="2023",
        layout_id="generated-modelo-303-2023-fichero",
        modelo=Modelo.M303,
        period=period,
        envelope=envelope,
        occurrences=(occurrence, second_occurrence),
        prefix=prefix,
        closer=closer,
        payload=many_payload,
        payload_sha256=sha256(many_payload).hexdigest(),
        total_length=len(many_payload),
    )

    assert zero_result.occurrences == ()
    assert many_result.payload == prefix + b"bodysecond-body" + closer
    assert tuple(item.occurrence for item in many_result.occurrences) == (1, 2)
    with pytest.raises(ValueError, match="occurrence digest"):
        FilingEnvelopeOccurrence(
            record_id="m303-declaration",
            occurrence=1,
            payload=b"body",
            payload_sha256="b" * 64,
        )
    with pytest.raises(ValueError, match="contiguous"):
        FilingEnvelopeRenderResult(
            draft_id="draft-303",
            revision_id="2023",
            layout_id="generated-modelo-303-2023-fichero",
            modelo=Modelo.M303,
            period=period,
            envelope=envelope,
            occurrences=(occurrence.model_copy(update={"occurrence": 2}),),
            prefix=prefix,
            closer=closer,
            payload=payload,
            payload_sha256=sha256(payload).hexdigest(),
            total_length=len(payload),
        )
