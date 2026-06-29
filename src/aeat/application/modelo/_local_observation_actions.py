"""Operator-supplied local filed observations for calculation prefill.

This module records local, non-official observations in the existing
cross-period calculation observation store. It deliberately does not create a
``ModeloRecord`` and does not stamp ``ExternalEvidence``: the values are
operator-supplied scratch/local inputs that can feed relation and
``previous_filing`` calculation prefill, but they must never satisfy the
filing-grade clean-state proof that requires AEAT-backed evidence.

Each persisted observation is grounded against the law-determined
:class:`RegistrySnapshot` and stored as provenance-bearing
:class:`CasillaObservation` rows, while the source kind stays explicitly
non-official.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, ValidationError

from ...core import STRICT_FROZEN_CONFIG, Period
from ...core.resources import resources
from ...core.time import now as _utc_now
from ...domain.calculations.registry import (
    CasillaId,
    CasillaObservation,
    RegistryModeloObservation,
    RegistrySnapshot,
    RegistrySnapshotError,
    RegistryValidationError,
    casilla_noncanonical_reference_targets,
    casillas_by_id,
    undeclared_casilla_ids,
    validated_casilla_id,
)
from ..calculations import CalculationObservationRepository, observation_key
from ._action_errors import ModeloLocalObservationError

OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND: Final = "operator_manual"
"""Non-official source kind for operator-supplied local observations."""

_NUMERIC_CASILLA_DATA_TYPES: Final = frozenset({"decimal", "money", "integer", "ratio"})


class ModeloLocalObservationResult(BaseModel):
    """Result of recording one operator-supplied local observation."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    filing_year: int
    period: Period
    revision_id: str
    observation_key: str
    source_kind: str
    casilla_values: dict[CasillaId, Decimal]
    captured_at: datetime
    captured_by: str
    official_evidence: bool = False
    filing_record_created: bool = False
    aeat_accepted: bool = False


def record_operator_local_observation[CasillaKey](
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    casilla_values: Mapping[CasillaKey, Decimal],
    actor: str = "operator-manual",
    repository: CalculationObservationRepository | None = None,
    clock: datetime | None = None,
) -> ModeloLocalObservationResult:
    """Persist an operator-supplied local observation for later calculation prefill.

    The observation is grounded against the law-determined
    :class:`RegistrySnapshot` for ``modelo`` / ``filing_year`` /
    ``period``. Every supplied casilla id must be a canonical numeric
    casilla declared by that snapshot; printed-number aliases and
    unknown ids are refused before the observation store is touched.

    The persisted row uses ``source_kind="operator_manual"`` and carries the
    snapshot revision id as its stamp. Calculation prefill can then resolve the
    :class:`CasillaObservation` values, while cross-period clean-state
    verification still treats it as non-official local evidence.

    Returns:
        A :class:`ModeloLocalObservationResult` describing the persisted local
        observation stamp.
    """
    snapshot = _load_snapshot(modelo=modelo, filing_year=filing_year, period=period)
    canonical_values = _canonical_casilla_values(snapshot=snapshot, casilla_values=casilla_values)
    observations = _observation_rows(snapshot=snapshot, casilla_values=canonical_values)
    observation = RegistryModeloObservation(
        modelo=modelo,
        filing_year=filing_year,
        period=period.registry_token,
        observations=observations,
    )
    captured_at = clock or _utc_now()
    captured_by = actor.strip() or "operator-manual"
    key = observation_key(modelo, period)
    repo = repository or CalculationObservationRepository()
    repo.save_observation(
        observation,
        source_kind=OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND,
        captured_at=captured_at,
        stamped_revision_id=snapshot.revision.id,
        source_metadata={
            "local_observation_kind": "operator_supplied",
            "captured_by": captured_by,
            "official_evidence": "false",
            "filing_record_created": "false",
        },
    )
    return ModeloLocalObservationResult(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=snapshot.revision.id,
        observation_key=key,
        source_kind=OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND,
        casilla_values=dict(canonical_values),
        captured_at=captured_at,
        captured_by=captured_by,
    )


def _load_snapshot(*, modelo: str, filing_year: int, period: Period) -> RegistrySnapshot:
    try:
        return resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period.registry_token)
    except RegistrySnapshotError as exc:
        raise ModeloLocalObservationError(
            (
                f"local observation cannot be recorded because the registry snapshot is missing for "
                f"modelo={modelo!r} filing_year={filing_year} period={period.registry_token!r}"
            ),
            context={"modelo": modelo, "filing_year": filing_year, "period": period.registry_token},
        ) from exc


def _canonical_casilla_values[CasillaKey](
    *,
    snapshot: RegistrySnapshot,
    casilla_values: Mapping[CasillaKey, Decimal],
) -> dict[CasillaId, Decimal]:
    if not casilla_values:
        raise ModeloLocalObservationError("local observation requires at least one --set CASILLA=DECIMAL value")

    canonical: dict[CasillaId, Decimal] = {}
    malformed: list[str] = []
    non_decimal: list[str] = []
    for key, value in casilla_values.items():
        try:
            casilla_id = validated_casilla_id(key, surface="local observation casilla")
        except ValueError:
            malformed.append(repr(key))
            continue
        if isinstance(value, bool) or not isinstance(value, Decimal):
            non_decimal.append(casilla_id)
            continue
        canonical[casilla_id] = value

    if malformed:
        raise ModeloLocalObservationError(
            "local observation casilla keys must be canonical casilla.id values",
            context={"casillas": ",".join(sorted(malformed)), "revision_id": snapshot.revision.id},
        )
    if non_decimal:
        raise ModeloLocalObservationError(
            "local observation casilla values must be Decimal instances",
            context={"casillas": ",".join(sorted(non_decimal)), "revision_id": snapshot.revision.id},
        )

    unknown = undeclared_casilla_ids(snapshot.revision, canonical)
    if unknown:
        noncanonical = {
            casilla_id: targets
            for casilla_id in unknown
            if (targets := casilla_noncanonical_reference_targets(snapshot.revision, casilla_id))
        }
        if noncanonical:
            details = "; ".join(
                f"{casilla_id!r} -> {', '.join(targets)}" for casilla_id, targets in sorted(noncanonical.items())
            )
            raise ModeloLocalObservationError(
                f"local observation casillas must use canonical casilla.id values; refused aliases: {details}",
                context={"casillas": ",".join(sorted(noncanonical)), "revision_id": snapshot.revision.id},
            )
        raise ModeloLocalObservationError(
            f"local observation casillas are not declared in revision {snapshot.revision.id!r}: {unknown!r}",
            context={"casillas": ",".join(unknown), "revision_id": snapshot.revision.id},
        )

    declared = casillas_by_id(snapshot.revision)
    non_numeric = sorted(
        casilla_id
        for casilla_id in canonical
        if declared[casilla_id].data_type not in _NUMERIC_CASILLA_DATA_TYPES
    )
    if non_numeric:
        raise ModeloLocalObservationError(
            "local observation --set accepts only numeric casillas",
            context={"casillas": ",".join(non_numeric), "revision_id": snapshot.revision.id},
        )
    return canonical


def _observation_rows(
    *,
    snapshot: RegistrySnapshot,
    casilla_values: Mapping[CasillaId, Decimal],
) -> tuple[CasillaObservation, ...]:
    declared = casillas_by_id(snapshot.revision)
    rows: list[CasillaObservation] = []
    for casilla_id, value in casilla_values.items():
        casilla = declared[casilla_id]
        try:
            rows.append(
                CasillaObservation(
                    casilla_id=casilla_id,
                    value=value,
                    legal_refs=casilla.legal_refs,
                    source_refs=casilla.source_refs,
                ),
            )
        except (RegistryValidationError, ValidationError, TypeError, ValueError) as exc:
            raise ModeloLocalObservationError(
                "local observation casilla cannot be persisted without registry legal/source provenance",
                context={"casilla": casilla_id, "revision_id": snapshot.revision.id},
            ) from exc
    return tuple(rows)


__all__ = [
    "OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND",
    "ModeloLocalObservationResult",
    "record_operator_local_observation",
]
