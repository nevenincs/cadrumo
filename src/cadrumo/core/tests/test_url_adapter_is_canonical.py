"""The absolute-HTTP-URL validator has exactly one definition.

Six modules each built their own ``TypeAdapter(AnyHttpUrl)`` under four
different names. The adapter is stateless and identical wherever it is
constructed, so every copy was a duplicate.

The gate deliberately scopes itself to ``AnyHttpUrl`` and leaves
``TypeAdapter(HttpUrl)`` alone. Those are different validators -- ``HttpUrl``
constrains the scheme, ``AnyHttpUrl`` does not -- and one of the displaced
names, ``_URL_ADAPTER``, was in use for BOTH. Merging on the name rather than
the validated type would have swapped a stricter check for a weaker one.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest
from pydantic import HttpUrl, TypeAdapter

from ..url_validation import ANY_HTTP_URL_ADAPTER

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parents[2]


def test_the_canonical_adapter_validates_an_absolute_http_url() -> None:
    """Pin the behaviour, so the scan below cannot pass over a hollowed-out name."""
    assert ANY_HTTP_URL_ADAPTER.validate_python("https://example.test/path")

    with pytest.raises(ValueError, match="URL"):
        ANY_HTTP_URL_ADAPTER.validate_python("not-a-url")


def test_the_canonical_adapter_is_not_the_length_limited_validator() -> None:
    """`AnyHttpUrl` and `HttpUrl` must stay distinguishable.

    Both reject a non-http scheme, so scheme is not what separates them. What
    does is length: ``HttpUrl`` enforces a maximum the other does not. If a
    future edit repointed this module at ``HttpUrl``, every call site would
    silently begin rejecting long URLs it previously accepted, and no
    scheme-based assertion would notice.
    """
    long_url = "https://" + ("a" * 2090) + ".test/"

    assert ANY_HTTP_URL_ADAPTER.validate_python(long_url)

    with pytest.raises(ValueError, match="URL"):
        TypeAdapter(HttpUrl).validate_python(long_url)


def _builds_any_http_url_adapter(path: Path) -> list[str]:
    """Return module-level names bound to ``TypeAdapter(AnyHttpUrl)``."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    found: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if isinstance(target, ast.Name) and ast.unparse(value) == "TypeAdapter(AnyHttpUrl)":
            found.append(target.id)
    return found


def test_no_module_builds_its_own_absolute_url_adapter() -> None:
    """`core.url_validation` is the only module that may construct this validator."""
    modules = [
        path for path in _PACKAGE_ROOT.rglob("*.py") if "tests" not in path.parts and path.name != "url_validation.py"
    ]

    assert len(modules) > 500, (
        f"only {len(modules)} modules were enumerated; the scan collapsed, so an empty "
        "result below would mean 'nothing was searched' rather than 'no duplicates exist'"
    )

    offenders = {
        path.relative_to(_PACKAGE_ROOT).as_posix(): names
        for path in modules
        if (names := _builds_any_http_url_adapter(path))
    }

    assert offenders == {}, (
        "module(s) build their own TypeAdapter(AnyHttpUrl) instead of importing "
        f"ANY_HTTP_URL_ADAPTER from core.url_validation: {offenders}"
    )
