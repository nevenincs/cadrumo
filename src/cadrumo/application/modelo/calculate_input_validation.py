"""Calculation input validation and diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, NoReturn

from ...core.casilla_id import CasillaId
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.calculations.registry.binding_selector_utils import boolean_binding_encoded_values
from ...domain.calculations.registry.casilla_membership import (
    casilla_noncanonical_reference_targets,
    declared_casilla_ids,
)
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.irnr_tipo_renta import (
    m210_fetch_gated_tipo_renta_codes,
    m210_tipo_renta_code_projection,
)
from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ...domain.calculations.registry.schema_scalars import (
    validate_registry_text_scalar,
)
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.row_models import (
    Modelo184MemberRow,
    Modelo184ShareSumError,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
    ModeloDetailRow,
    validate_m184_member_share_sum,
    validate_m349_country_prefix_context,
    validate_m349_nif_format,
)
from ...domain.modelos.work_unit import WorkUnit
from .action_errors import ModeloPreconditionErrorMixin

# Intra-package reuse of a sibling module's cap, permitted by the architecture
# rule; only cross-package private reaches are barred, and that gate is separate.
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


class ModeloCalculateInputError(ModeloError):
    """Raised when operator-supplied modelo calculation inputs are invalid."""


class ModeloCalculateDetailRowsError(ModeloCalculateInputError):
    """Raised when detail rows violate modelo calculation preconditions."""


class ModeloCalculateDecimalInputError(ModeloPreconditionErrorMixin, ModeloCalculateInputError):
    """Raised when a calculation override value is not decimal-shaped."""


class ModeloCalculateTextInputError(ModeloCalculateInputError):
    """Raised when a ``--casilla`` override targets a text casilla with a value its type refuses."""


class ModeloCalculateCasillaInputError(ModeloPreconditionErrorMixin, ModeloCalculateInputError):
    """Raised when a casilla override cannot be resolved for the active revision."""


class ModeloCalculateBindingInputError(ModeloPreconditionErrorMixin, ModeloCalculateInputError):
    """Raised when a ``--binding`` override cannot be resolved for the active revision."""


class ModeloCalculateRelationInputError(ModeloCalculateInputError):
    """Raised when a ``--relation`` override cannot be resolved for the active revision."""


class ModeloCalculateShortcutInputError(ModeloCalculateInputError):
    """Raised when grouped calculation shortcut inputs are incomplete."""


class ModeloCalculateSemanticRoleError(ModeloCalculateInputError):
    """Raised when a registry revision lacks a semantic-role target required by a shortcut."""


def validate_m349_detail_rows(
    rows: tuple[ModeloDetailRow, ...], *, work_unit: WorkUnit, operation: PinnedAuthorityOperation
) -> None:
    """Validate NIF and country context inside the original governed-facts scope."""
    with validating_governed_facts(operation):
        for row in rows:
            if isinstance(row, (Modelo349OperadorRow, Modelo349RectificacionRow)) and not validate_m349_nif_format(
                row.nif_comunitario, row.codigo_pais
            ):
                raise ModeloCalculateDetailRowsError(
                    context={"nif": row.nif_comunitario, "pais": row.codigo_pais},
                    translated_message="application.modelo.errors.calculate_m349_invalid_nif",
                )
            if isinstance(row, Modelo349OperadorRow):
                validate_m349_country_prefix_context(
                    country_code=row.codigo_pais,
                    clave_operacion=row.clave_operacion,
                    filing_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                )
            elif isinstance(row, Modelo349RectificacionRow):
                validate_m349_country_prefix_context(
                    country_code=row.codigo_pais,
                    clave_operacion=row.clave_operacion,
                    filing_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                    is_rectification=True,
                    rectified_year=int(row.ejercicio),
                    rectified_period=row.periodo,
                )


def validate_detail_rows(
    rows: tuple[ModeloDetailRow, ...], *, work_unit: WorkUnit, operation: PinnedAuthorityOperation
) -> None:
    """Validate model-specific detail rows against the pinned operation."""
    member_rows = [row for row in rows if isinstance(row, Modelo184MemberRow)]
    try:
        validate_m184_member_share_sum(member_rows)
    except Modelo184ShareSumError as exc:
        raise ModeloCalculateDetailRowsError(
            context={"total": str(exc.total), "count": str(exc.count)},
            translated_message="application.modelo.errors.calculate_m184_share_sum_invalid",
        ) from exc

    if str(work_unit.modelo) != form_for_role("iva.intracommunity_summary"):
        return
    validate_m349_detail_rows(rows, work_unit=work_unit, operation=operation)


def decimal(raw_value: str, *, flag: str, key: str) -> Decimal:
    """Validate an operator-supplied calculation input against the canonical grammar.

    The fractional part is deliberately uncapped: a casilla, relation, or
    binding value may legitimately carry sub-cent precision (the AEAT
    fixed-width encoder rounds such a value to cents with ``ROUND_HALF_UP`` per
    the AEAT Instrucciones), so a two-digit cap here would refuse a value the
    export layer is built to accept. What the grammar does refuse is text whose
    numeric meaning is not what it appears: scientific notation, a leading
    ``+``, a comma decimal separator, embedded whitespace, and
    ``NaN``/``Infinity`` — all of which a bare :class:`~decimal.Decimal` call
    silently accepted.
    """
    parsed = try_parse_canonical_decimal(raw_value)
    if parsed is None:
        raise ModeloCalculateDecimalInputError(
            context={"flag": flag, "key": key, "value": raw_value},
            translated_message="application.modelo.errors.calculate_decimal_input_invalid",
        )
    return parsed


def decimal_binding_value(
    raw_value: str,
    binding: BindingDefinition,
    *,
    work_unit: WorkUnit | None = None,
) -> Decimal:
    """Parse a ``--binding`` decimal value, teaching the accepted encoding on failure.

    For a boolean-typed decimal-channel binding (the Modelo 100 estimación-directa
    modality flag), a non-numeric value such as ``false`` otherwise produces the
    opaque "is not a decimal" error. This raises an instructive refusal that names
    the accepted ``0`` / ``1`` encoding and what each value means, derived from the
    binding's boolean selector rather than a per-form hardcoded table.

    Conformance is judged by the same canonical grammar :func:`decimal` applies,
    so a value whose numeric meaning is not what it appears (scientific
    notation, a leading ``+``, a comma decimal) refuses here too instead of
    being silently coerced.
    """
    encoded_options = boolean_binding_encoded_values(binding)
    parsed = try_parse_canonical_decimal(raw_value)
    if parsed is None:
        if encoded_options:
            mapping = ", ".join(
                f"{option.encoded_value} ({'true' if option.boolean_meaning else 'false'} = "
                f"registry value {option.registry_value!r})"
                for option in encoded_options
            )
            accepted = ", ".join(option.encoded_value for option in encoded_options)
            raise ModeloCalculateDecimalInputError(
                context={
                    "flag": "--binding",
                    "key": binding.id,
                    "value": raw_value,
                    "accepted": accepted,
                    "mapping": mapping,
                },
                translated_message="application.modelo.errors.calculate_boolean_binding_encoding_invalid",
                precondition_failure=caller_override_failure(
                    work_unit,
                    scenario_id="modelo.work.calculate.caller_overrides.boolean_binding_encoding_invalid",
                    evidence_id=_BINDING_OVERRIDE_EVIDENCE_ID,
                    facts={"binding_id": binding.id, "accepted_encoded_values": accepted},
                    with_registry_listing=True,
                ),
            )
        raise ModeloCalculateDecimalInputError(
            context={"flag": "--binding", "key": binding.id, "value": raw_value},
            translated_message="application.modelo.errors.calculate_decimal_input_invalid",
        )
    return parsed


def typed_text_value(raw_value: str, *, key: str, casilla_def: CasillaDefinition) -> str:
    """Canonicalise a ``--casilla`` value through its casilla's declared text-scalar validator.

    The text channel carries the whole registry string family (``period_code``,
    ``nif``, ``iban``, ``country_code``, ... — every ``data_type`` whose
    :func:`cadrumo.domain.calculations.registry.schema_scalars.registry_scalar_value_type` is
    ``"str"``), not only bare ``text``. Each family member declares its own
    validator, so running it here keeps the CLI the operator's first
    instructive surface: a malformed ``period_code`` is refused by name at the
    boundary instead of surfacing as a generic registry error deeper in the
    calculation pipeline. The canonical form the validator returns is what
    reaches the engine, exactly as
    :func:`cadrumo.domain.calculations.registry.schema_scalars.validate_registry_text_scalar`
    would produce there.
    """
    value = text_value(raw_value, key=key)
    try:
        return validate_registry_text_scalar(
            casilla_def.data_type,
            value,
            tax_id_format=runtime_tax_id_format() if casilla_def.data_type == "nif" else None,
        )
    except RegistryValidationError as exc:
        context = {"key": key, "data_type": casilla_def.data_type}
        if casilla_def.data_type != "iban":
            context["value"] = raw_value
        raise ModeloCalculateTextInputError(
            context=context,
            translated_message="application.modelo.errors.calculate_typed_text_input_invalid",
        ) from exc


def text_value(raw_value: str, *, key: str) -> str:
    """Validate that a ``--casilla`` value routed to the text channel is a non-empty string.

    Mirrors the registry engine's own
    :func:`cadrumo.domain.calculations.registry.formula_text_inputs.validated_text_input_casilla_ids`
    non-empty-string contract at the CLI boundary, so an empty text value
    refuses loudly here instead of surfacing a generic registry error deeper in
    the calculation pipeline. Callers routing a value to a declared text-scalar
    family go through :func:`typed_text_value`, which adds that family's own
    validator on top of this contract.
    """
    value = raw_value.strip()
    if not value:
        raise ModeloCalculateTextInputError(
            context={"key": key, "value": raw_value},
            translated_message="application.modelo.errors.calculate_text_input_empty",
        )
    return value


def projected_m210_tipo_renta_code(official_code: str) -> str:
    """Project a validated Modelo 210 official ``tipo_renta`` code to its rate concept.

    The generic ``--casilla key=value`` surface cannot render a static Typer
    ``Choice`` for one casilla's value, so this is the sanctioned
    architecture-boundaries fallback: a registry-driven refusal that LISTS the
    accepted declared codes and names a fetch-gated code as fetch-gated rather
    than "invalid". The fetch-gated codes
    (the registry-declared fetch-gated code set) are real AEAT
    HOJA-INFORMATIVA-210 codes whose rate is not yet grounded, so an operator
    entering code ``08`` is told it is not yet fileable, never that it is
    invalid. The accepted set is the declared code axis
    (the registry-projected code map), kept in parity with the selected
    detail catalogue by the governed-fact resolver.

    On acceptance the operator-entered official code is PROJECTED to its
    :class:`~cadrumo.core.irnr.TipoRentaIrnr` rate-concept token — the value the engine
    already keys the baseline rate table and treaty overrides on — so the
    operator declares the code the form asks for while the rate machinery keeps
    its conceptual key. (Codes that share a concept, e.g. arrendamiento ``01``
    and empresariales ``03`` both ``general``, collapse to that concept here;
    per-code form-fidelity display belongs to the fetch-gated full-casilla
    schema.)
    """
    return m210_tipo_renta_code_projection()[official_code].value


def validated_m210_official_tipo_renta_code(raw_value: str, *, key: str) -> str:
    """Return the validated raw M210 code without collapsing its identity.

    The formula engine receives the conceptual rate token, while the ledger
    source resolver and persisted calculation revision retain this official
    code. Keeping both values prevents the many-to-one rate projection from
    turning distinct declarations such as codes ``01`` and ``03`` into the
    same ledger-selection key.
    """
    value = text_value(raw_value, key=key)
    projection = m210_tipo_renta_code_projection()
    fetch_gated_codes = m210_fetch_gated_tipo_renta_codes()
    if value in projection:
        return value
    accepted = ", ".join(sorted(projection))
    if value in fetch_gated_codes:
        raise ModeloCalculateTextInputError(
            context={"key": key, "value": value, "accepted": accepted},
            translated_message="application.modelo.errors.calculate_m210_tipo_renta_fetch_gated",
        )
    fetch_gated = ", ".join(sorted(fetch_gated_codes))
    raise ModeloCalculateTextInputError(
        context={"key": key, "value": value, "accepted": accepted, "fetch_gated": fetch_gated},
        translated_message="application.modelo.errors.calculate_m210_tipo_renta_unknown",
    )


def refuse_row_field_casilla_override(key: CasillaId, *, records: tuple[str, ...], work_unit: WorkUnit) -> NoReturn:
    """Refuse a casilla an export record fills once per detail row, naming those records."""
    raise ModeloCalculateCasillaInputError(
        context={"casilla_ids": key, "record_ids": ",".join(records)},
        translated_message="errors.calc.row_field_template_supplied_as_input",
        precondition_failure=caller_override_failure(
            work_unit,
            scenario_id="modelo.work.calculate.caller_overrides.row_field_casilla_refused",
            evidence_id=_CASILLA_OVERRIDE_EVIDENCE_ID,
            facts={"casilla_key": key},
            with_registry_listing=False,
        ),
    )


_CALCULATE_SUBJECT_LEAF = "modelo.work.calculate"


_BINDING_OVERRIDE_EVIDENCE_ID = "modelo.work.calculate.binding_override"


_CASILLA_OVERRIDE_EVIDENCE_ID = "modelo.work.calculate.casilla_override"


def caller_override_failure(
    work_unit: WorkUnit | None,
    *,
    scenario_id: str,
    evidence_id: str,
    facts: Mapping[str, str | int],
    with_registry_listing: bool,
) -> ModeloPreconditionFailure | None:
    """Build the declared calculate refusal for one caller override, when the target is known.

    Only the calculate verb supplies its work unit; the preview projection and
    the edit path share the binding validators without being that verb, so
    they get no ``modelo.work.calculate`` verdict. Every actionable
    caller-override scenario recovers through a registry listing addressed by
    the work unit's modelo, year and period.
    """
    if work_unit is None:
        return None
    listing_arguments: Mapping[str, str | int] = {
        "modelo": str(work_unit.modelo),
        "year": work_unit.filing_year,
        "period": work_unit.period.registry_token,
    }
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=_CALCULATE_SUBJECT_LEAF,
        scenario_id=scenario_id,
        evidence_id=evidence_id,
        evidence_values={"work_unit_id": work_unit.work_unit_id, **listing_arguments, **facts},
        provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
        action_argument_values=listing_arguments if with_registry_listing else None,
    )


def validated_binding_input_channel(
    key: str,
    revision: ModeloRevision,
    known_binding_ids: set[BindingId],
    enum_channel_ids: frozenset[BindingId],
    *,
    work_unit: WorkUnit | None = None,
) -> tuple[BindingId, Literal["decimal", "enum"]]:
    """Return the registry-declared engine channel for a ``--binding`` override.

    Routes the override by the binding's *declared* input channel, not by
    parse success: a binding the revision's formulas consume as a string
    enum key (``enum_consumed_binding_ids``) is an ``"enum"`` channel and
    its override is carried verbatim; every other declared binding is a
    ``"decimal"`` channel whose override the caller coerces with
    :func:`decimal` (so a malformed numeric value REFUSES instead of
    silently reclassifying as an enum string). An unknown binding id
    refuses with the accepted set, per ``no-silent-under-declaration``
    and the CLI-Choice-hint mandate.

    Takes ``revision`` as a :class:`ModeloRevision`.
    """
    if key not in known_binding_ids:
        accepted = ", ".join(sorted(known_binding_ids))
        raise ModeloCalculateBindingInputError(
            context={"key": key, "accepted": accepted},
            translated_message="application.modelo.errors.calculate_binding_unknown",
            precondition_failure=caller_override_failure(
                work_unit,
                scenario_id="modelo.work.calculate.caller_overrides.binding_unknown",
                evidence_id=_BINDING_OVERRIDE_EVIDENCE_ID,
                facts={
                    "binding_id": key,
                    "revision_id": revision.id,
                    "declared_binding_count": len(known_binding_ids),
                },
                with_registry_listing=True,
            ),
        )
    return key, "enum" if key in enum_channel_ids else "decimal"


def validated_relation_id(key: str, known_relation_ids: set[RelationId]) -> RelationId:
    """Validate a relation identifier against the revision declarations."""
    if key in known_relation_ids:
        return key
    accepted = ", ".join(sorted(known_relation_ids))
    raise ModeloCalculateRelationInputError(
        context={"key": key, "accepted": accepted},
        translated_message="application.modelo.errors.calculate_relation_unknown",
    )


def validated_canonical_casilla_id(key: str, revision: ModeloRevision, *, work_unit: WorkUnit) -> CasillaId:
    """Validate a canonical casilla identifier against the revision.

    Takes ``revision`` as a :class:`ModeloRevision`.
    """
    known_ids = declared_casilla_ids(revision)
    if key in known_ids:
        return key

    noncanonical_targets = casilla_noncanonical_reference_targets(revision, key)
    if noncanonical_targets:
        accepted = ", ".join(noncanonical_targets)
        if len(noncanonical_targets) > 1:
            raise ModeloCalculateCasillaInputError(
                context={"key": key, "accepted": accepted},
                translated_message="application.modelo.errors.calculate_casilla_noncanonical_ambiguous",
            )
        raise ModeloCalculateCasillaInputError(
            context={"key": key, "accepted": accepted},
            translated_message="application.modelo.errors.calculate_casilla_noncanonical_refused",
        )

    shown = sorted(known_ids)[:20]
    accepted_hint = ", ".join(shown)
    if len(known_ids) > len(shown):
        accepted_hint += ", ..."
    raise ModeloCalculateCasillaInputError(
        context={"key": key, "accepted": accepted_hint},
        translated_message="application.modelo.errors.calculate_casilla_unknown",
        precondition_failure=caller_override_failure(
            work_unit,
            scenario_id="modelo.work.calculate.caller_overrides.casilla_unknown",
            evidence_id=_CASILLA_OVERRIDE_EVIDENCE_ID,
            facts={
                "casilla_key": key,
                "revision_id": revision.id,
                "declared_casilla_count": len(known_ids),
            },
            with_registry_listing=True,
        ),
    )
