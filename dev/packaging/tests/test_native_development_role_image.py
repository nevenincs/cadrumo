"""Keep the checkout's built-binary setting equal in the package declaration and the components client."""

from __future__ import annotations

import re

import pytest

from cadrumo.adapters.outbound.components.role_image import DEVELOPMENT_ROLE_IMAGE_VARIABLE
from dev._paths import REPO_ROOT
from dev.packaging.native.application_environment import DECLARATION, ApplicationEnvironmentError, load, parse

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DECLARED = re.compile(r'^development_role_image_variable = "[^"]*"$', flags=re.MULTILINE)


def _declared_as(value: str) -> str:
    text = (REPO_ROOT / DECLARATION).read_text(encoding="utf-8")
    declared = _DECLARED.search(text)
    assert declared is not None
    return text.replace(declared.group(0), f'development_role_image_variable = "{value}"')


def test_the_declared_name_is_the_one_the_components_client_reads() -> None:
    declaration = load(REPO_ROOT)

    assert declaration.components["development_role_image_variable"] == DEVELOPMENT_ROLE_IMAGE_VARIABLE
    assert DEVELOPMENT_ROLE_IMAGE_VARIABLE not in declaration.names


@pytest.mark.parametrize("value", ["CADRUMO_LOCAL_STORAGE_ROOT", "CADRUMO_PROXY_URL", "cadrumo_lower", ""])
def test_a_name_a_profile_can_admit_or_a_malformed_one_is_refused(value: str) -> None:
    with pytest.raises(ApplicationEnvironmentError, match="development_role_image_variable"):
        parse(_declared_as(value))
