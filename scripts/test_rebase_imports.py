"""Test fixture for ``scripts.rebase_imports``.

Per the restructure ADR Acceptance criteria, the rebase script must
correctly handle every import shape the project actually uses:
relative imports, `TYPE_CHECKING` blocks, star imports, dynamic
`importlib.import_module` calls, and quoted dotted-names in
configuration strings.

This test file exercises each shape against the live rewrite map.
It is intentionally NOT colocated with `src/aeat/` so the rebase
script does not rewrite its own fixture mid-run.
"""

from __future__ import annotations

import textwrap

import pytest
from rebase_imports import load_rewrite_rules, rewrite_text

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


@pytest.fixture(scope="module")
def forward_rules() -> tuple:
    """Forward (OLD -> NEW) rewrite rules."""
    return load_rewrite_rules(reverse=False)


@pytest.fixture(scope="module")
def reverse_rules() -> tuple:
    """Reverse (NEW -> OLD) rewrite rules; rollback symmetric pair."""
    return load_rewrite_rules(reverse=True)


def test_absolute_import_form_rewrites(forward_rules: tuple) -> None:
    """`from aeat.X import Y` becomes `from aeat.<new-bucket>.X import Y`."""
    text = "from aeat.errors import AeatError\n"
    out = rewrite_text(text, forward_rules)
    assert out == "from aeat.core.errors import AeatError\n"


def test_top_level_import_form_rewrites(forward_rules: tuple) -> None:
    """`import aeat.X` becomes `import aeat.<new-bucket>.X`."""
    text = "import aeat.formulas\n"
    out = rewrite_text(text, forward_rules)
    assert out == "import aeat.domain.formulas\n"


def test_quoted_dotted_name_rewrites(forward_rules: tuple) -> None:
    """`importlib.import_module("aeat.X")` rewrites the string."""
    text = 'importlib.import_module("aeat.formulas")\n'
    out = rewrite_text(text, forward_rules)
    assert "aeat.domain.formulas" in out


def test_type_checking_block_rewrites(forward_rules: tuple) -> None:
    """Imports inside a TYPE_CHECKING block rewrite the same way."""
    text = textwrap.dedent("""\
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from aeat.errors import AeatError
        """)
    out = rewrite_text(text, forward_rules)
    assert "from aeat.core.errors import AeatError" in out


def test_star_import_rewrites(forward_rules: tuple) -> None:
    """`from aeat.X import *` becomes `from aeat.<new>.X import *`."""
    text = "from aeat.errors import *\n"
    out = rewrite_text(text, forward_rules)
    assert out == "from aeat.core.errors import *\n"


def test_longest_prefix_wins(forward_rules: tuple) -> None:
    """`aeat.cli` rewrites to `aeat.entrypoints.cli` even when `aeat.cli.X` is requested."""
    text = "from aeat.cli.something import app\n"
    out = rewrite_text(text, forward_rules)
    assert out == "from aeat.entrypoints.cli.something import app\n"


def test_unrelated_imports_unchanged(forward_rules: tuple) -> None:
    """Imports of other packages or non-aeat dotted-names are untouched."""
    text = textwrap.dedent("""\
        import os
        from pathlib import Path
        from third_party.aeat_alike import x  # not our aeat
        """)
    out = rewrite_text(text, forward_rules)
    assert out == text


def test_substring_match_does_not_misfire(forward_rules: tuple) -> None:
    """A dotted name that has `aeat.errors` as substring (e.g. `aeat.errors_extra`) is left alone."""
    text = "from aeat.errors_extra import something\n"
    out = rewrite_text(text, forward_rules)
    assert out == text


def test_round_trip_forward_then_reverse_is_identity(forward_rules: tuple, reverse_rules: tuple) -> None:
    """Apply forward rewrites then reverse rewrites; the result equals the input."""
    text = textwrap.dedent("""\
        from aeat.errors import AeatError
        from aeat.formulas import Engine
        from aeat.cli.financial import app
        import aeat.storage
        importlib.import_module("aeat.casillas")
        """)
    forward = rewrite_text(text, forward_rules)
    back = rewrite_text(forward, reverse_rules)
    assert back == text


def test_rewrite_handles_multiple_imports_in_one_line(forward_rules: tuple) -> None:
    """Comma-separated multi-symbol imports rewrite cleanly."""
    text = "from aeat.errors import AeatError, ErrorCode, ErrorEnvelope\n"
    out = rewrite_text(text, forward_rules)
    assert out == "from aeat.core.errors import AeatError, ErrorCode, ErrorEnvelope\n"


def test_rewrite_preserves_indentation(forward_rules: tuple) -> None:
    """Imports inside indented blocks (TYPE_CHECKING / inside a function) preserve indent."""
    text = "    from aeat.errors import AeatError\n"
    out = rewrite_text(text, forward_rules)
    assert out == "    from aeat.core.errors import AeatError\n"
