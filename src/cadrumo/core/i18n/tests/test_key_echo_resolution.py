"""Direct coverage for the renderer's key-echo miss branch.

A catalogue value equal to its own key is the scaffold placeholder for
"declared but not translated yet", so resolution must treat it exactly
like an absent key. The shipped catalogues are gated echo-free, so the
branch can only be exercised against a fixture catalogue resolved
through :func:`_override_locales_root`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..render import _I18N_STRICT_MISSING_KEYS, MissingTranslationError, _override_locales_root, tr

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ECHO_KEY = "probe.echo"
_AUTHORED_KEY = "probe.authored"
_AUTHORED_VALUE = "Authored probe value"


@pytest.fixture
def fixture_locales_root(tmp_path: Path) -> Path:
    """Return a locales root whose catalogue plants one key-echo defect."""
    (tmp_path / "en.yml").write_text(
        f"probe:\n  echo: '{_ECHO_KEY}'\n  authored: '{_AUTHORED_VALUE}'\n",
        encoding="utf-8",
    )
    return tmp_path


def test_key_echo_value_is_a_miss_under_strict_mode(fixture_locales_root: Path) -> None:
    """A value equal to its own key refuses exactly like an absent key."""
    with _override_locales_root(fixture_locales_root):
        assert tr(_AUTHORED_KEY, locale="en") == _AUTHORED_VALUE
        with pytest.raises(MissingTranslationError) as excinfo:
            tr(_ECHO_KEY, locale="en")

    assert excinfo.value.key == _ECHO_KEY
    assert excinfo.value.locale == "en"


def test_key_echo_honours_the_explicit_default_opt_out(fixture_locales_root: Path) -> None:
    """A caller supplying ``default`` gets the fallback, not the echo."""
    with _override_locales_root(fixture_locales_root):
        rendered = tr(_ECHO_KEY, locale="en", default="explicit fallback")

    assert rendered == "explicit fallback"


def test_key_echo_humanises_outside_strict_mode(fixture_locales_root: Path) -> None:
    """Production mode renders the echo through the humanised-miss fallback."""
    token = _I18N_STRICT_MISSING_KEYS.set(False)
    try:
        with _override_locales_root(fixture_locales_root):
            rendered = tr(_ECHO_KEY, locale="en")
    finally:
        _I18N_STRICT_MISSING_KEYS.reset(token)

    # The raw key must never surface; the fallback derives a label instead.
    assert rendered != _ECHO_KEY
    assert "probe." not in rendered


def test_override_scope_ends_with_the_context(fixture_locales_root: Path) -> None:
    """Outside the override, resolution returns to the packaged catalogues."""
    with _override_locales_root(fixture_locales_root):
        assert tr(_AUTHORED_KEY, locale="en") == _AUTHORED_VALUE
    with pytest.raises(MissingTranslationError) as excinfo:
        tr(_AUTHORED_KEY, locale="en")

    assert excinfo.value.key == _AUTHORED_KEY
