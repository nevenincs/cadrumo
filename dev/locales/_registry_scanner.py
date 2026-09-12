"""Registry-declared locale key discovery for the committed registry trees.

Some operator-facing copy is declared as registry DATA rather than at a
Python call site, so the regex, AST, and f-string scanners -- all of which
walk Python source -- cannot see it. This module is the fourth discovery
path: it walks the committed registry.

Three registry surfaces declare keys, and they are scanned by separate
functions rather than one merged walk. The category profile fact names its
keys literally in TOML; the user-profile schema and Modelo schema instead
declare STRUCTURE, and their keys are derived from that structure. Merging
them would put unrelated registries inside :func:`scan_registry_keys`, whose
caller-visible contract (and pinned count) is the category-profile key
universe.

Kept separate from :mod:`locales._ast_scanner`, whose contract is Python-AST
walking; the registry is a TOML surface and shares no traversal machinery.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from functools import cache

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.user_profile.labels import profile_field_label_key, profile_section_title_key
from cadrumo.domain.user_profile.loader import load_user_profile_schema
from dev.registry.compiler.loader import load_modelo_locale_key_projection

_CATEGORY_LOCALE_PREFIX = "categories.registry."
_CATEGORY_LOCALIZED_ENTRY_NAMES = frozenset({"display_label", "notes"})
_CAP_VARIANT_ENTRY_PREFIX = "statutory_cap_variant."
_CAP_VARIANT_LABEL_SUFFIX = ".label"
_CAP_VARIANT_FIELDS = frozenset({"label", "eur_per_day", "eur"})


class LocaleRegistryEnumerationError(RuntimeError):
    """The registry source could not be enumerated for locale-key discovery.

    Locale discovery must never turn a broken registry into an empty key set:
    doing so would make every registry-derived dynamic translation appear
    complete while silently dropping its concrete leaves.  Callers may catch
    this error to report a blocking discovery diagnostic, but must not treat it
    as an empty enumeration.
    """


def scan_registry_keys() -> set[str]:
    """Return every locale key declared in the category profile fact source.

    The committed TOML fact is the authority for this inventory. Read its
    mapping entries directly instead of loading the published authority or
    typed category profiles: locale tooling must remain usable while those
    runtime bindings are being migrated. Citation quotes and all other
    evidence fields are excluded: they are verbatim AEAT excerpts or
    non-localized metadata authored in the registry TOML.

    Returns:
        The dotted translation keys declared across the profile corpus.

    Raises:
        LocaleRegistryEnumerationError: If the committed fact source cannot
            be read or its localization-bearing structure is ambiguous.
    """
    try:
        path = bundled_path("registry", "aeat", "facts", "0064-categories-profile.toml").resolve()
    except (OSError, ValueError) as exc:
        raise LocaleRegistryEnumerationError(
            f"cannot resolve category profile locale-key source: {type(exc).__name__}: {exc}",
        ) from exc
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise LocaleRegistryEnumerationError(
            f"cannot enumerate category profile locale keys from {path}: {type(exc).__name__}: {exc}",
        ) from exc

    if not isinstance(document, Mapping):
        raise LocaleRegistryEnumerationError(f"category profile source is not a TOML table: {path}")
    fact = document.get("fact")
    if not isinstance(fact, Mapping):
        raise LocaleRegistryEnumerationError(f"category profile source has no [fact] table: {path}")
    if fact.get("fact_id") != "categories.profile":
        raise LocaleRegistryEnumerationError(
            f"category profile source has unexpected fact_id {fact.get('fact_id')!r}: {path}",
        )
    if fact.get("family") != "mapping":
        raise LocaleRegistryEnumerationError(
            f"category profile source has unexpected family {fact.get('family')!r}: {path}",
        )

    variants = fact.get("variants")
    if not isinstance(variants, list) or not variants:
        raise LocaleRegistryEnumerationError(f"category profile source has no mapping variants: {path}")

    keys: set[str] = set()
    for variant_index, variant in enumerate(variants):
        if not isinstance(variant, Mapping):
            raise LocaleRegistryEnumerationError(
                f"category profile variant[{variant_index}] is not a table: {path}",
            )
        payload = variant.get("payload")
        if not isinstance(payload, Mapping) or payload.get("kind") != "mapping":
            raise LocaleRegistryEnumerationError(
                f"category profile variant[{variant_index}] has no mapping payload: {path}",
            )
        entries = payload.get("entries")
        if not isinstance(entries, list) or not entries:
            raise LocaleRegistryEnumerationError(
                f"category profile variant[{variant_index}] has no mapping entries: {path}",
            )
        for entry_index, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                raise LocaleRegistryEnumerationError(
                    f"category profile variant[{variant_index}].entries[{entry_index}] is not a table: {path}",
                )
            entry_key = entry.get("key")
            entry_value = entry.get("value")
            if not isinstance(entry_key, str) or not entry_key:
                raise LocaleRegistryEnumerationError(
                    f"category profile variant[{variant_index}].entries[{entry_index}] has no string key: {path}",
                )
            if "value" not in entry:
                raise LocaleRegistryEnumerationError(
                    f"category profile entry {entry_key!r} has no value: {path}",
                )
            if not _is_valid_category_entry(entry_key):
                raise LocaleRegistryEnumerationError(
                    f"category profile entry {entry_key!r} has an ambiguous cap-variant shape: {path}",
                )
            if _is_localized_category_entry(entry_key):
                if (
                    not isinstance(entry_value, str)
                    or not entry_value.strip()
                    or entry_value != entry_value.strip()
                    or not entry_value.startswith(_CATEGORY_LOCALE_PREFIX)
                ):
                    raise LocaleRegistryEnumerationError(
                        f"category profile entry {entry_key!r} has an ambiguous locale key {entry_value!r}: {path}",
                    )
                keys.add(entry_value)

    if not keys:
        raise LocaleRegistryEnumerationError(f"category profile source declares no locale keys: {path}")
    return keys


def _is_localized_category_entry(entry_key: str) -> bool:
    """Return whether a mapping entry carries a category translation key."""
    if entry_key in _CATEGORY_LOCALIZED_ENTRY_NAMES:
        return True
    if not entry_key.startswith(_CAP_VARIANT_ENTRY_PREFIX) or not entry_key.endswith(_CAP_VARIANT_LABEL_SUFFIX):
        return False
    variant_id = entry_key[len(_CAP_VARIANT_ENTRY_PREFIX) : -len(_CAP_VARIANT_LABEL_SUFFIX)]
    return bool(variant_id)


def _is_valid_category_entry(entry_key: str) -> bool:
    """Return whether a cap-variant entry uses the committed fact grammar."""
    if not entry_key.startswith(_CAP_VARIANT_ENTRY_PREFIX):
        return True
    variant_id, separator, field = entry_key[len(_CAP_VARIANT_ENTRY_PREFIX) :].rpartition(".")
    return bool(variant_id) and bool(separator) and field in _CAP_VARIANT_FIELDS


def scan_profile_schema_keys() -> set[str]:
    """Return every locale key derived from the user-profile schema.

    The schema's section titles and field labels are keyed by structure, so
    a field added to the schema TOML declares its label key by construction.
    Enrolling them here is what makes such a field a parity failure rather
    than a row that silently renders its English-or-Spanish description.

    Returns:
        The dotted section-title and field-label keys the schema declares.
    """
    keys: set[str] = set()
    for section in load_user_profile_schema().sections:
        keys.add(profile_section_title_key(section.key))
        for field in section.fields:
            keys.add(profile_field_label_key(section.key, field.key))
    return keys


@cache
def scan_modelo_schema_keys() -> set[str]:
    """Return every concrete key derived by the language-neutral Modelo schema.

    The compiler projection reads only the committed structural source and
    deliberately does not construct the typed binding family.  Keep failures
    explicit: an incomplete or ambiguous source must block locale inventory,
    never turn into an apparently complete empty set.
    """
    try:
        return set(load_modelo_locale_key_projection(bundled_path("registry", "aeat")))
    except LocaleRegistryEnumerationError:
        raise
    except Exception as exc:  # Intentional audit boundary around source reads.
        raise LocaleRegistryEnumerationError(
            f"cannot enumerate Modelo schema locale keys: {type(exc).__name__}: {exc}",
        ) from exc


@cache
def scan_detail_row_fields() -> tuple[str, ...]:
    """Enumerate every ``row_field`` token authored by the bundled registry.

    The sheet-detail header renderer receives its selector from the validated
    registry, but the published authority artifact may be unavailable while
    locale tooling is running.  This development scanner therefore reads the
    committed TOML source *structurally* and collects only the exact
    ``row_field`` declarations.  It does not validate or stand in for the
    filing-grade authority.  Any source read/parse failure is raised with the
    path and cause so callers report inability to enumerate honestly instead
    of silently returning an incomplete set.

    Returns:
        A sorted tuple of all distinct row-field tokens in the registry source.

    Raises:
        LocaleRegistryEnumerationError: If the source tree is absent, unreadable,
            malformed, or carries no row-field declaration.
    """
    root = bundled_path("registry", "aeat").resolve()
    if not root.is_dir():
        raise LocaleRegistryEnumerationError(f"registry source root is not a directory: {root}")
    paths = tuple(sorted(root.rglob("*.toml")))
    if not paths:
        raise LocaleRegistryEnumerationError(f"registry source root contains no TOML files: {root}")

    values: set[str] = set()

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "row_field":
                    if not isinstance(value, str) or not value:
                        raise LocaleRegistryEnumerationError(
                            f"registry row_field declaration is not a non-empty string under {root}"
                        )
                    values.add(value)
                _walk(value)
        elif isinstance(node, list):
            for value in node:
                _walk(value)

    for path in paths:
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise LocaleRegistryEnumerationError(
                f"cannot enumerate registry row fields from {path}: {type(exc).__name__}: {exc}"
            ) from exc
        _walk(payload)

    if not values:
        raise LocaleRegistryEnumerationError(f"registry source contains no row_field declarations: {root}")
    return tuple(sorted(values))
