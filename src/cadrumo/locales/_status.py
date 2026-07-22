"""Honest campaign-state measurement for the runtime locale catalogues.

One classification produces one report: every required catalogue key is
assigned exactly one :class:`CatalogueLeafState`, so the per-locale counts
partition the required key set and no counter can overstate authored work.
The modelo schema-local side of the same report reuses
:meth:`~cadrumo.locales._modelo_manager.ModeloLocaleManager.coverage_records`,
which applies the equivalent partition through
:func:`~cadrumo.locales._modelo_manager.classify_modelo_locale_leaf`.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .manager import (
    _INTENTIONAL_IDENTICAL_FILENAME,
    LocaleManager,
    _covered_by_namespace,
    _flatten_raw_locale_leaves,
    _load_intentional_identical,
)

_REFERENCE_LOCALE_FILE = "en.yml"
_PENDING_BUCKET_KEY = "untranslated_pending"


class CatalogueLeafState(StrEnum):
    """Honest per-leaf state for one required catalogue key in one locale."""

    AUTHORED = "authored"
    KEY_ECHO = "key_echo"
    IDENTICAL_ALLOWLISTED = "identical_allowlisted"
    IDENTICAL_PENDING = "identical_pending"
    ABSENT = "absent"


class CatalogueStatusRecord(BaseModel):
    """State partition of the required key set for one locale catalogue.

    ``authored + key_echo + identical_allowlisted + identical_pending +
    absent == required`` by construction. ``extra`` counts catalogue keys
    outside the required set that no dynamic namespace explains; it is
    informational and outside the partition.
    """

    model_config = ConfigDict(frozen=True)

    locale_file: str = Field(min_length=1)
    required: int = Field(ge=0)
    authored: int = Field(ge=0)
    key_echo: int = Field(ge=0)
    identical_allowlisted: int = Field(ge=0)
    identical_pending: int = Field(ge=0)
    absent: int = Field(ge=0)
    extra: int = Field(ge=0)


def classify_catalogue_leaf(
    key: str,
    value: str | None,
    *,
    reference_value: str | None,
    is_reference_locale: bool,
    allowlisted: bool,
) -> CatalogueLeafState:
    """Classify one required catalogue key's value into its honest state.

    Args:
        key: Dotted locale key being classified.
        value: The locale's stored leaf, or ``None`` when missing or not a
            string.
        reference_value: The reference (English) catalogue's leaf for ``key``.
        is_reference_locale: Whether the classified catalogue is the
            reference catalogue itself.
        allowlisted: Whether the key carries a per-key
            deliberately-identical allowlist entry for this locale.

    Returns:
        Exactly one :class:`CatalogueLeafState`; only ``AUTHORED`` and
        ``IDENTICAL_ALLOWLISTED`` describe finished work.
    """
    if value is None:
        return CatalogueLeafState.ABSENT
    if value == key:
        return CatalogueLeafState.KEY_ECHO
    if not is_reference_locale and reference_value is not None and value == reference_value:
        return CatalogueLeafState.IDENTICAL_ALLOWLISTED if allowlisted else CatalogueLeafState.IDENTICAL_PENDING
    return CatalogueLeafState.AUTHORED


def catalogue_status(manager: LocaleManager) -> tuple[CatalogueStatusRecord, ...]:
    """Return the honest state partition for every runtime catalogue.

    The required set is the codebase translation-key inventory; dynamic
    namespaces only exempt catalogue-extra keys, exactly as the parity
    audit treats them.
    """
    required_keys = manager.get_codebase_keys()
    namespace_prefixes = tuple(
        marker.rstrip("*").rstrip(".") for marker in manager.get_codebase_namespaces() if marker.rstrip("*").rstrip(".")
    )
    allowlist = _load_intentional_identical(manager.locales_dir / _INTENTIONAL_IDENTICAL_FILENAME)

    leaves_by_file = {
        path.name: _string_leaves(_flatten_raw_locale_leaves(manager.load_locale(path)))
        for path in sorted(manager.locales_dir.glob("*.yml"))
    }
    reference_leaves = leaves_by_file.get(_REFERENCE_LOCALE_FILE, {})

    records: list[CatalogueStatusRecord] = []
    for locale_file, leaves in leaves_by_file.items():
        locale_code = locale_file.removesuffix(".yml")
        allowed_keys = {
            key for key in allowlist.get(locale_code, {}) if not key.startswith("_") and key != _PENDING_BUCKET_KEY
        }
        counts = dict.fromkeys(CatalogueLeafState, 0)
        for key in required_keys:
            state = classify_catalogue_leaf(
                key,
                leaves.get(key),
                reference_value=reference_leaves.get(key),
                is_reference_locale=locale_file == _REFERENCE_LOCALE_FILE,
                allowlisted=key in allowed_keys,
            )
            counts[state] += 1
        extra = sum(
            1 for key in leaves if key not in required_keys and not _covered_by_namespace(key, namespace_prefixes)
        )
        records.append(
            CatalogueStatusRecord(
                locale_file=locale_file,
                required=len(required_keys),
                authored=counts[CatalogueLeafState.AUTHORED],
                key_echo=counts[CatalogueLeafState.KEY_ECHO],
                identical_allowlisted=counts[CatalogueLeafState.IDENTICAL_ALLOWLISTED],
                identical_pending=counts[CatalogueLeafState.IDENTICAL_PENDING],
                absent=counts[CatalogueLeafState.ABSENT],
                extra=extra,
            ),
        )
    return tuple(records)


def _string_leaves(raw_leaves: dict[str, object]) -> dict[str, str]:
    """Keep only string leaves; non-string scalars read as absent."""
    return {key: value for key, value in raw_leaves.items() if isinstance(value, str)}


__all__ = [
    "CatalogueLeafState",
    "CatalogueStatusRecord",
    "catalogue_status",
    "classify_catalogue_leaf",
]
