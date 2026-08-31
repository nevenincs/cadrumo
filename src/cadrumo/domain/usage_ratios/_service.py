"""Pure usage-ratio register logic: object key, mutation lock, censo derivation.

Usage ratios carry business / personal split percentages. The encrypted
:class:`Envelope`-wrapped persistence lives in the adapter
(:mod:`adapters.persistence.profile.usage_ratios`); this module owns
only the persistence-substrate-free pieces: the secure-object key
convention, the per-bucket read-modify-write lock, and the censo-derived
HOME_OFFICE ratio computation.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from ...core.identity import canonical_bucket_id
from ...core.logging import get_logger
from ..categories import (
    HOME_OFFICE_FAMILIES,
    SpendingCategory,
    categories_for_family,
    effective_usage_ratio,
    resolve_category_profiles,
)
from ._model import UsageRatioProfile
from .errors import UsageRatioPersistenceError, UsageRatioValidationError

__all__ = [
    "derive_home_office_ratios_from_censo",
    "usage_ratio_bucket_lock",
    "usage_ratios_object_key",
]

_LOGGER = get_logger(__name__)


def _canonical_bucket_id(bucket_id: str) -> str:
    """Return ``bucket_id`` under the canonical :data:`~core.identity.BucketId` contract.

    The key and lock helpers stripped and rejected blanks for themselves but
    never consumed the canonical alias, so they also accepted identifiers past
    its 128-character cap. A 129-character bucket could therefore own a
    usage-ratio row and a lock target that no other bucket consumer would
    address the same way, fragmenting storage ownership for one profile.

    The rule itself is not restated here. It lives beside the alias it
    enforces, as :func:`~core.identity.canonical_bucket_id`; this wrapper only
    translates the shared refusal into this domain's own error class, which is
    exactly why the shared helper raises the plain builtin.

    Raises:
        UsageRatioPersistenceError: When ``bucket_id`` is blank after
            stripping or violates the canonical bound.
    """
    try:
        return canonical_bucket_id(bucket_id)
    except ValueError as exc:
        raise UsageRatioPersistenceError(
            "bucket_id must be a canonical bucket identifier: non-blank and at most 128 characters",
        ) from exc


def usage_ratios_object_key(bucket_id: str) -> str:
    """Return the secure object key for one profile bucket's usage-ratio profile.

    Raises:
        UsageRatioPersistenceError: When ``bucket_id`` is not a canonical
            :data:`~core.identity.BucketId`.
    """
    return f"profile:{_canonical_bucket_id(bucket_id)}"


def _usage_ratio_lock_target(bucket_id: str) -> Path:
    """Return the per-bucket sidecar path that guards the usage-ratio row.

    The lock sidecar is placed inside the bucket's own storage directory
    (alongside its encrypted database) so it scopes mutual exclusion to a
    single profile bucket and never serialises writes to unrelated profiles.
    The sidecar carries no payload — it is an empty OS-lock coordination file —
    so it is not sensitive financial data and does not breach the
    secure-storage boundary; the profile bytes still live only in the
    encrypted :class:`SecureObjectRepository` row.
    """
    from ...core.config import (
        classify_storage_route,
        load_settings,
        settings_for_active_profile_bucket,
    )

    trimmed = _canonical_bucket_id(bucket_id)
    settings = load_settings()
    if "cadrumo_database_url" in settings.model_fields_set:
        # Explicit-database route (test/bootstrap): the route already names the
        # storage authority; scope the lock to that database's directory.
        route = classify_storage_route(settings)
    else:
        route = classify_storage_route(settings_for_active_profile_bucket(trimmed, settings))
    base = route.database_path.parent if route.database_path is not None else settings.cadrumo_local_storage_root
    safe = "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in trimmed)
    return base / f"usage-ratios.{safe}.lock"


@contextmanager
def usage_ratio_bucket_lock(bucket_id: str) -> Generator[None]:
    """Serialise the load-modify-save of one bucket's usage-ratio row.

    The usage-ratio profile is a single :class:`SecureObjectRepository` row per
    bucket. Every mutator (``ratios set`` / ``ratios unset`` and the censo
    home-office seed) reads that row, mutates one entry, and writes the whole
    row back. Without a cross-transaction guard two concurrent writers each load
    the same snapshot, apply their own change, and the second save silently
    drops the first writer's category — a lost update. The encrypted-SQLite
    ``busy_timeout`` / WAL only serialises individual write transactions; it
    does not make the read-modify-write span atomic, so the lost update
    persists.

    This context manager acquires the project's OS-level
    :func:`core.locks.exclusive_file_lock` on a per-bucket sidecar so the
    whole load-modify-save runs under mutual exclusion. Because the lock is held
    across both the load and the save, concurrent writers serialise and every
    update survives — there is no silent overwrite. The lock is scoped to the
    bucket, so writers on unrelated profiles never contend.

    Args:
        bucket_id: Profile bucket whose usage-ratio row is being mutated.

    Raises:
        LockAcquisitionError: When the per-bucket lock cannot be acquired within
            the configured ``cadrumo_file_lock_timeout_s`` budget.
    """
    from ...core.locks import exclusive_file_lock

    with exclusive_file_lock(_usage_ratio_lock_target(bucket_id)):
        yield


def derive_home_office_ratios_from_censo(
    raw_afectacion_ratio: Decimal,
    *,
    year: int,
) -> UsageRatioProfile:
    """Build a :class:`UsageRatioProfile` for HOME_OFFICE categories from the censo.

    The operator's vivienda afectación ratio is the raw
    ``office_m2 / total_m2`` computed from the AEAT-bound censo facts
    (LIRPF Art. 30.2 rule 5, Ley 6/2017 BOE-A-2017-12544). For every
    HOME_OFFICE_SUMINISTROS category, the ratio is multiplied by the
    registry rule's ``statutory_multiplier`` (legally 0.30 for utility
    costs); for every HOME_OFFICE_OWNERSHIP category, the multiplier is
    absent (effective factor 1.0) so the operator-chosen ratio is the
    full deductible percentage.

    Args:
        raw_afectacion_ratio: ``office_m2 / total_m2`` as a Decimal in
            [0, 1]. Higher values are rejected; AEAT exclusive-use
            criteria forbid 100% afectación on the habitual vivienda.
        year: Registry profile year (e.g. ``2025``) whose
            proportionality rules drive the derivation.

    Returns:
        A :class:`UsageRatioProfile` carrying one entry per
        HOME_OFFICE category, each set to its legally-effective
        deductible percentage.

    Raises:
        UsageRatioValidationError: When ``raw_afectacion_ratio`` is outside
            the ``[0, 1]`` range.
    """
    if raw_afectacion_ratio < Decimal("0") or raw_afectacion_ratio > Decimal("1"):
        raise UsageRatioValidationError(
            f"raw_afectacion_ratio must be in [0, 1]; got {raw_afectacion_ratio}",
        )
    registry = resolve_category_profiles(year)
    derived: dict[SpendingCategory, Decimal] = {}
    for family in HOME_OFFICE_FAMILIES:
        for category in categories_for_family(family):
            profile = registry[category]
            derived[category] = effective_usage_ratio(profile.proportionality, raw_afectacion_ratio)
    return UsageRatioProfile(ratios=derived)
