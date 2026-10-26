"""Official M190 signed amounts retain their reintegro and key conditions."""

from __future__ import annotations

import pytest

from cadrumo.application.filing.m190_context_validation import require_m190_signed_reintegro_context
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from cadrumo.domain.filing.errors import FilingExportValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PAIRS = ((81, 82), (108, 109), (255, 256), (282, 283))
_NAMES = (
    ("percepcion-dineraria", "percepcion-dineraria", "modelo-190-perceptor-row-percibido-dinerario"),
    ("percepcion-especie", "percepcion-especie", "modelo-190-perceptor-row-percibido-especie"),
    (
        "incapacidad-dineraria",
        "incapacidad-dineraria-percepcion",
        "modelo-190-perceptor-row-incapacidad-dineraria-percepcion",
    ),
    (
        "incapacidad-especie",
        "incapacidad-especie-valoracion",
        "modelo-190-perceptor-row-incapacidad-especie-valoracion",
    ),
)
_SOURCE_DIGESTS = {"aeat-dr-190-2025": "a7d1092f78620431812354e560a5146a3ae244e0aed69d9d58c353370ba0134d"}
_CONTEXT_FIELDS = (
    ("modelo-190-perc-clave", 78, 1),
    ("modelo-190-perc-subclave", 79, 2),
    ("modelo-190-perc-ejercicio-devengo", 148, 4),
    ("modelo-190-perc-retenciones-practicadas", 95, 13),
    ("modelo-190-perc-ingresos-a-cuenta", 122, 13),
    ("modelo-190-perc-incapacidad-dineraria-retenciones", 269, 13),
    ("modelo-190-perc-incapacidad-especie-ingresos-a-cuenta", 296, 13),
)


def _record() -> ExportRecordDefinition:
    fields = []
    for (sign_offset, amount_offset), (sign_name, amount_name, binding) in zip(_PAIRS, _NAMES, strict=True):
        for field_id, offset, length, policy in (
            (f"modelo-190-perc-signo-{sign_name}", sign_offset, 1, ExportValuePolicy.SIGNED_COMPONENT_SIGN),
            (f"modelo-190-perc-{amount_name}", amount_offset, 13, ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE),
        ):
            fields.append(
                ExportFieldDefinition.model_construct(
                    id=field_id,
                    offset=offset,
                    length=length,
                    kind=CasillaFieldKind.BINDING,
                    binding=binding,
                    value_policy=policy,
                    source_refs=("aeat-dr-190-2025",),
                )
            )
    fields.extend(
        ExportFieldDefinition.model_construct(
            id=field_id, offset=offset, length=length, source_refs=("aeat-dr-190-2025",)
        )
        for field_id, offset, length in _CONTEXT_FIELDS
    )
    return ExportRecordDefinition.model_construct(id="modelo-190-perceptor", fields=tuple(fields))


def _wire(*, key: str = "A", subkey: str = "01", devengo: str = "2024", filing: str = "2025") -> list[str]:
    wire = list(" " * 500)
    wire[4:8], wire[77], wire[78:80], wire[147:151] = list(filing), key, list(subkey), list(devengo)
    for offset in (82, 109, 256, 283, 95, 122, 269, 296):
        wire[offset - 1 : offset + 12] = list("0" * 13)
    return wire


def test_negative_reintegro_requires_prior_devengo_and_zero_withholding() -> None:
    record = _record()
    wire = _wire()
    wire[80], wire[81:94] = "N", list("0" * 12 + "1")
    require_m190_signed_reintegro_context(record, "".join(wire), source_digests=_SOURCE_DIGESTS)
    for changed in (_wire(devengo="2025"), _wire(devengo="0000"), _wire(devengo="2024")):
        changed[80], changed[81:94] = "N", list("0" * 12 + "1")
        if changed[147:151] == list("2024"):
            changed[94:107] = list("0" * 12 + "1")
        with pytest.raises(FilingExportValidationError, match="earlier devengo year and zero"):
            require_m190_signed_reintegro_context(record, "".join(changed), source_digests=_SOURCE_DIGESTS)


def test_incapacity_key_conditions_apply_to_positive_and_negative_amounts() -> None:
    record = _record()
    monetary = _wire(key="B", subkey="01")
    monetary[254], monetary[255:268] = "N", list("0" * 12 + "1")
    require_m190_signed_reintegro_context(record, "".join(monetary), source_digests=_SOURCE_DIGESTS)
    for key, subkey in (("B", "02"), ("C", "01")):
        bad = _wire(key=key, subkey=subkey)
        bad[255:268] = list("0" * 12 + "1")
        with pytest.raises(FilingExportValidationError, match=r"key A or B\.01"):
            require_m190_signed_reintegro_context(record, "".join(bad), source_digests=_SOURCE_DIGESTS)
    in_kind = _wire(key="B", subkey="01")
    in_kind[282:295] = list("0" * 12 + "1")
    with pytest.raises(FilingExportValidationError, match="requires key A"):
        require_m190_signed_reintegro_context(record, "".join(in_kind), source_digests=_SOURCE_DIGESTS)


def test_signed_context_refuses_stale_source_and_inconsistent_pair() -> None:
    record = _record()
    wire = "".join(_wire())
    with pytest.raises(FilingExportValidationError, match="reviewed source digest"):
        require_m190_signed_reintegro_context(record, wire, source_digests={"aeat-dr-190-2025": "0" * 64})
    changed = record.model_copy(
        update={"fields": (record.fields[0].model_copy(update={"binding": "other"}), *record.fields[1:])}
    )
    with pytest.raises(FilingExportValidationError, match="declaration is incomplete or changed"):
        require_m190_signed_reintegro_context(changed, wire, source_digests=_SOURCE_DIGESTS)
    negative_zero = _wire()
    negative_zero[80] = "N"
    with pytest.raises(FilingExportValidationError, match="nonzero magnitude"):
        require_m190_signed_reintegro_context(record, "".join(negative_zero), source_digests=_SOURCE_DIGESTS)
