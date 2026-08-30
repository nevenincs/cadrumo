"""Registry lookup and casilla validation helpers for modelo actions.

The helper layer resolves
:class:`~cadrumo.domain.calculations.registry.RegistrySnapshot` instances through
:mod:`cadrumo.application.modelo._registry_resources`, validates
operator/imported casilla maps against the selected
:class:`~cadrumo.domain.calculations.registry.ModeloRevision`, and refuses
non-canonical printed-number tokens before the calculation engine or
persistence layer sees them.

It also verifies stored :class:`~CalculationRevision`
payloads by re-deriving their content-addressed identifiers and checking
:class:`~cadrumo.domain.calculations.registry.CasillaObservation`/value consistency
before stored payloads are trusted by verification or filing workflows.

See Also:
    :func:`cadrumo.domain.calculations.registry.authority.bundled_authority`
        Canonical registry authority used by snapshot-backed guards.
    :func:`validate_casilla_input_ids`
        Boundary validator for operator-supplied casilla maps.
    :func:`assert_revision_content_integrity`
        Read-side guard for stored calculation revision drift.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from ...core import Period
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.casilla_membership import (
    casilla_noncanonical_reference_targets,
    casillas_by_id,
    format_noncanonical_casilla_reference,
    undeclared_casilla_ids,
)
from ...domain.calculations.registry.errors import (
    RegistrySnapshotError,
    RegistryValidationError,
)
from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ...domain.modelos.calculation_revision import CalculationRevision, derive_calculation_revision_id_from_revision
from ._action_errors import (
    AmendmentOverrideCasillaError,
    AmendmentVerificationRefusedError,
    ExternalModeloImportError,
    StoredCalculationDriftError,
)
from ._registry_resources import (
    registry_root,
    reject_unknown_period_for_revision,
    reject_unknown_revision,
)

# Casilla data types the engine represents on the numeric Decimal channel. This
# is the one canonical declaration in this package; ``_local_observation_actions.py``
# imports it rather than re-declaring its own copy.
NUMERIC_CASILLA_DATA_TYPES: frozenset[str] = frozenset({"decimal", "money", "integer", "ratio"})

# A boolean casilla answers on this same Decimal channel, encoded 0 / 1. That is
# the engine's own representation rather than a convenience: the Modelo 100
# art. 85 operand reads a boolean casilla out of the NUMERIC map and refuses
# anything that is not 0 or 1, and the art. 23.2 arrendamiento reducción uses its
# flag casilla as a multiplicative operand, so an absent flag arrives as zero and
# silently withholds the reducción. A boolean-typed BINDING is already encoded
# this way on the ``--binding`` channel, so accepting it for a casilla makes the
# two channels agree instead of leaving the casilla half unreachable.
#
# Kept as its own set rather than folded into the numeric one because only this
# family is domain-restricted to 0 / 1 below. A numeric casilla stays
# unrestricted, and no ``bool`` is admitted anywhere: the value is and remains a
# Decimal, so nothing widens toward writing a Python boolean onto a numeric row.
_BOOLEAN_CASILLA_DATA_TYPES: frozenset[str] = frozenset({"boolean"})
_BOOLEAN_CASILLA_ENCODED_VALUES: frozenset[Decimal] = frozenset({Decimal(0), Decimal(1)})


@dataclass(frozen=True)
class _ResolvedRegistryCasillaInputs:
    """One snapshot-backed normalisation result for a caller's casilla map."""

    snapshot: RegistrySnapshot
    canonical_values: dict[CasillaId, Decimal]
    malformed: tuple[str, ...]
    unknown: tuple[CasillaId, ...]
    noncanonical: dict[CasillaId, tuple[CasillaId, ...]]
    unknown_only: tuple[CasillaId, ...]


def _resolve_registry_snapshot(*, modelo: str, filing_year: int, period: Period) -> RegistrySnapshot:
    """Resolve the law-selected registry snapshot for one filing target."""
    return bundled_authority().snapshot(modelo, filing_year=filing_year, period=period.registry_token)


def _normalise_registry_casilla_inputs[CasillaKey](
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    casilla_values: Mapping[CasillaKey, Decimal],
    surface: str,
) -> _ResolvedRegistryCasillaInputs:
    """Resolve a snapshot and classify a casilla map against its declared ids."""
    snapshot = _resolve_registry_snapshot(modelo=modelo, filing_year=filing_year, period=period)
    malformed: list[str] = []
    canonical_values: dict[CasillaId, Decimal] = {}
    for casilla_id, value in casilla_values.items():
        try:
            canonical_values[validated_casilla_id(casilla_id, surface=surface)] = value
        except ValueError:
            malformed.append(repr(casilla_id))
    unknown = undeclared_casilla_ids(snapshot.revision, canonical_values)
    noncanonical, unknown_only = _noncanonical_casilla_reference_details(snapshot.revision, unknown)
    return _ResolvedRegistryCasillaInputs(
        snapshot=snapshot,
        canonical_values=canonical_values,
        malformed=tuple(sorted(malformed)),
        unknown=unknown,
        noncanonical=noncanonical,
        unknown_only=unknown_only,
    )


def reject_incomplete_amendment_casillas(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    casilla_values: Mapping[CasillaId, Decimal],
) -> None:
    """Mirror the verify-modelo-revision required-manual gate on amend.

    The supplied :class:`~cadrumo.core.Period` selects the
    :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot` used to read
    required manual casillas. Missing required manual casillas raise
    :class:`~cadrumo.application.modelo.AmendmentVerificationRefusedError` before
    an amendment can be accepted as complete.
    """
    required_optional = required_input_casilla_ids_for_revision(modelo=modelo, filing_year=filing_year, period=period)
    if required_optional is None:
        raise AmendmentVerificationRefusedError(
            translated_message="application.modelo.errors.amendment_verification_refused_no_snapshot",
            context={
                "modelo": str(modelo),
                "filing_year": str(filing_year),
                "period": period.registry_token,
                "snapshot_present": False,
            },
        )
    required, _ = required_optional
    missing = sorted(casilla_id for casilla_id in required if casilla_id not in casilla_values)
    if missing:
        raise AmendmentVerificationRefusedError(
            translated_message="application.modelo.errors.amendment_verification_refused_missing_casillas",
            context={
                "modelo": str(modelo),
                "filing_year": str(filing_year),
                "period": period.registry_token,
                "missing_casilla_ids": ", ".join(str(casilla_id) for casilla_id in missing),
            },
        )


def validate_casilla_input_ids[CasillaKey, CasillaValue](
    revision: ModeloRevision,
    casilla_inputs: Mapping[CasillaKey, CasillaValue],
) -> dict[CasillaId, Decimal]:
    """Validate operator-supplied numeric input casillas against the revision.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies the
    declared casilla ids, data types, and non-canonical reference targets used to
    reject ambiguous or malformed operator input. The returned mapping is keyed
    by canonical :class:`~cadrumo.core.CasillaId` values and
    contains only ``Decimal`` numeric inputs that the registry engine may
    consume.

    Two declared families may carry a value: the numeric ones over their full
    range, and the boolean family restricted to ``0`` / ``1``, which is how the
    engine itself reads a boolean casilla. Both arrive as ``Decimal``; a Python
    ``bool`` is refused for either, so widening to booleans never widens toward
    writing a ``True`` onto an amount row.
    """
    if not casilla_inputs:
        return {}
    revision_casillas_by_id = casillas_by_id(revision)
    canonical_inputs, malformed = _canonicalise_casilla_inputs(casilla_inputs)
    _reject_malformed_casilla_input_keys(revision, malformed)
    _reject_unknown_casilla_input_ids(revision, canonical_inputs)
    decimal_inputs = _validated_decimal_casilla_inputs(revision, canonical_inputs)
    _reject_non_numeric_casilla_inputs(revision, revision_casillas_by_id, decimal_inputs)
    _reject_boolean_casilla_inputs_outside_domain(revision, revision_casillas_by_id, decimal_inputs)
    return decimal_inputs


def _canonicalise_casilla_inputs[CasillaKey, CasillaValue](
    casilla_inputs: Mapping[CasillaKey, CasillaValue],
) -> tuple[dict[CasillaId, CasillaValue], list[str]]:
    """Keep canonical input keys separate from malformed boundary tokens."""
    canonical_inputs: dict[CasillaId, CasillaValue] = {}
    malformed: list[str] = []
    for key, value in casilla_inputs.items():
        try:
            canonical_key = validated_casilla_id(key, surface="casilla input key")
        except ValueError:
            malformed.append(repr(key))
            continue
        canonical_inputs[canonical_key] = value
    return canonical_inputs, malformed


def _reject_malformed_casilla_input_keys(revision: ModeloRevision, malformed: list[str]) -> None:
    """Refuse malformed keys before examining declared membership or values."""
    if malformed:
        raise RegistryValidationError(
            translated_message="errors.error.error_calculations_registry_validation",
            context={"casilla_ids": ",".join(sorted(malformed)), "revision_id": revision.id},
        )


def _reject_unknown_casilla_input_ids(
    revision: ModeloRevision,
    canonical_inputs: Mapping[CasillaId, object],
) -> None:
    """Refuse unknown ids, naming non-canonical reference tokens first."""
    unknown = undeclared_casilla_ids(revision, canonical_inputs)
    if unknown:
        noncanonical, unknown_only = _noncanonical_casilla_reference_details(revision, unknown)
        if noncanonical:
            details = "; ".join(
                format_noncanonical_casilla_reference(casilla_id, targets)
                for casilla_id, targets in sorted(noncanonical.items())
            )
            raise RegistryValidationError(
                translated_message="errors.error.error_calculations_registry_validation",
                context={
                    "casilla_ids": ",".join(sorted(noncanonical)),
                    "revision_id": revision.id,
                    "noncanonical_reference_targets": details,
                },
            )
        raise RegistryValidationError(
            translated_message="errors.error.error_calculations_registry_validation",
            context={"casilla_ids": ",".join(unknown_only), "revision_id": revision.id},
        )


def _validated_decimal_casilla_inputs[CasillaValue](
    revision: ModeloRevision,
    canonical_inputs: Mapping[CasillaId, CasillaValue],
) -> dict[CasillaId, Decimal]:
    """Refuse non-decimal values before data-type or boolean-domain checks."""
    non_decimal = sorted(
        casilla_id
        for casilla_id, value in canonical_inputs.items()
        if isinstance(value, bool) or not isinstance(value, Decimal)
    )
    if non_decimal:
        raise RegistryValidationError(
            translated_message="errors.error.error_calculations_registry_validation",
            context={
                "casilla_ids": ",".join(non_decimal),
                "revision_id": revision.id,
                "value_types": ",".join(type(canonical_inputs[casilla_id]).__name__ for casilla_id in non_decimal),
            },
        )
    return {casilla_id: value for casilla_id, value in canonical_inputs.items() if isinstance(value, Decimal)}


def _reject_non_numeric_casilla_inputs(
    revision: ModeloRevision,
    revision_casillas_by_id: Mapping[CasillaId, CasillaDefinition],
    decimal_inputs: Mapping[CasillaId, Decimal],
) -> None:
    """Keep the numeric/boolean input-kind policy at this application boundary."""
    accepted_data_types = NUMERIC_CASILLA_DATA_TYPES | _BOOLEAN_CASILLA_DATA_TYPES
    non_numeric = sorted(
        casilla_id
        for casilla_id in decimal_inputs
        if revision_casillas_by_id[casilla_id].data_type not in accepted_data_types
    )
    if non_numeric:
        raise RegistryValidationError(
            translated_message="errors.error.error_calculations_registry_validation",
            context={
                "casilla_ids": ",".join(non_numeric),
                "revision_id": revision.id,
                "data_types": ",".join(revision_casillas_by_id[casilla_id].data_type for casilla_id in non_numeric),
            },
        )


def _reject_boolean_casilla_inputs_outside_domain(
    revision: ModeloRevision,
    revision_casillas_by_id: Mapping[CasillaId, CasillaDefinition],
    decimal_inputs: Mapping[CasillaId, Decimal],
) -> None:
    """Require the engine's exact 0/1 representation for boolean casillas."""
    out_of_domain = sorted(
        casilla_id
        for casilla_id, value in decimal_inputs.items()
        if revision_casillas_by_id[casilla_id].data_type in _BOOLEAN_CASILLA_DATA_TYPES
        and value not in _BOOLEAN_CASILLA_ENCODED_VALUES
    )
    if out_of_domain:
        # Named rather than rounded toward the nearer of 0 / 1. The engine refuses
        # a boolean casilla that is not exactly 0 or 1, so coercing here would only
        # move the same refusal further from the operator who typed the value, and
        # guessing which answer a 2 meant is not a guess this boundary can make.
        raise RegistryValidationError(
            translated_message="errors.error.error_calculations_registry_validation",
            context={
                "casilla_ids": ",".join(out_of_domain),
                "revision_id": revision.id,
                "accepted": "0,1",
                "values": ",".join(str(decimal_inputs[casilla_id]) for casilla_id in out_of_domain),
            },
        )


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
    """Refuse amendment override casillas outside the resolved revision.

    Keys are canonicalised as
    :class:`~cadrumo.core.CasillaId` values and checked
    against the :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot`
    selected by ``modelo``, ``filing_year``, and :class:`~cadrumo.core.Period`.
    Printed-number aliases and ambiguous reused numbers raise
    :class:`~cadrumo.application.modelo.AmendmentOverrideCasillaError` instead of
    being projected to a declared casilla.
    """
    if not overrides:
        return {}

    try:
        resolved = _normalise_registry_casilla_inputs(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            casilla_values=overrides,
            surface="amendment override casilla",
        )
    except FileNotFoundError as exc:
        raise AmendmentOverrideCasillaError(
            translated_message="application.modelo.errors.amendment_registry_root_missing",
            context={"registry_root": registry_root()},
        ) from exc
    except RegistrySnapshotError as exc:
        raise AmendmentOverrideCasillaError(
            translated_message="application.modelo.errors.amendment_registry_snapshot_unresolved",
            context={"modelo": modelo, "filing_year": filing_year, "period": period.registry_token},
        ) from exc

    if resolved.malformed:
        raise AmendmentOverrideCasillaError(
            translated_message="application.modelo.errors.amendment_unknown_casillas",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
                "casillas": list(resolved.malformed),
            },
        )
    if resolved.unknown:
        if resolved.noncanonical:
            details = "; ".join(
                format_noncanonical_casilla_reference(casilla_id, targets)
                for casilla_id, targets in sorted(resolved.noncanonical.items())
            )
            raise AmendmentOverrideCasillaError(
                f"amendment override casillas must use canonical casilla.id values; "
                f"non-canonical reference tokens are not accepted: {details}",
                translated_message="application.modelo.errors.amendment_unknown_casillas",
                context={
                    "noncanonical_reference_targets": details,
                    "modelo": modelo,
                    "filing_year": filing_year,
                    "period": period.registry_token,
                    "casillas": sorted(resolved.noncanonical),
                },
            )
        raise AmendmentOverrideCasillaError(
            translated_message="application.modelo.errors.amendment_unknown_casillas",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
                "casillas": resolved.unknown_only,
            },
        )
    return resolved.canonical_values


def reject_unknown_import_casillas[CasillaKey](
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    casilla_values: Mapping[CasillaKey, Decimal],
) -> tuple[RegistrySnapshot, dict[CasillaId, Decimal]]:
    """Validate imported casilla ids and return the resolved registry snapshot.

    The snapshot is a
    :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot`. The returned
    mapping is keyed by canonical
    :class:`~cadrumo.core.CasillaId` values declared by the
    selected :class:`~cadrumo.domain.calculations.registry.ModeloRevision`.
    Unknown, malformed, and non-canonical printed numbers raise
    :class:`~cadrumo.application.modelo.ExternalModeloImportError` so imported AEAT
    values enter observation projection only under registry ids.
    """
    try:
        resolved = _normalise_registry_casilla_inputs(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            casilla_values=casilla_values,
            surface="external import casilla",
        )
    except FileNotFoundError as exc:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_registry_root_missing",
            context={"registry_root": registry_root()},
        ) from exc
    except RegistrySnapshotError as exc:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_registry_snapshot_unresolved",
            context={"modelo": modelo, "filing_year": filing_year, "period": period.registry_token},
        ) from exc

    if resolved.malformed:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_unknown_casillas",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
                "casillas": list(resolved.malformed),
            },
        )
    if resolved.unknown:
        if resolved.noncanonical:
            details = "; ".join(
                format_noncanonical_casilla_reference(casilla_id, targets)
                for casilla_id, targets in sorted(resolved.noncanonical.items())
            )
            raise ExternalModeloImportError(
                f"external import casillas must use canonical casilla.id values; "
                f"non-canonical reference tokens are not accepted: {details}",
                translated_message="application.modelo.errors.external_import_unknown_casillas",
                context={
                    "noncanonical_reference_targets": details,
                    "modelo": modelo,
                    "filing_year": filing_year,
                    "period": period.registry_token,
                    "casillas": sorted(resolved.noncanonical),
                },
            )
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_unknown_casillas",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
                "casillas": resolved.unknown_only,
            },
        )
    return resolved.snapshot, resolved.canonical_values


def required_input_casilla_ids_for_revision(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
) -> tuple[tuple[CasillaId, ...], tuple[CasillaId, ...]] | None:
    """Resolve required manual and replayable input casilla ids for a revision.

    Returns ``None`` when the registry root or
    :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot` cannot be
    loaded. The first tuple contains required manual casillas from the selected
    :class:`~cadrumo.domain.calculations.registry.ModeloRevision`; the second
    contains declared manual, bound, and computed
    :class:`~cadrumo.core.CasillaId` values that
    amendment/import paths may need to carry through replay.
    """
    try:
        snapshot = _resolve_registry_snapshot(modelo=modelo, filing_year=filing_year, period=period)
    except (FileNotFoundError, RegistrySnapshotError):
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
    """Return verification predicate rows for the selected revision.

    The rows are
    :class:`~cadrumo.domain.calculations.registry.VerificationPredicateDefinition`
    instances. Missing registry roots or unresolved
    :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot` instances
    produce an empty tuple so callers can degrade to their existing verification
    paths.
    """
    try:
        snapshot = _resolve_registry_snapshot(modelo=modelo, filing_year=filing_year, period=period)
    except (FileNotFoundError, RegistrySnapshotError):
        return ()

    return snapshot.revision.verification_predicates


def assert_revision_content_integrity(revision: CalculationRevision) -> None:
    """Check revision integrity; raise stored-calculation drift on mismatch.

    The supplied :class:`~CalculationRevision` is re-hashed
    from its persisted inputs, bindings, relations, casilla values, and source
    metadata before its provenance observations are compared with
    ``casilla_values``. This is a defense-in-depth read-side check for raw
    storage corruption that bypassed normal model construction; a mismatched
    observation envelope raises
    :exc:`~cadrumo.application.modelo.StoredCalculationDriftError` before the
    revision is treated as authoritative.
    """
    expected = derive_calculation_revision_id_from_revision(revision)
    if expected != revision.calculation_revision_id:
        raise StoredCalculationDriftError(
            f"calculation revision {revision.calculation_revision_id!r} content-address mismatch: "
            f"stored id does not match re-derived hash of its payload; "
            f"the record may have been tampered with or corrupted",
        )

    for obs in revision.observations:
        stored = revision.casilla_values.get(obs.casilla_id)
        if stored is None:
            stored = revision.input_values_by_casilla_id.get(obs.casilla_id)
        if stored is None:
            raise StoredCalculationDriftError(
                f"calculation revision {revision.calculation_revision_id!r} provenance drift: "
                f"observation for casilla {obs.casilla_id!r} is present but neither casilla_values nor "
                f"input_values_by_casilla_id has an entry for it; the provenance envelope may have been tampered with",
            )
        if obs.value != stored:
            raise StoredCalculationDriftError(
                f"calculation revision {revision.calculation_revision_id!r} provenance drift: "
                f"observation value for casilla {obs.casilla_id!r} is {obs.value!r} "
                f"but casilla_values holds {stored!r}; "
                f"the record may have been tampered with or corrupted",
            )


__all__ = [
    "NUMERIC_CASILLA_DATA_TYPES",
    "assert_revision_content_integrity",
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
