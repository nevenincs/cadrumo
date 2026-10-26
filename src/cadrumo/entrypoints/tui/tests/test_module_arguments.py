"""The TUI process takes no page or profile from its command line; a desktop asks the running TUI instead."""

import pytest

from ..module_arguments import TUI_SELF_TEST_FLAG, TuiModuleArgumentError, headless_invocation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]
_PROFILE = "5aa00000-0000-4000-8000-0000000000aa"


def test_only_the_bare_and_self_test_invocations_are_admitted() -> None:
    assert headless_invocation([]) is False
    assert headless_invocation([TUI_SELF_TEST_FLAG]) is True


@pytest.mark.parametrize(
    "arguments",
    [
        ["--aeat-auth-profile", _PROFILE],
        ["--destination", "workbench.ledger"],
        [TUI_SELF_TEST_FLAG, TUI_SELF_TEST_FLAG],
        [f"cadrumo://profiles/{_PROFILE}/ledger"],
        ["cadrumo://view/ledger"],
    ],
)
def test_a_page_or_profile_on_the_command_line_is_refused(arguments: list[str]) -> None:
    with pytest.raises(TuiModuleArgumentError):
        headless_invocation(arguments)
