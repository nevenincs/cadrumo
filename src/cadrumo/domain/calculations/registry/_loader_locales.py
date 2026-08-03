"""Locale-translation loading and merging for the directory-mode TOML loader.

Extracted from :mod:`~domain.calculations.registry._loader` to keep that
module under its size budget (`aeat-architecture-boundaries`,
`registry-resolver-family-extraction`). Owns the ``locales/*.toml`` read,
merge, referential-integrity check, and casilla-injection pipeline that
:func:`~domain.calculations.registry._loader.load_modelo_directory`
applies after merging a modelo's revision fragments. Per
`aeat-locales-cli`, the modelo schema-local translation TOML this module
reads is authored only through the ``cadrumo.locales modelo`` CLI; this module
is the read-side compiler for that authored data, not an authoring surface.

See Also:
    :mod:`~domain.calculations.registry._loader`
        Owns directory-mode modelo/revision fragment merging and calls
        :func:`apply_locales` once the revision TOML is merged.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from ....core import freeze_toml, read_toml
from ._errors import RegistryLoadError, RegistryValidationError
from ._ids import CasillaId, validated_casilla_id
from ._toml_helpers import as_toml_table

_TOML_ARRAY_ADAPTER: TypeAdapter[list[object] | tuple[object, ...]] = TypeAdapter(
    list[object] | tuple[object, ...], config=ConfigDict(strict=True)
)


def _toml_array(value: object) -> tuple[object, ...] | None:
    """Return a strictly typed TOML array without changing its item values."""
    try:
        return tuple(_TOML_ARRAY_ADAPTER.validate_python(value))
    except ValidationError:
        return None


class RegistryLocaleTranslation(BaseModel):
    labels: dict[str, str] = Field(default_factory=dict)
    help: dict[str, str] = Field(default_factory=dict)


def _load_locale_translation(path: Path) -> RegistryLocaleTranslation:
    try:
        raw_data = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
        return RegistryLocaleTranslation.model_validate(raw_data)
    except Exception as exc:
        raise RegistryValidationError(f"Invalid locales file {path}: {exc}") from exc


def _merge_locale_translation(
    *,
    language: str,
    target: RegistryLocaleTranslation,
    source: RegistryLocaleTranslation,
    path: Path,
) -> RegistryLocaleTranslation:
    labels = dict(target.labels)
    help_text = dict(target.help)
    duplicate_labels = sorted(set(labels).intersection(source.labels))
    duplicate_help = sorted(set(help_text).intersection(source.help))
    if duplicate_labels or duplicate_help:
        details: list[str] = []
        if duplicate_labels:
            details.append(f"labels={duplicate_labels!r}")
        if duplicate_help:
            details.append(f"help={duplicate_help!r}")
        raise RegistryValidationError(
            f"Duplicate {language!r} locale translation keys in {path}: {', '.join(details)}",
        )
    labels.update(source.labels)
    help_text.update(source.help)
    return RegistryLocaleTranslation(labels=labels, help=help_text)


def _load_locale_translation_group(language: str, paths: Iterable[Path]) -> RegistryLocaleTranslation:
    merged = RegistryLocaleTranslation()
    for path in sorted(paths):
        merged = _merge_locale_translation(
            language=language,
            target=merged,
            source=_load_locale_translation(path),
            path=path,
        )
    return merged


def _load_locale_translations(locales_dir: Path) -> dict[str, RegistryLocaleTranslation]:
    translations: dict[str, RegistryLocaleTranslation] = {}
    if not locales_dir.is_dir():
        return translations
    for path in sorted(locales_dir.glob("*.toml")):
        translations[path.stem] = _load_locale_translation_group(path.stem, (path,))
    for language_dir in sorted(path for path in locales_dir.iterdir() if path.is_dir()):
        paths = tuple(sorted(language_dir.glob("*.toml")))
        if not paths:
            continue
        if language_dir.name in translations:
            raise RegistryValidationError(
                f"Locale {language_dir.name!r} is declared both as a file and a fragment directory in {locales_dir}",
            )
        translations[language_dir.name] = _load_locale_translation_group(language_dir.name, paths)
    return translations


def _load_modelo_translations(modelo_dir: Path) -> dict[str, RegistryLocaleTranslation]:
    return _load_locale_translations(modelo_dir / "locales")


def _load_revision_translations(
    modelo_dir: Path,
) -> dict[str, dict[str, RegistryLocaleTranslation]]:
    translations: dict[str, dict[str, RegistryLocaleTranslation]] = {}
    revisions_dir = modelo_dir / "revisions"
    if not revisions_dir.is_dir():
        return translations
    for path in sorted(revisions_dir.iterdir()):
        if not path.is_dir():
            continue
        rev_locales_dir = path / "locales"
        locale_map = _load_locale_translations(rev_locales_dir)
        if locale_map:
            translations[path.name] = locale_map
    return translations


def _collect_valid_locale_ids(
    merged_revisions: dict[str, object],
) -> tuple[dict[str, set[CasillaId]], set[str]]:
    valid_casilla_ids: dict[str, set[CasillaId]] = {}
    valid_continuidad_ids: set[str] = set()
    for revision_id, raw_rev in merged_revisions.items():
        raw_rev_table = as_toml_table(raw_rev)
        if raw_rev_table is None:
            continue
        casillas_list = _toml_array(raw_rev_table.get("casillas", ()))
        if casillas_list is None:
            continue
        rev_casilla_ids: set[CasillaId] = set()
        for casilla in casillas_list:
            casilla_table = as_toml_table(casilla)
            if casilla_table is None:
                continue
            c_id = casilla_table.get("id")
            if isinstance(c_id, str):
                try:
                    rev_casilla_ids.add(validated_casilla_id(c_id, surface=f"revision {revision_id!r} casilla id"))
                except ValueError as exc:
                    raise RegistryValidationError(
                        f"Invalid casilla id {c_id!r} in revision {revision_id!r}: expected canonical casilla.id",
                    ) from exc
            cont_id = casilla_table.get("continuidad_id")
            if isinstance(cont_id, str):
                valid_continuidad_ids.add(cont_id)
        valid_casilla_ids[revision_id] = rev_casilla_ids
    return valid_casilla_ids, valid_continuidad_ids


def _validate_translation_keys(
    trans: RegistryLocaleTranslation,
    valid_ids: set[str] | set[CasillaId],
    locale: str,
    *,
    context: str,
    reason: str,
) -> None:
    for field_name, mapping in (("labels", trans.labels), ("help", trans.help)):
        for key in mapping:
            if key not in valid_ids:
                raise RegistryValidationError(
                    f"Invalid translation key {key!r} in {field_name} for locale {locale!r}{context}: {reason}",
                )


def _check_locale_referential_integrity(
    modelo_translations: dict[str, RegistryLocaleTranslation],
    revision_translations: dict[str, dict[str, RegistryLocaleTranslation]],
    valid_casilla_ids: dict[str, set[CasillaId]],
    valid_continuidad_ids: set[str],
) -> None:
    for locale, trans in modelo_translations.items():
        _validate_translation_keys(
            trans,
            valid_continuidad_ids,
            locale,
            context="",
            reason="no continuity chain found with this continuity id",
        )
    for revision_id, locale_map in revision_translations.items():
        rev_ids = valid_casilla_ids.get(revision_id, set())
        for locale, trans in locale_map.items():
            _validate_translation_keys(
                trans,
                rev_ids,
                locale,
                context=f" under revision {revision_id!r}",
                reason="no casilla found with this id",
            )


def _localize_casilla(
    casilla: object,
    revision_id: str,
    modelo_translations: dict[str, RegistryLocaleTranslation],
    revision_translations: dict[str, dict[str, RegistryLocaleTranslation]],
) -> object:
    casilla_table = as_toml_table(casilla)
    if casilla_table is None:
        return casilla

    casilla_id = casilla_table.get("id")
    continuidad_id = casilla_table.get("continuidad_id")

    localized_labels: dict[str, str] = {}
    localized_help: dict[str, str] = {}

    # Concept continuity (modelo-wide) translations
    if isinstance(continuidad_id, str):
        for locale, trans in modelo_translations.items():
            if continuidad_id in trans.labels:
                localized_labels[locale] = trans.labels[continuidad_id]
            if continuidad_id in trans.help:
                localized_help[locale] = trans.help[continuidad_id]

    # Revision-local override translations
    if isinstance(casilla_id, str):
        for locale, trans in revision_translations.get(revision_id, {}).items():
            if casilla_id in trans.labels:
                localized_labels[locale] = trans.labels[casilla_id]
            if casilla_id in trans.help:
                localized_help[locale] = trans.help[casilla_id]

    new_casilla = dict(casilla_table)
    new_casilla["localized_labels"] = localized_labels
    new_casilla["localized_help"] = localized_help
    return new_casilla


def _inject_localized_translations(
    merged_revisions: dict[str, object],
    modelo_translations: dict[str, RegistryLocaleTranslation],
    revision_translations: dict[str, dict[str, RegistryLocaleTranslation]],
) -> None:
    for revision_id, raw_rev in merged_revisions.items():
        raw_rev_table = as_toml_table(raw_rev)
        if raw_rev_table is None:
            continue
        casillas_list = _toml_array(raw_rev_table.get("casillas", ()))
        if casillas_list is None:
            continue
        raw_rev_table["casillas"] = tuple(
            _localize_casilla(casilla, revision_id, modelo_translations, revision_translations)
            for casilla in casillas_list
        )


def apply_locales(modelo_dir: Path, merged_revisions: dict[str, object]) -> None:
    """Load, validate, and inject a modelo directory's locale TOML in place.

    Called once by
    :func:`~domain.calculations.registry._loader._load_modelo_directory_cached`
    after a directory-mode modelo's revision fragments are merged, so the
    locale keys can be validated against the final casilla/continuity id set.
    """
    modelo_translations = _load_modelo_translations(modelo_dir)
    revision_translations = _load_revision_translations(modelo_dir)
    valid_casilla_ids, valid_continuidad_ids = _collect_valid_locale_ids(merged_revisions)
    _check_locale_referential_integrity(
        modelo_translations,
        revision_translations,
        valid_casilla_ids,
        valid_continuidad_ids,
    )
    _inject_localized_translations(merged_revisions, modelo_translations, revision_translations)
