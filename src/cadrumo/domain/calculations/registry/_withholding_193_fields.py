"""Modelo 193 withholding-field validation and completion rules."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from .errors import RegistryValidationError
from .withholding_bindings import IDENTIFICATION_BLOCK_CLAVES


def require_and_stringify_field(
    row: Mapping[str, Decimal | str],
    finalised: dict[str, Decimal | str],
    *,
    field: str,
    required_fields: frozenset[str],
    perceptor_tax_id: str,
    clave: str,
    requirement_description: str,
) -> None:
    """Require an always-recorded field and project it to record text."""
    if field not in required_fields:
        return
    value = row.get(field)
    if value is None:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} require "
            f"{field} {requirement_description}",
        )
    finalised[field] = str(value)


def validate_193_scoped_value(
    *,
    field: str,
    value: Decimal | str | None,
    in_scope: bool,
    require_when_in_scope: bool,
    require_even_for_naturaleza_s: bool,
    naturaleza_s: bool,
    perceptor_tax_id: str,
    clave: str,
    scope_description: str,
    requirement_description: str,
) -> None:
    """Validate the scope and requiredness of one Modelo 193 field."""
    if value is not None and not in_scope:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry {field}, {scope_description}",
        )
    if value is None and require_when_in_scope and in_scope and (require_even_for_naturaleza_s or not naturaleza_s):
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} require "
            f"{field} {requirement_description}: no observation carries it",
        )


def scoped_field_output(
    value: Decimal | str | None,
    *,
    naturaleza_s: bool,
    naturaleza_s_default: str | None,
    default: str,
) -> Decimal | str:
    """Select the design content after scope validation and the S cascade."""
    if naturaleza_s and naturaleza_s_default is not None:
        return naturaleza_s_default
    if value is not None:
        return value
    return default


def finalise_193_scoped_field(
    row: Mapping[str, Decimal | str],
    finalised: dict[str, Decimal | str],
    *,
    field: str,
    required_fields: frozenset[str],
    in_scope: bool,
    require_when_in_scope: bool,
    naturaleza_s: bool,
    require_even_for_naturaleza_s: bool = False,
    naturaleza_s_default: str | None,
    default: str,
    stringify: bool,
    perceptor_tax_id: str,
    clave: str,
    scope_description: str,
    requirement_description: str,
) -> None:
    """Validate, cascade, and serialise one Modelo 193 scoped field."""
    if field not in required_fields:
        return
    value = row.get(field)
    validate_193_scoped_value(
        field=field,
        value=value,
        in_scope=in_scope,
        require_when_in_scope=require_when_in_scope,
        require_even_for_naturaleza_s=require_even_for_naturaleza_s,
        naturaleza_s=naturaleza_s,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description=scope_description,
        requirement_description=requirement_description,
    )
    output = scoped_field_output(
        value,
        naturaleza_s=naturaleza_s,
        naturaleza_s_default=naturaleza_s_default,
        default=default,
    )
    finalised[field] = str(output) if stringify else output


def finalise_193_emisor_field(
    row: Mapping[str, Decimal | str],
    finalised: dict[str, Decimal | str],
    *,
    required_fields: frozenset[str],
    clave_abd: bool,
    naturaleza_s: bool,
    clave: str,
    perceptor_tax_id: str,
) -> None:
    """Apply the Modelo 193 issuer-code rules, including clave-code coupling."""
    field = "codigo_emisor"
    if field not in required_fields:
        return
    emisor = row.get(field)
    validate_193_scoped_value(
        field=field,
        value=emisor,
        in_scope=clave_abd,
        require_when_in_scope=False,
        require_even_for_naturaleza_s=False,
        naturaleza_s=naturaleza_s,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description="which design positions 80-91 declare only for claves A, B and D",
        requirement_description="",
    )
    if emisor is not None and row.get("clave_codigo") == 2:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry "
            "codigo_emisor with clave_codigo 2, which design positions 80-91 declare empty then",
        )
    if emisor is None and clave_abd and not naturaleza_s and row.get("clave_codigo") in (1, 3, 4):
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} require "
            "codigo_emisor (design positions 80-91, the issuer's NIF for clave codigo 1/4, "
            "ZXX country code for 3): no observation carries it",
        )
    finalised[field] = " " * 12 if naturaleza_s else emisor if emisor is not None else " " * 12


def finalise_193_primary_fields(
    row: Mapping[str, Decimal | str],
    *,
    required_fields: frozenset[str],
    clave: str,
    subclave: str,
    perceptor_tax_id: str,
    finalised: dict[str, Decimal | str],
) -> None:
    clave_abd = clave in IDENTIFICATION_BLOCK_CLAVES
    naturaleza_s = row.get("naturaleza_declarante") == "S"

    # ---- Modelo 193 perceptor-record completion ----
    # The design's claves A/B/D block, and the naturaleza-del-declarante 'S'
    # cascade that overrides it: under 'S' the A/B/D identification block
    # writes the design's own no-content and a present fact contradicts it.
    require_and_stringify_field(
        row,
        finalised,
        field="naturaleza",
        required_fields=required_fields,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        requirement_description="(design position 93): the per-clave subclave is always recorded",
    )
    require_and_stringify_field(
        row,
        finalised,
        field="tipo_percepcion",
        required_fields=required_fields,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        requirement_description="(design position 122): 1 dinerarias / 2 en especie is always recorded",
    )
    finalise_193_scoped_field(
        row,
        finalised,
        field="perceptor_mediador_flag",
        required_fields=required_fields,
        in_scope=clave_abd,
        require_when_in_scope=False,
        naturaleza_s=naturaleza_s,
        naturaleza_s_default=" ",
        default=" ",
        stringify=False,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description="which design position 76 declares only for claves A, B and D",
        requirement_description="",
    )
    finalise_193_scoped_field(
        row,
        finalised,
        field="clave_codigo",
        required_fields=required_fields,
        in_scope=clave_abd,
        require_when_in_scope=True,
        naturaleza_s=naturaleza_s,
        naturaleza_s_default="0",
        default="0",
        stringify=True,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description="which design position 79 declares only for claves A, B and D",
        requirement_description="(design position 79, clave 4 the general case)",
    )
    finalise_193_emisor_field(
        row,
        finalised,
        required_fields=required_fields,
        clave_abd=clave_abd,
        naturaleza_s=naturaleza_s,
        clave=clave,
        perceptor_tax_id=perceptor_tax_id,
    )
    finalise_193_scoped_field(
        row,
        finalised,
        field="pago",
        required_fields=required_fields,
        in_scope=clave_abd,
        require_when_in_scope=True,
        naturaleza_s=naturaleza_s,
        naturaleza_s_default="0",
        default="0",
        stringify=True,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description="which design position 95 declares only for claves A, B and D",
        requirement_description="(design position 95)",
    )
    finalise_193_scoped_field(
        row,
        finalised,
        field="tipo_codigo",
        required_fields=required_fields,
        in_scope=clave_abd,
        require_when_in_scope=True,
        naturaleza_s=naturaleza_s,
        naturaleza_s_default=" ",
        default=" ",
        stringify=False,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description="which design position 96 declares only for claves A, B and D",
        requirement_description="(design position 96)",
    )
    finalise_193_scoped_field(
        row,
        finalised,
        field="codigo_cuenta",
        required_fields=required_fields,
        in_scope=clave_abd,
        require_when_in_scope=False,
        naturaleza_s=naturaleza_s,
        naturaleza_s_default=" " * 20,
        default=" " * 20,
        stringify=False,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description="which design positions 97-116 declare only for claves A, B and D",
        requirement_description="",
    )
    finalise_193_scoped_field(
        row,
        finalised,
        field="pendiente_flag",
        required_fields=required_fields,
        in_scope=clave_abd,
        require_when_in_scope=False,
        naturaleza_s=naturaleza_s,
        naturaleza_s_default=None,
        default=" ",
        stringify=False,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description="which design position 117 declares only for claves A, B and D",
        requirement_description="",
    )


def validate_193_restricted_amount(
    *,
    field: str,
    value: Decimal | str,
    required_fields: frozenset[str],
    in_scope: bool,
    naturaleza_s: bool,
    perceptor_tax_id: str,
    clave: str,
    scope_description: str,
    cascade_description: str,
) -> None:
    """Validate one Modelo 193 amount's scope and naturaleza-S cascade."""
    if field not in required_fields or value == 0:
        return
    if not in_scope:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry {field}, {scope_description}",
        )
    if naturaleza_s:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry {field} {cascade_description}",
        )


def validate_193_isin_field(
    *,
    row: Mapping[str, Decimal | str],
    isin: Decimal | str | None,
    clave_abd: bool,
    naturaleza_s: bool,
    clave: str,
    perceptor_tax_id: str,
) -> None:
    """Validate the Modelo 193 ISIN coupling before projecting its content."""
    clave_codigo = row.get("clave_codigo")
    if isin is not None and clave_codigo not in (2, 4):
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry "
            "isin_code while clave_codigo is not 2 or 4, which design positions 193-204 "
            "declare as the ISIN's own scope",
        )
    if (
        isin is None
        and clave_abd
        and not naturaleza_s
        and clave_codigo in (2, 4)
        and clave == "A"
        and row.get("clave_mercado") == "A"
    ):
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave A require "
            "isin_code (design positions 193-204: obligatory when clave mercado is A): "
            "no observation carries it",
        )


def finalise_193_isin_field(
    row: Mapping[str, Decimal | str],
    finalised: dict[str, Decimal | str],
    *,
    required_fields: frozenset[str],
    clave_abd: bool,
    naturaleza_s: bool,
    clave: str,
    perceptor_tax_id: str,
) -> None:
    """Validate the Modelo 193 ISIN coupling and project its no-content."""
    field = "isin_code"
    if field not in required_fields:
        return
    isin = row.get(field)
    validate_193_isin_field(
        row=row,
        isin=isin,
        clave_abd=clave_abd,
        naturaleza_s=naturaleza_s,
        clave=clave,
        perceptor_tax_id=perceptor_tax_id,
    )
    finalised[field] = " " * 12 if naturaleza_s else isin if isin is not None else " " * 12


def finalise_193_loan_date(
    row: Mapping[str, Decimal | str],
    finalised: dict[str, Decimal | str],
    *,
    field: str,
    required_fields: frozenset[str],
    naturaleza_s: bool,
    clave: str,
    perceptor_tax_id: str,
    positions: str,
) -> None:
    """Validate and serialise one loan date, including its tipo-codigo scope."""
    if field not in required_fields:
        return
    value = row.get(field)
    if value is not None and row.get("tipo_codigo") != "P":
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry "
            f"{field} while tipo_codigo is not 'P', which design positions {positions} "
            "declare exclusively for prestamo de valores",
        )
    finalised[field] = "0" * 8 if naturaleza_s else value if value is not None else "0" * 8


def finalise_193_sequence_number(
    row: Mapping[str, Decimal | str],
    finalised: dict[str, Decimal | str],
    *,
    required_fields: frozenset[str],
    row_number: int,
    perceptor_tax_id: str,
) -> None:
    """Validate a supplied Modelo 193 order and write the derived sequence."""
    if "numero_orden" not in required_fields:
        return
    supplied_order = row.get("numero_orden")
    if supplied_order is not None and int(supplied_order) != row_number:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} carry numero_orden "
            f"{supplied_order!r}, which disagrees with the design's sequential record "
            f"number {row_number}",
        )
    finalised["numero_orden"] = str(row_number)


def finalise_193_instrument_fields(
    row: Mapping[str, Decimal | str],
    *,
    required_fields: frozenset[str],
    clave: str,
    subclave: str,
    perceptor_tax_id: str,
    finalised: dict[str, Decimal | str],
    row_number: int,
) -> None:
    clave_abd = clave in IDENTIFICATION_BLOCK_CLAVES
    naturaleza_s = row.get("naturaleza_declarante") == "S"
    for field, value, in_scope, scope_description, cascade_description in (
        (
            "penalizaciones",
            row["penalizaciones"],
            clave in {"B", "D"},
            "which design positions 182-192 declare only for claves B and D",
            "while naturaleza del declarante is 'S', which the design's cascade declares a ceros",
        ),
        (
            "compensaciones",
            row["compensaciones"],
            row.get("tipo_codigo") == "P",
            "which design positions 225-236 declare exclusively for prestamo de valores",
            "while naturaleza del declarante is 'S', which the design's cascade declares a ceros",
        ),
        (
            "garantias",
            row["garantias"],
            row.get("tipo_codigo") == "P",
            "which design positions 237-248 declare exclusively for prestamo de valores",
            "while naturaleza del declarante is 'S', which the design's cascade declares a ceros",
        ),
    ):
        validate_193_restricted_amount(
            field=field,
            value=value,
            required_fields=required_fields,
            in_scope=in_scope,
            naturaleza_s=naturaleza_s,
            perceptor_tax_id=perceptor_tax_id,
            clave=clave,
            scope_description=scope_description,
            cascade_description=cascade_description,
        )
    finalise_193_isin_field(
        row,
        finalised,
        required_fields=required_fields,
        clave_abd=clave_abd,
        naturaleza_s=naturaleza_s,
        clave=clave,
        perceptor_tax_id=perceptor_tax_id,
    )
    finalise_193_scoped_field(
        row,
        finalised,
        field="naturaleza_declarante",
        required_fields=required_fields,
        in_scope=True,
        require_when_in_scope=False,
        naturaleza_s=naturaleza_s,
        naturaleza_s_default=None,
        default=" ",
        stringify=False,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description="",
        requirement_description="",
    )
    finalise_193_loan_date(
        row,
        finalised,
        field="fecha_inicio_prestamo",
        required_fields=required_fields,
        naturaleza_s=naturaleza_s,
        clave=clave,
        perceptor_tax_id=perceptor_tax_id,
        positions="209-216",
    )
    finalise_193_loan_date(
        row,
        finalised,
        field="fecha_vencimiento_prestamo",
        required_fields=required_fields,
        naturaleza_s=naturaleza_s,
        clave=clave,
        perceptor_tax_id=perceptor_tax_id,
        positions="217-224",
    )
    finalise_193_scoped_field(
        row,
        finalised,
        field="nif_pagador_anterior",
        required_fields=required_fields,
        in_scope=clave_abd,
        require_when_in_scope=False,
        naturaleza_s=naturaleza_s,
        naturaleza_s_default=None,
        default=" " * 9,
        stringify=False,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description="which design positions 322-330 declare only for claves A, B and D",
        requirement_description="",
    )
    finalise_193_scoped_field(
        row,
        finalised,
        field="fecha_devengo",
        required_fields=required_fields,
        in_scope=clave == "A",
        require_when_in_scope=False,
        naturaleza_s=naturaleza_s,
        naturaleza_s_default=None,
        default="0" * 8,
        stringify=False,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description="which design positions 331-338 declare only for clave A",
        requirement_description="",
    )
    finalise_193_scoped_field(
        row,
        finalised,
        field="clave_mercado",
        required_fields=required_fields,
        in_scope=clave_abd,
        require_when_in_scope=True,
        require_even_for_naturaleza_s=True,
        naturaleza_s=naturaleza_s,
        naturaleza_s_default=None,
        default=" ",
        stringify=False,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description="which design position 339 declares only for claves A, B and D",
        requirement_description="(design position 339)",
    )
    finalise_193_sequence_number(
        row,
        finalised,
        required_fields=required_fields,
        row_number=row_number,
        perceptor_tax_id=perceptor_tax_id,
    )
