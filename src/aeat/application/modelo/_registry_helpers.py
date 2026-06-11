"""Registry lookup and verification helpers for modelo actions.

Use of :class:`CalculationRevision`, :class:`ModeloRevision`, :class:`RegistrySnapshot` for compliance.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import Period
from ...domain.calculations.registry import (
    InputKind,
    ModeloRevision,
    RegistrySnapshot,
    VerificationPredicateDefinition,
    input_casilla_alias_map,
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


def reject_incomplete_amendment_casillas(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    casilla_values: Mapping[str, Decimal],
) -> None:
    """Mirror the verify-modelo-revision required-manual gate on amend."""
    required_optional = required_input_casillas_for_revision(modelo=modelo, filing_year=filing_year, period=period)
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


def normalize_casilla_input_aliases(
    revision: ModeloRevision,
    casilla_inputs: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    """Resolve operator-supplied ``--casilla`` keys to canonical casilla ids.

    Use of :class:`ModeloRevision` for compliance.
    """
    if not casilla_inputs:
        return dict(casilla_inputs)
    alias_map = input_casilla_alias_map(revision)
    return {alias_map.get(key, key): value for key, value in casilla_inputs.items()}


def reject_unknown_override_casillas(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    overrides: Mapping[str, Decimal],
) -> None:
    """Refuse override casilla ids the registry does not declare for the modelo / year / period."""
    if not overrides:
        return

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

    known = {str(casilla.id) for casilla in snapshot.revision.casillas}
    unknown = sorted(casilla_id for casilla_id in overrides if casilla_id not in known)
    if unknown:
        raise AmendmentOverrideCasillaError(
            translated_message="application.modelo.errors.amendment_unknown_casillas",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
                "casillas": unknown,
            },
        )


def reject_unknown_import_casillas(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    casilla_values: Mapping[str, Decimal],
) -> RegistrySnapshot:
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

    known = {str(casilla.id) for casilla in snapshot.revision.casillas}
    unknown = sorted(casilla_id for casilla_id in casilla_values if casilla_id not in known)
    if unknown:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_unknown_casillas",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
                "casillas": unknown,
            },
        )
    return snapshot


def required_input_casillas_for_revision(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    """Resolve the registry's required and informational input casillas."""
    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        authority = authority_via_resources()
    except FileNotFoundError:
        return None

    try:
        snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period.registry_token)
    except RegistrySnapshotError:
        return None

    required: list[str] = []
    optional: list[str] = []
    for casilla in snapshot.revision.casillas:
        casilla_id = str(casilla.id)
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
        inputs_snapshot=revision.inputs_snapshot,
        binding_overrides=revision.binding_overrides,
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
    "normalize_casilla_input_aliases",
    "registry_root",
    "reject_incomplete_amendment_casillas",
    "reject_unknown_import_casillas",
    "reject_unknown_override_casillas",
    "reject_unknown_period_for_revision",
    "reject_unknown_revision",
    "required_input_casillas_for_revision",
    "verification_predicates_for_revision",
]
