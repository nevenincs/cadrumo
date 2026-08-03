"""Discover the path-valued settings fields the storage gates classify.

Selection is by **annotation**, never by name suffix, and the difference is not
theoretical. Measured against the live model: a suffix-and-``Path`` selector
finds 35 fields while annotation alone finds 38, and among the delta is
``cadrumo_libreoffice_executable`` -- classified nowhere for as long as the
suffix selector was the discovery mechanism, because it ends in none of
``_dir``, ``_path``, or ``_root``. A field must not be able to hide from a gate
by being named inconveniently.

The selector reads annotations for the converse reason too.
``aeat_sede_expedientes_path`` and ``aeat_status_notificaciones_path`` are
``str`` AEAT URL segments, not filesystem paths; a name-only selector would
over-select both and demand a storage classification for a URL.

Both directions are pinned as positive controls in
:mod:`~core.tests.test_storage_binding_gate`, so a future narrowing back to
name matching fails loudly rather than silently shrinking what the gates cover.
"""

from __future__ import annotations

from pathlib import Path
from types import UnionType
from typing import TYPE_CHECKING, Union, get_args, get_origin

if TYPE_CHECKING:
    from pydantic import BaseModel


def annotation_mentions_path(annotation: object) -> bool:
    """Whether ``annotation`` is ``Path`` or a union containing it.

    Optional path fields (``Path | None``) are path fields: an opt-in override
    that is unset today still names a filesystem location when it is set.
    """
    origin = get_origin(annotation)
    members: tuple[object, ...] = get_args(annotation) if origin in (Union, UnionType) else (annotation,)
    return any(member is Path for member in members)


def path_typed_settings_fields(model: type[BaseModel]) -> frozenset[str]:
    """Return every field on ``model`` whose annotation admits a :class:`~pathlib.Path`.

    Args:
        model: The settings model to introspect. Passed in rather than imported
            so the selector itself can be exercised against a synthetic model.

    Returns:
        The discovered field names.
    """
    return frozenset(
        name for name, field_info in model.model_fields.items() if annotation_mentions_path(field_info.annotation)
    )
