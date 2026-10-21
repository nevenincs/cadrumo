"""Protected setup navigation accepts only an exact nonempty profile UUID."""

from uuid import UUID

import pytest

from ..module_arguments import TuiModuleArgumentError, aeat_setup_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]
_PROFILE = "5aa00000-0000-4000-8000-0000000000aa"


def test_setup_profile_is_explicit_and_canonical() -> None:
    assert aeat_setup_profile(["--aeat-auth-profile", _PROFILE]) == UUID(_PROFILE)
    assert aeat_setup_profile([]) is None
    assert aeat_setup_profile(["--self-test"]) is None


@pytest.mark.parametrize(
    "arguments",
    [
        ["--aeat-auth-profile"],
        ["--aeat-auth-profile", _PROFILE, "--self-test"],
        ["--aeat-auth-profile", "00000000-0000-0000-0000-000000000000"],
        ["--aeat-auth-profile", _PROFILE.upper()],
        ["--aeat-auth-profile", "../profile"],
        ["--aeat-auth-profile", _PROFILE + "?password=secret"],
    ],
)
def test_setup_refuses_ambiguous_or_extended_targets(arguments: list[str]) -> None:
    with pytest.raises(TuiModuleArgumentError):
        aeat_setup_profile(arguments)
