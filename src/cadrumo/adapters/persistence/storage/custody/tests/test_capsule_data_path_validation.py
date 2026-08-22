"""A capsule data path is refused unless it stays inside the staging root.

``validated_data_path`` is the designated guard for the names in a capsule's
data inventory, and its refusal says the path "escapes its staging root". It
enumerated the ways a path escapes on POSIX -- absolute, or carrying an empty,
``.`` or ``..`` component -- and parsed the value as
:class:`~pathlib.PurePosixPath`, which is the capsule's on-wire spelling.

The join happens on whatever platform is running, and this one runs on Windows.
A drive-qualified value means different things to the two readings: ``"C:/x"``
is an ordinary two-component RELATIVE path to POSIX, so it is neither absolute
nor dotted and cleared every check -- while joining it on Windows discards the
staging root and yields ``C:x``. ``"C:x"`` resolves against the process's
current directory on that drive.

Measured before the fix, against a real join:

    'C:/foo' -> 'C:x'                      (staging root gone)
    'C:foo'  -> 'C:foo'                    (drive-relative, CWD-dependent)
    'a/b'    -> 'D:/staging/root/a/b'      (correct)

The backslash and UNC spellings were already refused, which is what made the
gap hard to see: three of the four ways to escape were covered, so the guard
looked complete from the outside.

No caller supplies an untrusted name today -- the inventory's keys are the
constant ``profile-label.v1.json`` and callers passing ``{}`` -- so this is a
latent hazard, not a live escape. It is fixed at the validator because that is
the function whose stated contract is the containment.
"""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

import pytest

from .._capsule_data import validated_data_path
from .._errors import ProfileCustodyRecordError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

#: Values that escape the staging root, each spelled without a POSIX dot segment.
_DRIVE_QUALIFIED = ("C:/foo", "C:foo", "c:/foo", "Z:x/y")


def test_a_drive_qualified_path_is_refused() -> None:
    """DISCRIMINATING: the spelling that reads as relative on POSIX and absolute on Windows."""
    for value in _DRIVE_QUALIFIED:
        with pytest.raises(ProfileCustodyRecordError, match="escapes its staging root"):
            validated_data_path(value)


def test_the_refused_values_would_have_escaped_the_join() -> None:
    """ANTI-VACUITY: pins WHY each value is refused, so the refusal cannot be dropped quietly.

    Asserting only that ``"C:/foo"`` raises says nothing about the consequence.
    This states it: joined on Windows, the staging root is simply gone. A
    future reader who doubts the rule can see what accepting it would cost.
    """
    staging_root = PureWindowsPath("D:/staging/root")

    for value in _DRIVE_QUALIFIED:
        joined = staging_root / value
        assert staging_root not in joined.parents, f"{value!r} unexpectedly stayed inside the root"

    # The control: an ordinary relative name lands underneath, as callers expect.
    assert staging_root in (staging_root / "a/b").parents


def test_the_posix_reading_alone_would_have_accepted_them() -> None:
    """ANTI-TAUTOLOGY: proves the NEW check is what refuses these, not the old ones.

    Without this, the drive-qualified values might be getting refused by the
    pre-existing absolute/dot-component checks, and the added Windows reading
    could be dead code that no assertion would notice.
    """
    for value in _DRIVE_QUALIFIED:
        posix_reading = PurePosixPath(value)
        assert not posix_reading.is_absolute()
        assert not any(part in {"", ".", ".."} for part in posix_reading.parts)


def test_an_ordinary_relative_capsule_name_is_still_accepted() -> None:
    """ANTI-TAUTOLOGY: the guard must not have widened onto the names actually used.

    ``profile-label.v1.json`` is the real inventory key. A validator that
    refused it -- or refused any name merely containing a dot or a colon-free
    version marker -- would satisfy every assertion above while breaking
    publication outright.
    """
    for value in ("profile-label.v1.json", "a/b", "nested/dir/file.v1.json", "..alpha/x"):
        assert validated_data_path(value) == PurePosixPath(value)


def test_the_previously_covered_escapes_are_still_refused() -> None:
    """The spellings that were already guarded must stay guarded."""
    for value in ("/etc/passwd", "../x", "a/../../b", ""):
        with pytest.raises(ProfileCustodyRecordError):
            validated_data_path(value)

    with pytest.raises(ProfileCustodyRecordError):
        validated_data_path(".." + chr(92) + "x")


def test_a_bare_dot_is_refused_though_the_component_check_cannot_see_it() -> None:
    """DISCRIMINATING: the validator named ``"."`` and then could not reach it.

    ``PurePosixPath`` normalises a lone dot away, so ``"."`` and ``"./"`` parse
    to NO components and the ``{"", ".", ".."}`` membership test never runs
    against the value it explicitly forbids. The path resolves to the staging
    root itself -- a directory, not a file to write -- so this is a degenerate
    name rather than an escape, but the guard claimed to refuse it and did not.
    """
    for value in (".", "./"):
        assert not PurePosixPath(value).parts, "premise: pathlib normalises the dot away"
        with pytest.raises(ProfileCustodyRecordError, match="escapes its staging root"):
            validated_data_path(value)


def test_an_interior_dot_component_is_normalised_rather_than_refused() -> None:
    """The other direction, measured rather than assumed.

    ``"a/./b"`` is NOT an escape: pathlib collapses it to ``a/b`` before any
    check runs, and accepting it is correct. This was written the other way
    first and the test failed, which is how the normalisation above was found.
    """
    assert validated_data_path("a/./b") == PurePosixPath("a/b")
