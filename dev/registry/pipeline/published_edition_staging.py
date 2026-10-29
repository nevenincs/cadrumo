"""Stage isolated published editions and their supporting registry models."""

from __future__ import annotations

import re
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import cast

from cadrumo.core.i18n.render import locale_map, override_locales_root
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_occurrence_locale_key,
)

from ..compiler.edition_materialisation import MaterialisedEdition, materialise_edition
from .candidate_source_chain import stage_source_chain
from .candidate_staging import stage_attested_inherited_modelo
from .edition_candidate_staging import (
    drop_cross_edition_evolutions,
    edition_requires_detachment,
    write_complete_edition,
)
from .generated_export_inheritance_model import GeneratedExportInheritanceContext

_SOURCE_MODELO_RE = re.compile(r'^\s*source_modelo\s*=\s*"(?P<modelo>[^"]+)"', re.MULTILINE)


@cache
def supporting_modelos(modelo: str) -> frozenset[str]:
    """Return declared cross-modelo dependencies that isolated validation needs."""
    modelos_root = bundled_path("registry", "aeat", "modelos")
    source_modelo_root = modelos_root / modelo
    referenced = {
        str(match.group("modelo"))
        for path in source_modelo_root.rglob("*.toml")
        for match in _SOURCE_MODELO_RE.finditer(path.read_text(encoding="utf-8"))
    }
    return frozenset(item for item in referenced - {modelo} if (modelos_root / item).is_dir())


def stage_published_modelo(
    root: Path,
    *,
    modelo: str,
    revision: str,
    inheritance: GeneratedExportInheritanceContext | None = None,
    retain_source_chain: bool = False,
) -> Path | None:
    """Stage a one-revision published modelo only when check needs the witness.

    The witness is staged in registry shape with the published authored facts
    and shared legal catalogues beside it, because loading a modelo validates
    its bindings against the governed facts and filing-year envelope of the
    registry that holds it and refuses without them.
    """
    source_registry_root = bundled_path("registry", "aeat")
    source_modelo_root = source_registry_root / "modelos" / modelo
    revisions = tuple((source_modelo_root / "revisions").iterdir())
    if len(revisions) == 1:
        return None
    staged_registry_root = root / "published-registry" / "aeat"
    shutil.copytree(source_registry_root / "facts", staged_registry_root / "facts")
    shutil.copytree(source_registry_root / "legal", staged_registry_root / "legal")
    if retain_source_chain:
        return stage_source_chain(
            source_modelo_root,
            staged_registry_root / "modelos" / modelo,
            revision=revision,
            include_target_export=True,
        )
    if inheritance is not None:
        return stage_attested_inherited_modelo(
            source_modelo_root,
            staged_registry_root / "modelos" / modelo,
            revision=revision,
            inheritance=inheritance,
            include_target_export=True,
        )
    staged = stage_isolated_edition(
        source_modelo_root,
        staged_registry_root / "modelos" / modelo,
        revision=revision,
        source_locales_root=bundled_path().parent / "locales",
        staged_locales_root=root / "published-locales",
    )
    return staged.modelo_root


@dataclass(frozen=True, slots=True)
class _StagedEdition:
    """An isolated edition and the catalogue its casilla labels resolve from."""

    modelo_root: Path
    locales_root: Path


def stage_isolated_edition(
    source_modelo_root: Path,
    staged_root: Path,
    *,
    revision: str,
    source_locales_root: Path,
    staged_locales_root: Path,
) -> _StagedEdition:
    """Stage ``revision`` as the only edition of a copy of its modelo, complete by construction.

    Pruning the sibling editions is what isolates the target, and it is exactly
    what an edition inheriting from a predecessor cannot survive: its chain
    would be deleted with them. Such an edition is therefore resolved first and
    written back as the full-copy edition it stands for, naming no predecessor,
    so the staged tree never presents the rows it states as the whole edition.
    An edition whose named predecessor is absent from the source is refused by
    that resolution rather than staged thin. An edition stating every row is
    copied unchanged and keeps resolving its labels from the source catalogue.

    The labels travel with the rows. Casilla labels are catalogued per edition,
    so an inherited row's text lives under the key of the edition that last
    stated it, and a full copy names no predecessor through which to reach it.
    The staged catalogue is a copy of the source catalogue in which each
    inherited row's own occurrence key carries its origin's text, in each
    locale where the row has no text of its own, so every staged label resolves
    to exactly what the live edition resolves.
    """
    from dev.locales.locale_yaml import discover_locale_codes
    from dev.locales.manager import LocaleManager

    edition = materialise_edition(source_modelo_root, revision)
    shutil.copytree(source_modelo_root, staged_root)
    revisions_root = staged_root / "revisions"
    for entry in revisions_root.iterdir():
        if entry.name != revision:
            shutil.rmtree(entry)
    if not edition_requires_detachment(edition):
        drop_cross_edition_evolutions(revisions_root / revision)
        return _StagedEdition(modelo_root=staged_root, locales_root=source_locales_root)
    write_complete_edition(revisions_root / revision, edition)
    drop_cross_edition_evolutions(revisions_root / revision)
    if edition.inherits_from is None:
        # A storage-baseline edition restates rows under its own keys; only a
        # predecessor chain moves label text onto inherited occurrences.
        return _StagedEdition(modelo_root=staged_root, locales_root=source_locales_root)
    shutil.copytree(source_locales_root, staged_locales_root)
    manager = LocaleManager(src_dir=staged_locales_root, locales_dir=staged_locales_root)
    for locale in sorted(discover_locale_codes(staged_locales_root)):
        carried = _inherited_labels(edition, source_locales_root, locale=locale)
        if carried:
            manager.set_locale_values(locale, carried)
    return _StagedEdition(modelo_root=staged_root, locales_root=staged_locales_root)


def _inherited_labels(edition: MaterialisedEdition, source_locales_root: Path, *, locale: str) -> dict[str, str | None]:
    """Return the origin text each inherited row needs under its own occurrence key in ``locale``."""
    rows = edition.table.get("casillas")
    origins = edition.label_origins
    if origins is None or not isinstance(rows, tuple) or len(cast(tuple[object, ...], rows)) != len(origins):
        raise ValueError(
            f"edition {edition.revision_id!r} of modelo {edition.modelo_id!r} carries no label origin per casilla",
        )
    with override_locales_root(source_locales_root):
        catalogue = locale_map(locale)
    carried: dict[str, str | None] = {}
    for row, origin in zip(cast(tuple[object, ...], rows), origins, strict=True):
        casilla_id = cast(Mapping[str, object], row).get("id") if isinstance(row, Mapping) else None
        if origin is None or not isinstance(casilla_id, str):
            continue
        own_key = casilla_occurrence_locale_key(
            edition.modelo_id, edition.revision_id, casilla_id, ModeloLocalizationFieldKind.LABEL
        )
        origin_key = casilla_occurrence_locale_key(
            edition.modelo_id, origin, casilla_id, ModeloLocalizationFieldKind.LABEL
        )
        origin_text = _authored_text(catalogue, origin_key)
        if origin_text is not None and _authored_text(catalogue, own_key) is None:
            carried[own_key] = origin_text
    return carried


def _authored_text(catalogue: Mapping[str, str | None], key: str) -> str | None:
    """Apply the catalogue's miss rule: an absent key, a null and a key echo all carry no text."""
    value = catalogue.get(key)
    return None if value is None or value == key else value
