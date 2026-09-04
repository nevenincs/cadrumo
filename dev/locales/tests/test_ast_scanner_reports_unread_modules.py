"""The locale scanner must say which modules it could not read.

`_iter_parseable_python_modules` feeds every locale-key scan. Three silences
were stacked in it: a lenient decode dropped undecodable bytes so the text
scanned was not the file, a read failure was logged at debug level, and a parse
failure was swallowed the same way.

All three shrink the set of DECLARED keys, and a key never seen declared looks
unused. That is how a cleanup sweep deletes a live translation - not a
hypothetical for this scanner, which once put seventy-seven catalogue entries on
the deletion path because it did not know four key factories.

The skip itself stays: this walks thousands of modules while the tree is edited,
and one unreadable file must not cost the scan. Measured: 2119 modules declare
locale keys, none undecodable, none unparsable, 4299 keys scanned.
"""

from __future__ import annotations

import pathlib

import pytest

from .._ast_scanner import scan_source_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DECLARING_SOURCE = 'raise CadrumoError("cli.config.profile.missing")' + chr(10)


def test_an_undecodable_module_is_announced_rather_than_silently_mangled(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A dropped byte changes the source, so a key can vanish from the scan.

    With a lenient decode the scanner read text the file does not contain and
    said nothing, which is the worst shape: the key it failed to see is then
    reported unused.
    """
    (tmp_path / "sound.py").write_text(_DECLARING_SOURCE, encoding="utf-8")
    (tmp_path / "undecodable.py").write_bytes(bytes([0xFF, 0xFE]) + _DECLARING_SOURCE.encode("utf-8"))

    scan_source_tree(tmp_path)

    error = capsys.readouterr().err
    assert "would look unused to a cleanup sweep" in error
    assert "undecodable.py" in error


def test_an_unparsable_module_is_announced(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A parse failure was swallowed at debug level, invisible in a normal run."""
    (tmp_path / "broken.py").write_text(
        'raise CadrumoError("cli.broken.key")' + chr(10) + "def (:" + chr(10),
        encoding="utf-8",
    )

    scan_source_tree(tmp_path)

    assert "does not parse" in capsys.readouterr().err


def test_the_scan_continues_past_a_module_it_cannot_read(
    tmp_path: pathlib.Path,
) -> None:
    """One unreadable file must not cost the keys declared by every other module.

    The broken module sorts first, so a walk that stopped there would return
    nothing at all.
    """
    (tmp_path / "aaa_broken.py").write_text(
        'raise CadrumoError("cli.broken.key")' + chr(10) + "def (:" + chr(10),
        encoding="utf-8",
    )
    (tmp_path / "zulu_sound.py").write_text(_DECLARING_SOURCE, encoding="utf-8")

    assert "cli.config.profile.missing" in scan_source_tree(tmp_path)


def test_a_readable_tree_announces_nothing(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A notice that fires on every run would carry no information."""
    (tmp_path / "sound.py").write_text(_DECLARING_SOURCE, encoding="utf-8")

    assert scan_source_tree(tmp_path)
    assert capsys.readouterr().err == ""
