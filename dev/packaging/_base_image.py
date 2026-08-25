"""Resolve the one Linux base image every Cadrumo container derives from.

The base is declared EXACTLY ONCE, as the ``PYTHON_BASE_IMAGE`` build
argument's default in the repository-root ``Dockerfile``. A Dockerfile ``ARG``
default has to be a literal — it cannot read a constant from elsewhere — so the
Dockerfile is the declaration and every other consumer reads it back from
there. That keeps the devcontainer image and the clean-Linux packaging proof on
one distribution by construction rather than by comment.

The previous shape had the string written out twice: ``FROM python:3.13-slim``
in the Dockerfile and ``--image python:3.13-slim`` as an argparse default in
:mod:`dev.packaging.smoke_docker`, with a Dockerfile comment asserting the two
"stay on one Linux base convention" and nothing enforcing it. They drifted the
moment either moved.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8

_ARG_PATTERN: Final = re.compile(r"^\s*ARG\s+PYTHON_BASE_IMAGE=(?P<image>\S+)\s*$", re.MULTILINE)
_UTF_8: Final[str] = UTF_8


def dockerfile_path() -> Path:
    """Return the repository-root ``Dockerfile`` that declares the base image."""
    return REPO_ROOT / "Dockerfile"


def linux_base_image() -> str:
    """Return the declared Linux base image reference.

    Raises:
        RuntimeError: when the ``Dockerfile`` is missing or no longer declares a
            ``PYTHON_BASE_IMAGE`` build argument. Failing loudly is the point:
            a silent fallback default would reintroduce the duplicate
            declaration this module exists to remove.
    """
    path = dockerfile_path()
    try:
        text = path.read_text(encoding=_UTF_8)
    except OSError as error:  # pragma: no cover - filesystem-level failure
        raise RuntimeError(f"cannot read the base-image declaration at {path}: {error}") from error

    match = _ARG_PATTERN.search(text)
    if match is None:
        raise RuntimeError(
            f"{path} declares no `ARG PYTHON_BASE_IMAGE=<image>` line; "
            "it is the single declaration point for the shared Linux base image."
        )
    return match.group("image")
