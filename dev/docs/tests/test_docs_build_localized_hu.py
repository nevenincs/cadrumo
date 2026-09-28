"""Hungarian user-scope nitpicky docs build gate.

One module per translation target, because pytest-xdist distributes by file: the
three language builds are multi-minute each, and carried together they serialise
on one worker while the rest of the lane idles. The shared runner and the
language-set coverage gate live beside this module
(:mod:`dev.docs.tests._localized_build_support`,
``test_docs_build_localized``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ._localized_build_support import assert_localized_user_scope_build_is_nitpicky_clean

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs, pytest.mark.timeout(1800)]


def test_hungarian_user_scope_build_is_nitpicky_clean(tmp_path: Path) -> None:
    """The Hungarian user-scope ``-n -W`` build succeeds.

    Args:
        tmp_path: Pytest-provided isolated output directory.
    """
    assert_localized_user_scope_build_is_nitpicky_clean(tmp_path, "hu")
