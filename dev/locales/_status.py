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

from cadrumo.core.i18n.render import extract_placeholders

from .manager import (
    LocaleManager,
    _covered_by_namespace,
    _flatten_raw_locale_leaves,
    discover_locale_codes,
    locale_catalogue_source,
)

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
    ABSENT = "absent"


class CatalogueStatusRecord(BaseModel):
    """State partition of the required key set for one locale catalogue.

    ``authored + key_echo + blank + unbindable + absent == required`` by construction — an
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
    absent: int = Field(ge=0)
    extra: int = Field(ge=0)
    namespace_exempted: int = Field(ge=0, default=0)


def classify_catalogue_leaf(
    key: str,
    value: str | None,
) -> CatalogueLeafState:
    """Classify one required catalogue key's value into its honest state.

    Args:
        key: Dotted locale key being classified.
        value: The locale's stored leaf, or ``None`` when missing or not a
            string.
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
        Exactly one :class:`CatalogueLeafState`; only ``AUTHORED`` describes
        a present, structurally valid value.
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
    leaves_by_file: dict[str, dict[str, str]] = {}
    for locale in sorted(discover_locale_codes(manager.locales_dir)):
        source = locale_catalogue_source(manager.locales_dir, locale)
        if source is None:
            continue
        leaves_by_file[f"{locale}.yml"] = _string_leaves(_flatten_raw_locale_leaves(manager.load_locale(source)))
    return tuple(
        _catalogue_record(
            locale_file=locale_file,
            leaves=leaves,
            required_keys=required_keys,
            namespace_prefixes=namespace_prefixes,
        )
        for locale_file, leaves in leaves_by_file.items()
    )


def _catalogue_record(
    *,
    locale_file: str,
    leaves: dict[str, str],
    required_keys: set[str],
    namespace_prefixes: tuple[str, ...],
) -> CatalogueStatusRecord:
    """Partition one catalogue's leaves into the honest per-state counts."""
    counts = dict.fromkeys(CatalogueLeafState, 0)
    for key in required_keys:
        state = classify_catalogue_leaf(
            key,
            leaves.get(key),
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
