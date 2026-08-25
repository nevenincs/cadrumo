"""Gate: every Cadrumo container derives from ONE declared Linux base image.

Three container surfaces exist in this repository and they are related, not
independent:

* the devcontainer development image (repository-root ``Dockerfile``),
* the clean-Linux wheel-install proof (:mod:`dev.packaging.smoke_docker`), which
  runs NESTED inside the self-hosted Linux runner containers through the mounted
  host docker socket,
* the self-hosted runner containers themselves, which are a different family
  (``ghcr.io/actions/actions-runner``) and deliberately out of scope here.

The first two MUST share a base. They previously each wrote the string
``python:3.13-slim`` out by hand, with a Dockerfile comment claiming they
"stay on one Linux base convention" and nothing enforcing it. That is exactly
the shape that rots: ``python:3.13-slim`` is a MOVING tag, it rolled from Debian
12 (bookworm) to Debian 13 (trixie), and trixie's 64-bit ``time_t`` transition
renamed every ABI-bearing library the Dockerfile installs to a ``t64`` suffix.
Cache-cold builds broke while cache-warm machines kept passing.

This gate holds the seam closed:

1. The ``Dockerfile`` is the single declaration point (``ARG PYTHON_BASE_IMAGE``).
2. ``smoke_docker``'s ``--image`` default resolves to that same declaration
   rather than to an independently written literal.
3. No container surface re-declares a bare ``python:3.13-*`` literal.
4. The declared tag pins the DISTRIBUTION, not merely the Python minor, so the
   Dockerfile's explicit apt package list cannot be invalidated by a silent
   base-image distro roll.
"""

from __future__ import annotations

import ast
import re

import pytest

from ..._paths import REPO_ROOT
from .._base_image import dockerfile_path, linux_base_image

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = REPO_ROOT

# Distributions whose package names the Dockerfile's explicit apt list is
# written against. A base tag that does not pin one of these is a moving
# target and may re-break the apt layer without any change in this repository.
_PINNED_DISTRIBUTIONS = ("trixie", "bookworm")


def test_dockerfile_is_the_single_base_image_declaration() -> None:
    """The Dockerfile declares the base image and the resolver reads it back."""
    declared = linux_base_image()

    assert declared, "the Dockerfile must declare a non-empty PYTHON_BASE_IMAGE"
    assert dockerfile_path().is_file()
    # The FROM must consume the ARG rather than restate the image.
    dockerfile = dockerfile_path().read_text(encoding="utf-8")
    assert "FROM ${PYTHON_BASE_IMAGE}" in dockerfile, (
        "the base stage must build FROM the declared ARG, not from a repeated literal"
    )


def test_declared_base_pins_the_distribution() -> None:
    """The tag pins a Debian release, so the explicit apt list stays truthful."""
    declared = linux_base_image()

    assert any(distribution in declared for distribution in _PINNED_DISTRIBUTIONS), (
        f"{declared!r} does not pin a Debian release. `python:3.13-slim` is a moving tag: "
        "it rolled bookworm -> trixie and the trixie t64 library rename broke the "
        "Dockerfile's apt layer on every cache-cold build. Pin the distribution "
        f"(one of {_PINNED_DISTRIBUTIONS}) or update the apt package list with it."
    )


def test_smoke_docker_binds_its_image_default_to_the_resolver() -> None:
    """`smoke_docker --image` derives its default; it does not restate a literal.

    Asserted structurally against the module's AST rather than by comparing the
    resolver's return value to itself, which would pass no matter what the
    shipped default was.
    """
    module_path = _REPO_ROOT / "dev" / "packaging" / "smoke_docker.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))

    defaults = [
        keyword.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "--image"
        for keyword in node.keywords
        if keyword.arg == "default"
    ]

    assert len(defaults) == 1, f"expected exactly one `--image` default, found {len(defaults)}"
    default = defaults[0]

    assert not isinstance(default, ast.Constant), (
        "`--image` binds a hardcoded literal default. It must derive from "
        "`linux_base_image()` so the packaging proof cannot drift off the "
        "Dockerfile's declared base."
    )
    assert isinstance(default, ast.Call) and isinstance(default.func, ast.Name), (
        "`--image` default must be a direct call to the base-image resolver"
    )
    assert default.func.id == "linux_base_image"


def test_no_surface_restates_a_bare_python_base_literal() -> None:
    """No container surface writes its own `python:3.13-*` literal."""
    surfaces = (
        _REPO_ROOT / "Dockerfile",
        _REPO_ROOT / "dev" / "packaging" / "smoke_docker.py",
        _REPO_ROOT / "justfile",
    )
    bare_literal = re.compile(r"python:3\.13[-\w.]*")

    offenders: list[str] = []
    for surface in surfaces:
        text = surface.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not bare_literal.search(line):
                continue
            # The one sanctioned occurrence is the declaration itself.
            if surface.name == "Dockerfile" and line.strip().startswith("ARG PYTHON_BASE_IMAGE="):
                continue
            # Prose explaining the historical moving-tag hazard is not a declaration.
            if line.lstrip().startswith("#"):
                continue
            offenders.append(f"{surface.relative_to(_REPO_ROOT)}:{line_number}: {line.strip()}")

    assert not offenders, (
        "these lines re-declare the Linux base image instead of deriving it from "
        "`ARG PYTHON_BASE_IMAGE` in the repository-root Dockerfile:\n  " + "\n  ".join(offenders)
    )
