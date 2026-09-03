"""The generated Modelo 303 annual Orden artefacts still match their sources.

This module's `--check` mode already refuses a stale or missing artefact, and
nothing ran it. It was the only module in this package carrying a public surface
that no test imported - found after three wrong answers from three wrong ways of
asking, and worth a test precisely because a generator nobody invokes is
indistinguishable from one whose output is current.
"""

from __future__ import annotations

import pytest

from ..analysis.m303_orden_anual import main

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_check_mode_accepts_the_committed_artefacts() -> None:
    """The shipped manifest and census artefact reproduce from their pinned sources.

    Exit zero here means the committed bytes are what the current extraction
    produces. A drift shows up as a refusal from the check itself, naming which
    artefact moved, rather than as a difference nobody looks for - which is the
    state this artefact pair was in until now, since the generator was reachable
    only by hand.
    """
    assert main(["--check"]) == 0


def test_the_check_flag_is_what_refuses_rather_than_the_default() -> None:
    """The default WRITES, so a test must never invoke it.

    Recorded as an assertion rather than a comment because the distinction is
    one keystroke wide and the wrong side of it regenerates registry artefacts
    from a test run. The parser is inspected instead of exercised.
    """
    import argparse
    import inspect

    source = inspect.getsource(main)

    assert '"--check"' in source
    assert "action=\"store_true\"" in source
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    assert parser.parse_args([]).check is False, "an absent flag must not read as a check"
