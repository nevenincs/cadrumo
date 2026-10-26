"""Where the built Cadrumo binary that runs the ``components`` role is, or that this build has none.

An interpreter the Cadrumo binary hosts is told that binary's path by the
``-X`` option it passes, and that binary runs the role. Otherwise an installed
package names its one desktop image, the Cadrumo binary, in its package
manifest beside the package interpreter. A source checkout has no package; a
developer names a built binary with :data:`DEVELOPMENT_ROLE_IMAGE_VARIABLE`,
which only a checkout honours. Without one of these there is no binary, and
every component reads as not in this build.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from ....core.package_interpreter import ROLE_IMAGE_OPTION
from ....core.storage_environment import StorageMode, storage_mode

__all__ = ["DEVELOPMENT_ROLE_IMAGE_VARIABLE", "components_role_image"]

DEVELOPMENT_ROLE_IMAGE_VARIABLE: Final = "CADRUMO_DEVELOPMENT_ROLE_IMAGE"
"""The built Cadrumo binary a source checkout runs its native roles with; no packaged image admits it."""

_PACKAGE_MANIFEST: Final = ("data", "package-manifest.json")
_MANIFEST_BYTES_LIMIT: Final = 64 * 1024 * 1024


def _hosting_image() -> Path | None:
    options: object = getattr(sys, "_xoptions", {})
    image = options.get(ROLE_IMAGE_OPTION) if isinstance(options, dict) else None
    if not isinstance(image, str) or not image:
        return None
    path = Path(image)
    return path if path.is_absolute() and path.is_file() else None


def _relative_parts(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        return None
    parts = tuple(value.split("/"))
    return None if any(part in {"", ".", ".."} for part in parts) else parts


def _inside(root: Path, parts: tuple[str, ...]) -> Path | None:
    try:
        resolved = root.joinpath(*parts).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return resolved if resolved.is_relative_to(root) else None


def _package_image(interpreter: Path) -> Path | None:
    """The desktop image the package manifest beside ``interpreter`` declares, when that file exists."""
    try:
        resolved_interpreter = interpreter.resolve(strict=True)
        root = resolved_interpreter.parent
        manifest_path = _inside(root, _PACKAGE_MANIFEST)
        if manifest_path is None or manifest_path.stat().st_size > _MANIFEST_BYTES_LIMIT:
            return None
        layout = json.loads(manifest_path.read_bytes())["layout"]
        executable = _relative_parts(layout["paths"]["executable"])
        if executable is None or _inside(root, executable) != resolved_interpreter:
            return None
        images = [image for image in layout["application_images"] if image.get("desktop") is True]
        if len(images) != 1:
            return None
        name = _relative_parts(images[0]["name"] + layout["entrypoint_suffix"])
        placement = () if images[0]["placement"] == "." else _relative_parts(images[0]["placement"])
        if name is None or placement is None or len(name) != 1:
            return None
        candidate = _inside(root, (*placement, *name))
        return candidate if candidate is not None and candidate.is_file() else None
    except (OSError, RuntimeError, KeyError, TypeError, ValueError, AttributeError, RecursionError):
        return None


def _development_image(environ: Mapping[str, str]) -> Path | None:
    value = environ.get(DEVELOPMENT_ROLE_IMAGE_VARIABLE, "").strip()
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() and path.is_file() else None


def components_role_image(*, environ: Mapping[str, str] | None = None) -> Path | None:
    """Return the Cadrumo binary that runs the components role, or ``None`` when this build has none."""
    hosting = _hosting_image()
    if hosting is not None:
        return hosting
    if storage_mode().mode is StorageMode.DEVELOPMENT:
        return _development_image(os.environ if environ is None else environ)
    return _package_image(Path(sys.executable))
