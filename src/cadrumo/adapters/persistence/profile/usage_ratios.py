"""Encrypted secure-object persistence for :class:`UsageRatioProfile`.

These load / save helpers are the persistence adapter behind the pure
:mod:`~domain.usage_ratios` register. A usage-ratio profile is stored
as an :class:`Envelope`-wrapped encrypted byte object via
:class:`SecureObjectRepository` at :class:`SensitivityClass` FINANCIAL; no
plaintext profile JSON or envelope file lands on disk.

Living in the persistence adapter (not in :mod:`~domain.usage_ratios`)
keeps the :class:`SecureObjectRepository` / :class:`Envelope` coupling out
of the domain layer: the domain package owns only the pure
:class:`UsageRatioProfile` model, the censo derivation, and the
read-modify-write lock, and depends on no persistence substrate. The
censo refuse-load guard composes the read with the domain-pure derivation
so an operator's persisted HOME_OFFICE override is refused on any
disagreement with the bound censo (no auto-migration, no silent coercion).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import ValidationError

from ....core.external_constants import UTF_8_ENCODING
from ....core.logging import get_logger
from ....core.time.clock import now
from ....domain.categories.spending_category import home_office_categories
from ....domain.usage_ratios._model import ELIGIBLE_USAGE_RATIO_CATEGORIES, UsageRatioProfile
from ....domain.usage_ratios._service import derive_home_office_ratios_from_censo, usage_ratios_object_key
from ....domain.usage_ratios.errors import CensoRatioMismatchError, UsageRatioPersistenceError
from ..storage._secure_object_namespaces import USAGE_RATIO_PROFILE_NAMESPACE

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage.sql import SecureObjectRepository

__all__ = [
    "load_usage_ratios",
    "load_usage_ratios_with_censo_guard",
    "save_usage_ratios",
]

_LOGGER = get_logger(__name__)
_USAGE_RATIO_VERSION = USAGE_RATIO_PROFILE_NAMESPACE.schema_version
_USAGE_RATIO_SENSITIVITY = USAGE_RATIO_PROFILE_NAMESPACE.sensitivity
_USAGE_RATIO_NAMESPACE = USAGE_RATIO_PROFILE_NAMESPACE.namespace


def load_usage_ratios(*, bucket_id: str, objects: SecureObjectRepository | None = None) -> UsageRatioProfile:
    """Load one bucket's persisted :class:`UsageRatioProfile`, or return an empty one.

    Args:
        bucket_id: Profile bucket identifier.
        objects: Optional :class:`SecureObjectRepository` override; resolved from settings when absent.
    """
    from ..storage._schema_lineage import inner_envelope_classification_is_expected, inner_envelope_version_is_current
    from ..storage.envelope._envelope import Envelope
    from ..storage.errors import ClassificationError, EnvelopeVersionError
    from ..storage.runtime_repository import secure_object_repository_for_bucket

    object_key = usage_ratios_object_key(bucket_id)
    repository = objects if objects is not None else secure_object_repository_for_bucket(bucket_id)
    try:
        record = repository.load(
            _USAGE_RATIO_NAMESPACE,
            object_key,
            expected_class=_USAGE_RATIO_SENSITIVITY,
            max_supported_version=_USAGE_RATIO_VERSION,
        )
        if record is None:
            _LOGGER.debug("usage-ratios object not found; returning empty profile bucket_id=%s", bucket_id)
            return UsageRatioProfile()
        envelope = Envelope[UsageRatioProfile].model_validate_json(record.payload.decode(UTF_8_ENCODING))
        if not inner_envelope_classification_is_expected(envelope.classification, _USAGE_RATIO_SENSITIVITY):
            raise ClassificationError(
                f"usage-ratio profile object has classification {envelope.classification}; "
                f"consumer expected {_USAGE_RATIO_SENSITIVITY}",
            )
        if not inner_envelope_version_is_current(envelope.schema_version, _USAGE_RATIO_VERSION):
            raise EnvelopeVersionError(
                f"usage-ratio profile object is at version {envelope.schema_version}; "
                f"consumer supports up to {_USAGE_RATIO_VERSION}",
            )
    except ValidationError as exc:
        _LOGGER.error("usage-ratios object validation failed", exc_info=True)
        raise UsageRatioPersistenceError(
            f"invalid usage-ratio profile object\n{_summarise_validation_errors(exc)}",
        ) from exc
    except UnicodeDecodeError as exc:
        _LOGGER.error("usage-ratios object payload is not UTF-8", exc_info=True)
        raise UsageRatioPersistenceError(
            f"invalid usage-ratio profile object\n  - payload: invalid UTF-8: {exc}",
        ) from exc
    except (ClassificationError, EnvelopeVersionError) as exc:
        _LOGGER.error("usage-ratios object integrity error", exc_info=True)
        raise UsageRatioPersistenceError(
            f"usage-ratio profile object integrity error: {exc.__class__.__name__}: {exc}",
        ) from exc
    profile = envelope.payload
    _LOGGER.info("loaded %s usage ratios from secure database bucket_id=%s", len(profile.ratios), bucket_id)
    return profile


def _summarise_validation_errors(exc: ValidationError) -> str:
    """Render a short, operator-legible summary of a pydantic validation failure."""
    lines: list[str] = []
    for error in exc.errors():
        loc = error.get("loc", ())
        location = ".".join(str(part) for part in loc)
        message = error.get("msg", "validation error")
        if error.get("type") == "enum" and len(loc) >= 3 and loc[0] == "ratios" and loc[-1] == "[key]":
            offending_key = loc[1]
            eligible = ", ".join(sorted(c.value for c in ELIGIBLE_USAGE_RATIO_CATEGORIES))
            lines.append(f"  - ratios.{offending_key}: unknown ratio key; eligible categories are: {eligible}")
            continue
        if message.startswith("Value error, "):
            message = message[len("Value error, ") :]
        lines.append(f"  - {location}: {message}" if location else f"  - {message}")
    return "\n".join(lines) if lines else "  - validation error"


def save_usage_ratios(
    profile: UsageRatioProfile,
    *,
    bucket_id: str,
    objects: SecureObjectRepository | None = None,
) -> None:
    """Persist one bucket's usage-ratio profile in the encrypted database.

    Args:
        profile: The usage-ratio profile to persist.
        bucket_id: Profile bucket identifier.
        objects: Optional :class:`SecureObjectRepository` override; resolved from settings when absent.
    """
    from ..storage.envelope._envelope import Envelope
    from ..storage.runtime_repository import secure_object_repository_for_bucket

    envelope = Envelope[UsageRatioProfile](
        schema_version=_USAGE_RATIO_VERSION,
        written_at=now(),
        classification=_USAGE_RATIO_SENSITIVITY,
        payload=profile,
    )
    object_key = usage_ratios_object_key(bucket_id)
    repository = objects if objects is not None else secure_object_repository_for_bucket(bucket_id)
    try:
        repository.save(
            namespace=_USAGE_RATIO_NAMESPACE,
            object_key=object_key,
            classification=_USAGE_RATIO_SENSITIVITY,
            schema_version=_USAGE_RATIO_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
        )
    except OSError as exc:
        _LOGGER.error("usage-ratios database write failed", exc_info=True)
        raise UsageRatioPersistenceError(
            f"unable to write usage-ratio profile: {exc.__class__.__name__}: {exc}",
        ) from exc
    _LOGGER.info("saved %s usage ratios to secure database bucket_id=%s", len(profile.ratios), bucket_id)


def load_usage_ratios_with_censo_guard(
    *,
    bucket_id: str,
    raw_afectacion_ratio: Decimal | None,
    year: int,
    objects: SecureObjectRepository | None = None,
) -> UsageRatioProfile:
    """Load a usage-ratio profile and refuse on censo disagreement.

    Calls :func:`load_usage_ratios` and then enforces the binding-
    censo invariant for HOME_OFFICE_SUMINISTROS and
    HOME_OFFICE_OWNERSHIP categories: every persisted override must
    equal the censo-derived value
    (``raw_afectacion_ratio * statutory_multiplier``). When the
    operator has not yet captured a censo snapshot, any persisted
    HOME_OFFICE override is refused as well, since there is no
    legally-grounded reference to validate against.

    The refusal is a clean break: no auto-migration, no silent
    coercion, no warning-and-continue. The calling surface
    (calculate / verify / file / build_draft / approve_draft /
    export_draft) must therefore surface the underlying
    :exc:`CensoRatioMismatchError` to the operator so they can
    update their censo vivienda_office data via
    ``aeat config profile edit`` or unset the diverging override.

    Args:
        bucket_id: Active workflow bucket id.
        raw_afectacion_ratio: ``office_m2 / total_m2`` from the bound
            censo snapshot, or ``None`` if the operator has not yet
            applied a censo.
        year: Registry year whose proportionality rules drive the
            derivation.
        objects: Optional injected :class:`SecureObjectRepository`
            (testing seam).

    Returns:
        The persisted :class:`UsageRatioProfile` when no HOME_OFFICE
        override disagrees with the censo.

    Raises:
        CensoRatioMismatchError: When at least one persisted HOME_OFFICE
            override disagrees with the censo-derived value, or when any
            persisted HOME_OFFICE override exists with ``raw_afectacion_ratio``
            unset.
    """
    profile = load_usage_ratios(bucket_id=bucket_id, objects=objects)
    home_office = home_office_categories()
    persisted_home_office = {category: ratio for category, ratio in profile.ratios.items() if category in home_office}
    if not persisted_home_office:
        return profile
    if raw_afectacion_ratio is None:
        offending = sorted(c.value for c in persisted_home_office)
        raise CensoRatioMismatchError(
            f"persisted HOME_OFFICE overrides require an applied censo; offending categories: {offending}",
        )
    derived = derive_home_office_ratios_from_censo(raw_afectacion_ratio, year=year)
    mismatches = {
        category: (persisted, derived.ratios[category])
        for category, persisted in persisted_home_office.items()
        if persisted != derived.ratios[category]
    }
    if mismatches:
        rendered = ", ".join(
            f"{category.value} persisted={persisted} censo={censo}"
            for category, (persisted, censo) in sorted(mismatches.items(), key=lambda kv: kv[0].value)
        )
        raise CensoRatioMismatchError(f"persisted HOME_OFFICE overrides disagree with the bound censo: {rendered}")
    return profile
