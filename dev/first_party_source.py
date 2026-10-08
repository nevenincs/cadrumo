"""The repository's first-party source roots, and what is production inside them.

Every development instrument that measures "the code" answers two questions:
which trees it reads, and which files in those trees are production rather than
test support or bundled data. Both answers live here, so two instruments can
only disagree about a file because they measure different named scopes, never
because each spelled the convention its own way.

Roots
    :data:`PRODUCT_PACKAGE` is the tax-filing product. :data:`HARNESS_PACKAGE`
    is the separately shipped agent harness. :data:`DEVELOPMENT_TOOLING` builds
    and verifies them, and :data:`PACKAGING_HOOKS` holds the distribution build
    hooks. :data:`FIRST_PARTY_ROOTS` names all four.

Named scopes
    An instrument measures every first-party root or a named subset, and the
    subset's reason is recorded here:

    * :data:`FIRST_PARTY_ROOTS` -- complexity, and any detector whose subject
      may appear in any maintained code (the regulatory-prose parser channel),
      reads every root, tooling included.
    * :data:`PRODUCT_PACKAGE` alone -- dead code, copy-paste and semantic
      duplication, and the stock security scan measure the shipped product.
      Development tooling exists to verify the product, so its debt would be
      misreported as product risk in those numbers.
    * :data:`DEPENDENCY_DECLARATION_ROOTS` -- the code whose third-party
      imports must be satisfied by declared, non-development dependencies: the
      product, the harness, and the registry tooling that runs from its own
      dependency group.

Classification
    The test surface is every module under a ``tests`` directory, every
    ``test_*`` or ``_test_*`` module, and every ``conftest.py``. Bundled data is
    everything under a ``_data`` directory. Production source is a Python
    module that is neither. :func:`is_test_module_name` applies the same
    convention to a dotted module name, and :func:`production_exclusion_globs`
    renders its complement for tools that only accept ignore globs.

    Classification reads only the segments of the path it is given, so that
    path must be relative: to the repository, or to the ``root`` passed with
    it. An absolute path is refused, because its checkout-location segments
    would be classified too, and a clone under a directory named ``tests``
    would read as nothing but test code.
"""

from __future__ import annotations

from pathlib import PurePath, PurePosixPath
from typing import Final

PRODUCT_PACKAGE: Final[str] = "src/cadrumo"
HARNESS_PACKAGE: Final[str] = "src/cadrumo_harness"
DEVELOPMENT_TOOLING: Final[str] = "dev"
PACKAGING_HOOKS: Final[str] = "packaging"

FIRST_PARTY_ROOTS: Final[tuple[str, ...]] = (PRODUCT_PACKAGE, HARNESS_PACKAGE, DEVELOPMENT_TOOLING, PACKAGING_HOOKS)
DEPENDENCY_DECLARATION_ROOTS: Final[tuple[str, ...]] = (
    PRODUCT_PACKAGE,
    HARNESS_PACKAGE,
    f"{DEVELOPMENT_TOOLING}/registry",
)

TEST_DIRECTORY: Final[str] = "tests"
BUNDLED_DATA_DIRECTORY: Final[str] = "_data"
TEST_MODULE_PREFIXES: Final[tuple[str, ...]] = ("test_", "_test_")
PYTEST_CONFTEST: Final[str] = "conftest.py"
_PYTHON_SUFFIX: Final[str] = ".py"


def _relative_parts(path: str | PurePath, root: str | PurePath | None) -> tuple[str, ...]:
    """Return the classified segments of ``path``, refusing an absolute one."""
    located = PurePath(path).relative_to(root) if root is not None else PurePath(path)
    if located.is_absolute() or PurePosixPath(located.as_posix()).is_absolute():
        raise ValueError(f"source classification needs a relative path or its root, not {path!s}")
    return PurePosixPath(located.as_posix()).parts


def is_test_source(path: str | PurePath, *, root: str | PurePath | None = None) -> bool:
    """Return whether ``path`` belongs to the test surface.

    Args:
        path: A relative path, or a path inside ``root``.
        root: The directory ``path`` is classified relative to, when given.
    """
    parts = _relative_parts(path, root)
    if not parts:
        return False
    leaf = parts[-1]
    return TEST_DIRECTORY in parts[:-1] or leaf.startswith(TEST_MODULE_PREFIXES) or leaf == PYTEST_CONFTEST


def is_bundled_data(path: str | PurePath, *, root: str | PurePath | None = None) -> bool:
    """Return whether ``path`` lies under a bundled-data directory."""
    return BUNDLED_DATA_DIRECTORY in _relative_parts(path, root)[:-1]


def is_production_source(path: str | PurePath, *, root: str | PurePath | None = None) -> bool:
    """Return whether ``path`` is a production Python module."""
    return (
        PurePath(path).suffix == _PYTHON_SUFFIX
        and not is_test_source(path, root=root)
        and not is_bundled_data(path, root=root)
    )


def is_test_module_name(module: str) -> bool:
    """Return whether the dotted ``module`` name belongs to the test surface."""
    parts = module.split(".")
    leaf = parts[-1]
    return TEST_DIRECTORY in parts or leaf.startswith(TEST_MODULE_PREFIXES) or leaf == PurePath(PYTEST_CONFTEST).stem


def production_exclusion_globs() -> tuple[str, ...]:
    """Return everything :func:`is_production_source` rejects, as recursive globs."""
    return (
        f"**/{TEST_DIRECTORY}/**",
        f"**/{BUNDLED_DATA_DIRECTORY}/**",
        *(f"**/{prefix}*{_PYTHON_SUFFIX}" for prefix in TEST_MODULE_PREFIXES),
        f"**/{PYTEST_CONFTEST}",
    )
