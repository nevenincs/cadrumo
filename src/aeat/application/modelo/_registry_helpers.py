"""Registry lookup and verification helpers for modelo actions.

Use of :class:`CalculationRevision`, :class:`ModeloRevision`, :class:`RegistrySnapshot` for compliance.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import Period
from ...domain.calculations.registry import (
    CasillaId,
    InputKind,
    ModeloRevision,
    RegistrySnapshot,
    RegistryValidationError,
    VerificationPredicateDefinition,
    casilla_noncanonical_reference_targets,
    casillas_by_id,
    undeclared_casilla_ids,
    validated_casilla_id,
)
from ...domain.modelos._calculation_revision import CalculationRevision, derive_calculation_revision_id
from ._action_errors import (
    AmendmentOverrideCasillaError,
    AmendmentVerificationRefusedError,
    ExternalModeloImportError,
    StoredCalculationDriftError,
)
from ._registry_resources import (
    authority_via_resources,
    registry_root,
    reject_unknown_period_for_revision,
    reject_unknown_revision,
)

_NUMERIC_CASILLA_DATA_TYPES: frozenset[str] = frozenset({"decimal", "money", "integer", "ratio"})


def reject_incomplete_amendment_casillas(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    casilla_values: Mapping[CasillaId, Decimal],
) -> None:
    """Mirror the verify-modelo-revision required-manual gate on amend."""
    required_optional = required_input_casilla_ids_for_revision(modelo=modelo, filing_year=filing_year, period=period)
    if required_optional is None:
        raise AmendmentVerificationRefusedError(
            f"registry has no snapshot for modelo={modelo!r} filing_year={filing_year} "
            f"period={period.registry_token!r}; cannot verify amendment completeness",
            translated_message="application.modelo.errors.amendment_verification_refused_no_snapshot",
        )
    required, _ = required_optional
    missing = sorted(casilla_id for casilla_id in required if casilla_id not in casilla_values)
    if missing:
        raise AmendmentVerificationRefusedError(
            f"amendment is incomplete: required casilla id(s) {missing!r} are not present "
            f"in the corrected map for modelo={modelo!r} filing_year={filing_year} "
            f"period={period.registry_token!r}",
            translated_message="application.modelo.errors.amendment_verification_refused_missing_casillas",
        )


def validate_casilla_input_ids[CasillaKey, CasillaValue](
    revision: ModeloRevision,
    casilla_inputs: Mapping[CasillaKey, CasillaValue],
) -> dict[CasillaId, Decimal]:
    """Validate operator-supplied numeric input casillas against the revision.

    Use of :class:`ModeloRevision` for compliance.
    """
    if not casilla_inputs:
        return {}
    revision_casillas_by_id = casillas_by_id(revision)
    canonical_inputs: dict[CasillaId, CasillaValue] = {}
    malformed: list[str] = []
    for key, value in casilla_inputs.items():
        try:
            canonical_key = validated_casilla_id(key, surface="casilla input key")
        except ValueError:
            malformed.append(repr(key))
            continue
        canonical_inputs[canonical_key] = value
    if malformed:
        raise RegistryValidationError(
            f"casilla input keys must be canonical casilla.id values for revision {revision.id!r}; "
            f"malformed keys: {sorted(malformed)!r}",
            context={"casilla_ids": ",".join(sorted(malformed)), "revision_id": revision.id},
        )
    unknown = undeclared_casilla_ids(revision, canonical_inputs)
    if unknown:
        noncanonical, unknown_only = _noncanonical_casilla_reference_details(revision, unknown)
        if noncanonical:
            details = "; ".join(
                _format_noncanonical_casilla_reference(casilla_id, targets)
                for casilla_id, targets in sorted(noncanonical.items())
            )
            raise RegistryValidationError(
                f"casilla input keys must be canonical casilla.id values for revision {revision.id!r}; "
                f"non-canonical reference tokens are not accepted: {details}",
                context={"casilla_ids": ",".join(sorted(noncanonical)), "revision_id": revision.id},
            )
        raise RegistryValidationError(
            f"casilla input keys must be canonical casilla.id values for revision {revision.id!r}; "
            f"unknown casilla.id values: {unknown_only!r}",
            context={"casilla_ids": ",".join(unknown_only), "revision_id": revision.id},
        )
    non_decimal = sorted(
        casilla_id
        for casilla_id, value in canonical_inputs.items()
        if isinstance(value, bool) or not isinstance(value, Decimal)
    )
    if non_decimal:
        raise RegistryValidationError(
            f"casilla input values must be Decimal instances for revision {revision.id!r}; "
            f"non-Decimal casillas: {non_decimal!r}",
            context={
                "casilla_ids": ",".join(non_decimal),
                "revision_id": revision.id,
                "value_types": ",".join(type(canonical_inputs[casilla_id]).__name__ for casilla_id in non_decimal),
            },
        )
    non_numeric = sorted(
        casilla_id
        for casilla_id in canonical_inputs
        if revision_casillas_by_id[casilla_id].data_type not in _NUMERIC_CASILLA_DATA_TYPES
    )
    if non_numeric:
        details = "; ".join(
            f"{casilla_id}: data_type={revision_casillas_by_id[casilla_id].data_type!r} "
            f"({revision_casillas_by_id[casilla_id].label})"
            for casilla_id in non_numeric
        )
        raise RegistryValidationError(
            f"casilla inputs must target numeric casillas for revision {revision.id!r}; {details}",
            context={
                "casilla_ids": ",".join(non_numeric),
                "revision_id": revision.id,
                "data_types": ",".join(revision_casillas_by_id[casilla_id].data_type for casilla_id in non_numeric),
            },
        )
    return {casilla_id: value for casilla_id, value in canonical_inputs.items() if isinstance(value, Decimal)}


def _format_noncanonical_casilla_reference(token: str, targets: tuple[CasillaId, ...]) -> str:
    rendered_targets = ", ".join(targets)
    if len(targets) > 1:
        return f"{token!r} is ambiguous; candidate casilla.id values: {rendered_targets}"
    return f"{token!r} -> {rendered_targets}"


def _noncanonical_casilla_reference_details(
    revision: ModeloRevision,
    casilla_ids: tuple[CasillaId, ...],
) -> tuple[dict[CasillaId, tuple[CasillaId, ...]], tuple[CasillaId, ...]]:
    noncanonical = {
        casilla_id: targets
        for casilla_id in casilla_ids
        if (targets := casilla_noncanonical_reference_targets(revision, casilla_id))
    }
    unknown = tuple(casilla_id for casilla_id in casilla_ids if casilla_id not in noncanonical)
    return noncanonical, unknown


def reject_unknown_override_casillas[CasillaKey](
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    overrides: Mapping[CasillaKey, Decimal],
) -> dict[CasillaId, Decimal]:
    """Refuse override casilla ids the registry does not declare for the modelo / year / period."""
    if not overrides:
        return {}

    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        authority = authority_via_resources()
    except FileNotFoundError as exc:
        raise AmendmentOverrideCasillaError(
            translated_message="application.modelo.errors.amendment_registry_root_missing",
            context={"registry_root": registry_root()},
        ) from exc

    try:
        snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period.registry_token)
    except RegistrySnapshotError as exc:
        raise AmendmentOverrideCasillaError(
            translated_message="application.modelo.errors.amendment_registry_snapshot_unresolved",
            context={"modelo": modelo, "filing_year": filing_year, "period": period.registry_token},
        ) from exc

    malformed: list[str] = []
    canonical_overrides: dict[CasillaId, Decimal] = {}
    for casilla_id, value in overrides.items():
        try:
            canonical_overrides[validated_casilla_id(casilla_id, surface="amendment override casilla")] = value
        except ValueError:
            malformed.append(repr(casilla_id))
    if malformed:
        raise AmendmentOverrideCasillaError(
            translated_message="application.modelo.errors.amendment_unknown_casillas",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
                "casillas": sorted(malformed),
            },
        )
    unknown = undeclared_casilla_ids(snapshot.revision, canonical_overrides)
    if unknown:
        noncanonical, unknown_only = _noncanonical_casilla_reference_details(snapshot.revision, unknown)
        if noncanonical:
            details = "; ".join(
                _format_noncanonical_casilla_reference(casilla_id, targets)
                for casilla_id, targets in sorted(noncanonical.items())
            )
            raise AmendmentOverrideCasillaError(
                f"amendment override casillas must use canonical casilla.id values; "
                f"non-canonical reference tokens are not accepted: {details}",
                translated_message="application.modelo.errors.amendment_unknown_casillas",
                context={
                    "modelo": modelo,
                    "filing_year": filing_year,
                    "period": period.registry_token,
                    "casillas": sorted(noncanonical),
                },
            )
        raise AmendmentOverrideCasillaError(
            translated_message="application.modelo.errors.amendment_unknown_casillas",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
                "casillas": unknown_only,
            },
        )
    return canonical_overrides


def reject_unknown_import_casillas[CasillaKey](
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    casilla_values: Mapping[CasillaKey, Decimal],
) -> tuple[RegistrySnapshot, dict[CasillaId, Decimal]]:
    """Refuse imported casilla ids the registry does not declare and return the resolved :class:`RegistrySnapshot`."""
    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        authority = authority_via_resources()
    except FileNotFoundError as exc:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_registry_root_missing",
            context={"registry_root": registry_root()},
        ) from exc

    try:
        snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period.registry_token)
    except RegistrySnapshotError as exc:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_registry_snapshot_unresolved",
            context={"modelo": modelo, "filing_year": filing_year, "period": period.registry_token},
        ) from exc

    malformed: list[str] = []
    canonical_values: dict[CasillaId, Decimal] = {}
    for casilla_id, value in casilla_values.items():
        try:
            canonical_values[validated_casilla_id(casilla_id, surface="external import casilla")] = value
        except ValueError:
            malformed.append(repr(casilla_id))
    if malformed:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_unknown_casillas",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
                "casillas": sorted(malformed),
            },
        )
    unknown = undeclared_casilla_ids(snapshot.revision, canonical_values)
    if unknown:
        noncanonical, unknown_only = _noncanonical_casilla_reference_details(snapshot.revision, unknown)
        if noncanonical:
            details = "; ".join(
                _format_noncanonical_casilla_reference(casilla_id, targets)
                for casilla_id, targets in sorted(noncanonical.items())
            )
            raise ExternalModeloImportError(
                f"external import casillas must use canonical casilla.id values; "
                f"non-canonical reference tokens are not accepted: {details}",
                translated_message="application.modelo.errors.external_import_unknown_casillas",
                context={
                    "modelo": modelo,
                    "filing_year": filing_year,
                    "period": period.registry_token,
                    "casillas": sorted(noncanonical),
                },
            )
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_unknown_casillas",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
                "casillas": unknown_only,
            },
        )
    return snapshot, canonical_values


def required_input_casilla_ids_for_revision(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
) -> tuple[tuple[CasillaId, ...], tuple[CasillaId, ...]] | None:
    """Resolve the registry's required and informational input casilla ids."""
    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        authority = authority_via_resources()
    except FileNotFoundError:
        return None

    try:
        snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period.registry_token)
    except RegistrySnapshotError:
        return None

    required: list[CasillaId] = []
    optional: list[CasillaId] = []
    for casilla in snapshot.revision.casillas:
        casilla_id = casilla.id
        if casilla.input_kind == InputKind.MANUAL and casilla.required:
            required.append(casilla_id)
        elif casilla.input_kind in (InputKind.MANUAL, InputKind.BOUND, InputKind.COMPUTED):
            optional.append(casilla_id)
    return tuple(required), tuple(optional)


def verification_predicates_for_revision(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
) -> tuple[VerificationPredicateDefinition, ...]:
    """Return a tuple of :class:`VerificationPredicateDefinition` records for the registry revision, or empty tuple."""
    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        authority = authority_via_resources()
    except FileNotFoundError:
        return ()

    try:
        snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period.registry_token)
    except RegistrySnapshotError:
        return ()

    return snapshot.revision.verification_predicates


def assert_revision_content_integrity(revision: CalculationRevision) -> None:
    """Check revision integrity; raise :exc:`StoredCalculationDriftError` on drift.

    Use of :class:`CalculationRevision` for compliance.
    """
    expected = derive_calculation_revision_id(
        work_unit_id=revision.work_unit_id,
        input_values_by_casilla_id=revision.input_values_by_casilla_id,
        binding_overrides=revision.binding_overrides,
        relation_overrides=revision.relation_overrides,
        casilla_values=revision.casilla_values,
        source_transaction_ids=revision.source_transaction_ids,
        borrador_snapshot_id=revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=revision.bindings_sourced_from_borrador,
    )
    if expected != revision.calculation_revision_id:
        raise StoredCalculationDriftError(
            f"calculation revision {revision.calculation_revision_id!r} content-address mismatch: "
            f"stored id does not match re-derived hash of its payload; "
            f"the record may have been tampered with or corrupted",
        )

    for obs in revision.observations:
        stored = revision.casilla_values.get(obs.casilla_id)
        if stored is None:
            raise StoredCalculationDriftError(
                f"calculation revision {revision.calculation_revision_id!r} provenance drift: "
                f"observation for casilla {obs.casilla_id!r} is present but casilla_values "
                f"has no entry for it; the provenance envelope may have been tampered with",
            )
        if obs.value != stored:
            raise StoredCalculationDriftError(
                f"calculation revision {revision.calculation_revision_id!r} provenance drift: "
                f"observation value for casilla {obs.casilla_id!r} is {obs.value!r} "
                f"but casilla_values holds {stored!r}; "
                f"the record may have been tampered with or corrupted",
            )


__all__ = [
    "assert_revision_content_integrity",
    "authority_via_resources",
    "registry_root",
    "reject_incomplete_amendment_casillas",
    "reject_unknown_import_casillas",
    "reject_unknown_override_casillas",
    "reject_unknown_period_for_revision",
    "reject_unknown_revision",
    "required_input_casilla_ids_for_revision",
    "validate_casilla_input_ids",
    "verification_predicates_for_revision",
]
