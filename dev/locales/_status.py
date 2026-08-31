"""Honest campaign-state measurement for the runtime locale catalogues.

One classification produces one report: every required catalogue key is
assigned exactly one :class:`CatalogueLeafState`, so the per-locale counts
partition the required key set and no counter can overstate authored work.
A mirrored, echoed, or otherwise structurally broken value is worse than
an absent one for reporting purposes, because it looks done.

The partition is an internal-consistency guarantee, not a completeness
one: the required set is the production key inventory from
:meth:`~dev.locales.manager.LocaleManager.get_codebase_keys`, so a
key that inventory cannot see is outside the partition entirely.
Namespace-exempted keys are likewise outside it; their count is surfaced
per catalogue so the exempted surface stays visible rather than silently
unreportable.

Modelo schema keys participate in this same partition through the shared
catalogue scanner; there is no second Modelo-local reporting path.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.i18n import extract_placeholders

from .manager import (
    _INTENTIONAL_IDENTICAL_FILENAME,
    _MODELO_SCHEMA_PREFIX,
    LocaleManager,
    _covered_by_namespace,
    _flatten_raw_locale_leaves,
    _load_intentional_identical,
    discover_locale_codes,
    locale_catalogue_source,
)

_REFERENCE_LOCALE_FILE = "en.yml"
_MODELO_SOURCE_LOCALE_FILE = "es.yml"
_PENDING_BUCKET_KEY = "untranslated_pending"

# tr() consumes these kwargs as rendering directives and strips them from the
# interpolation map, so a catalogue token carrying one of these names can
# never bind — the value is structurally broken no matter what a call site
# passes.
RESERVED_INTERPOLATION_TOKENS = frozenset({"locale", "default"})


class CatalogueLeafState(StrEnum):
    """Honest per-leaf state for one required catalogue key in one locale."""

    AUTHORED = "authored"
    KEY_ECHO = "key_echo"
    BLANK = "blank"
    UNBINDABLE = "unbindable"
    IDENTICAL_ALLOWLISTED = "identical_allowlisted"
    IDENTICAL_PENDING = "identical_pending"
    ABSENT = "absent"


class CatalogueStatusRecord(BaseModel):
    """State partition of the required key set for one locale catalogue.

    ``authored + key_echo + blank + unbindable + identical_allowlisted +
    identical_pending + absent == required`` by construction — an
    internal-consistency guarantee over the scanner's required set, not a
    completeness guarantee over every key production could ever request.
    ``extra`` counts catalogue keys outside the required set that no
    dynamic namespace explains, and ``namespace_exempted`` counts the
    keys a namespace marker removes from ``extra``'s reach; both are
    informational and outside the partition.
    """

    model_config = ConfigDict(frozen=True)

    locale_file: str = Field(min_length=1)
    required: int = Field(ge=0)
    authored: int = Field(ge=0)
    key_echo: int = Field(ge=0)
    blank: int = Field(ge=0, default=0)
    unbindable: int = Field(ge=0, default=0)
    identical_allowlisted: int = Field(ge=0)
    identical_pending: int = Field(ge=0)
    absent: int = Field(ge=0)
    extra: int = Field(ge=0)
    namespace_exempted: int = Field(ge=0, default=0)


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
        reference_value: The canonical source catalogue's leaf for ``key``.
        is_reference_locale: Whether the classified catalogue is a source
            equivalent for this key. English is the source for generic
            application keys; Spanish is the mandatory source for Modelo
            schema keys, while English may carry the same official text when
            the source itself is already English.
        allowlisted: Whether the key carries a per-key
            deliberately-identical allowlist entry for this locale.

    Comparison is whitespace-normalised so a stray space or trailing
    punctuation cannot smuggle a scaffold placeholder past the echo check,
    and an empty-after-strip value is its own never-authored state. Two
    probes are deliberately NOT classified because they cannot be
    distinguished from legitimate work: a value equal to the humanised
    form of its key (a short English label such as "Save" for ``…save``
    is often exactly right), and a value identical to a third locale's
    (Spanish and Catalan legitimately share many cognate strings). A
    discriminator that cannot tell defect from cognate would manufacture
    false positives and teach operators to ignore the report.

    Returns:
        Exactly one :class:`CatalogueLeafState`; only ``AUTHORED`` and
        ``IDENTICAL_ALLOWLISTED`` describe finished work.
    """
    if value is None:
        return CatalogueLeafState.ABSENT
    stripped = value.strip()
    if not stripped:
        return CatalogueLeafState.BLANK
    if stripped == key or stripped.rstrip(".:").rstrip() == key:
        return CatalogueLeafState.KEY_ECHO
    if extract_placeholders(value) & RESERVED_INTERPOLATION_TOKENS:
        # A token named after a tr() rendering directive can never bind;
        # the value looks authored but is structurally broken.
        return CatalogueLeafState.UNBINDABLE
    if not is_reference_locale and reference_value is not None and stripped == reference_value.strip():
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

    leaves_by_file: dict[str, dict[str, object]] = {}
    for locale in sorted(discover_locale_codes(manager.locales_dir)):
        source = locale_catalogue_source(manager.locales_dir, locale)
        if source is None:
            continue
        leaves_by_file[f"{locale}.yml"] = _string_leaves(_flatten_raw_locale_leaves(manager.load_locale(source)))
    reference_leaves = leaves_by_file.get(_REFERENCE_LOCALE_FILE, {})
    modelo_source_leaves = leaves_by_file.get(_MODELO_SOURCE_LOCALE_FILE, {})

    return tuple(
        _catalogue_record(
            locale_file=locale_file,
            leaves=leaves,
            required_keys=required_keys,
            reference_leaves=reference_leaves,
            modelo_source_leaves=modelo_source_leaves,
            allowlist=allowlist,
            namespace_prefixes=namespace_prefixes,
        )
        for locale_file, leaves in leaves_by_file.items()
    )


def _catalogue_record(
    *,
    locale_file: str,
    leaves: dict[str, str],
    required_keys: set[str],
    reference_leaves: dict[str, str],
    modelo_source_leaves: dict[str, str],
    allowlist: dict[str, dict[str, object]],
    namespace_prefixes: tuple[str, ...],
) -> CatalogueStatusRecord:
    """Partition one catalogue's leaves into the honest per-state counts."""
    locale_code = locale_file.removesuffix(".yml")
    allowed_keys = {
        key for key in allowlist.get(locale_code, {}) if not key.startswith("_") and key != _PENDING_BUCKET_KEY
    }
    counts = dict.fromkeys(CatalogueLeafState, 0)
    for key in required_keys:
        is_modelo_key = key.startswith(_MODELO_SCHEMA_PREFIX)
        state = classify_catalogue_leaf(
            key,
            leaves.get(key),
            reference_value=(modelo_source_leaves if is_modelo_key else reference_leaves).get(key),
            is_reference_locale=(
                locale_file == _REFERENCE_LOCALE_FILE or (is_modelo_key and locale_file == _MODELO_SOURCE_LOCALE_FILE)
            ),
            allowlisted=key in allowed_keys,
        )
        counts[state] += 1
    not_required = [key for key in leaves if key not in required_keys]
    namespace_exempted = sum(1 for key in not_required if _covered_by_namespace(key, namespace_prefixes))
    return CatalogueStatusRecord(
        locale_file=locale_file,
        required=len(required_keys),
        authored=counts[CatalogueLeafState.AUTHORED],
        key_echo=counts[CatalogueLeafState.KEY_ECHO],
        blank=counts[CatalogueLeafState.BLANK],
        unbindable=counts[CatalogueLeafState.UNBINDABLE],
        identical_allowlisted=counts[CatalogueLeafState.IDENTICAL_ALLOWLISTED],
        identical_pending=counts[CatalogueLeafState.IDENTICAL_PENDING],
        absent=counts[CatalogueLeafState.ABSENT],
        extra=len(not_required) - namespace_exempted,
        namespace_exempted=namespace_exempted,
    )


def _string_leaves(raw_leaves: dict[str, object]) -> dict[str, str]:
    """Keep only string leaves; non-string scalars read as absent."""
    return {key: value for key, value in raw_leaves.items() if isinstance(value, str)}


__all__ = [
    "RESERVED_INTERPOLATION_TOKENS",
    "CatalogueLeafState",
    "CatalogueStatusRecord",
    "catalogue_status",
    "classify_catalogue_leaf",
]
