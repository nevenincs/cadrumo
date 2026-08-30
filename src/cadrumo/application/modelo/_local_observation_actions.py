"""Operator-supplied local filed observations for calculation prefill.

This module records local, non-official observations in the existing
cross-period calculation observation store. It deliberately does not create a
:class:`ModeloRecord` and does not stamp :class:`ExternalEvidence`: the values are
operator-supplied scratch/local inputs that can feed relation and
``previous_filing`` calculation prefill, but they must never satisfy the
filing-grade clean-state proof that requires AEAT-backed evidence.

Each persisted observation is grounded against the law-determined
:class:`ModeloRevision` -- resolved structurally via ``select_revision``,
never a filing-grade snapshot, since recording a non-official local
observation is not itself a filing act -- and stored as provenance-bearing
:class:`CasillaObservation` rows, while the source kind stays explicitly
non-official.

See Also:
    :func:`~application.modelo._filed_revision_observation.persist_filed_revision_observation`:
        Local-filing projection that uses ``app_filing`` rather than
        operator-manual source.
    :mod:`~application.calculations.cross_period_clean_state`:
        Classifies local observations as non-official for filing-grade readiness.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, ValidationError

from ...core import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.resources import bundled_path
from ...core.time import now as _utc_now
from ...domain.calculations.registry.bindings import (
    CasillaObservation,
    RegistryModeloObservation,
)
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
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.loader import load_registry_tree
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.temporal import select_revision
from ..calculations import CalculationObservationRepository, ObservationSourceKind, observation_key
from ._action_errors import ModeloLocalObservationError
from ._registry_helpers import NUMERIC_CASILLA_DATA_TYPES

OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND: Final = ObservationSourceKind.OPERATOR_MANUAL
"""Non-official source kind for operator-supplied local observations."""


class ModeloLocalObservationResult(BaseModel):
    """Result of recording one operator-supplied local observation."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    filing_year: int
    period: Period
    revision_id: RevisionId
    observation_key: str
    source_kind: ObservationSourceKind
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
    casilla_values: Mapping[CasillaKey, object],
    actor: str = "operator-manual",
    repository: CalculationObservationRepository | None = None,
    clock: datetime | None = None,
    replace_official_evidence: bool = False,
) -> ModeloLocalObservationResult:
    """Persist an operator-supplied local observation for later calculation prefill.

    The observation is grounded against the law-determined
    :class:`ModeloRevision` for ``modelo`` / ``filing_year`` /
    ``period``. Every supplied casilla id must be a canonical numeric
    casilla declared by that revision; printed-number aliases and
    unknown ids are refused before the observation store is touched.

    The persisted row uses ``source_kind="operator_manual"`` and carries the
    revision id as its stamp. Calculation prefill can then resolve the
    :class:`CasillaObservation` values, while cross-period clean-state
    verification still treats it as non-official local evidence.

    Returns:
        A :class:`ModeloLocalObservationResult` describing the persisted local
        observation stamp.
    """
    revision = _load_revision(modelo=modelo, filing_year=filing_year, period=period)
    canonical_values = _canonical_casilla_values(revision=revision, casilla_values=casilla_values)
    observations = _observation_rows(revision=revision, casilla_values=canonical_values)
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
    repo.save(
        repo.prepare_observation_envelope(
            observation,
            source_kind=OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND,
            captured_at=captured_at,
            stamped_revision_id=revision.id,
            source_metadata={
                "local_observation_kind": "operator_supplied",
                "captured_by": captured_by,
                "official_evidence": "false",
                "filing_record_created": "false",
            },
            normalize_m303_carry=False,
            replace_official_evidence=replace_official_evidence,
        ),
    )
    return ModeloLocalObservationResult(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision.id,
        observation_key=key,
        source_kind=OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND,
        casilla_values=dict(canonical_values),
        captured_at=captured_at,
        captured_by=captured_by,
    )


def _load_revision(*, modelo: str, filing_year: int, period: Period) -> ModeloRevision:
    try:
        modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
        modelo_definition = next(candidate for candidate in modelos if candidate.id == modelo)
        return select_revision(
            modelo_definition,
            filing_year=filing_year,
            period=period.registry_token,
        )
    except RegistrySnapshotError as exc:
        raise ModeloLocalObservationError(
            (
                f"local observation cannot be recorded because the registry revision is missing for "
                f"modelo={modelo!r} filing_year={filing_year} period={period.registry_token!r}"
            ),
            context={"modelo": modelo, "filing_year": filing_year, "period": period.registry_token},
        ) from exc


def _canonical_casilla_values[CasillaKey](
    *,
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaKey, object],
) -> dict[CasillaId, Decimal]:
    if not casilla_values:
        raise ModeloLocalObservationError(
            translated_message="errors.error.error_modelos",
            context={"casilla_value_count": 0},
        )

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
            translated_message="errors.error.error_modelos",
            context={"casillas": ",".join(sorted(malformed)), "revision_id": revision.id},
        )
    if non_decimal:
        raise ModeloLocalObservationError(
            translated_message="errors.error.error_modelos",
            context={"casillas": ",".join(sorted(non_decimal)), "revision_id": revision.id},
        )

    unknown = undeclared_casilla_ids(revision, canonical)
    if unknown:
        noncanonical = {
            casilla_id: targets
            for casilla_id in unknown
            if (targets := casilla_noncanonical_reference_targets(revision, casilla_id))
        }
        if noncanonical:
            details = "; ".join(
                format_noncanonical_casilla_reference(casilla_id, targets)
                for casilla_id, targets in sorted(noncanonical.items())
            )
            raise ModeloLocalObservationError(
                translated_message="errors.error.error_modelos",
                context={
                    "casillas": ",".join(sorted(noncanonical)),
                    "revision_id": revision.id,
                    "noncanonical_reference_targets": details,
                },
            )
        raise ModeloLocalObservationError(
            translated_message="errors.error.error_modelos",
            context={"casillas": ",".join(unknown), "revision_id": revision.id},
        )

    declared = casillas_by_id(revision)
    non_numeric = sorted(
        casilla_id for casilla_id in canonical if declared[casilla_id].data_type not in NUMERIC_CASILLA_DATA_TYPES
    )
    if non_numeric:
        raise ModeloLocalObservationError(
            translated_message="errors.error.error_modelos",
            context={"casillas": ",".join(non_numeric), "revision_id": revision.id},
        )
    return canonical


def _observation_rows(
    *,
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
) -> tuple[CasillaObservation, ...]:
    declared = casillas_by_id(revision)
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
                translated_message="errors.error.error_modelos",
                context={"casilla": casilla_id, "revision_id": revision.id},
            ) from exc
    return tuple(rows)


__all__ = [
    "OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND",
    "ModeloLocalObservationResult",
    "record_operator_local_observation",
]
