"""Canonical session registration fixture for application wizard tests."""

import pytest

import cadrumo.application.wizard.catalogue as _catalogue


@pytest.fixture(autouse=True, scope="session")
def register_wizard_catalogue() -> None:
    if _catalogue is None:
        raise AssertionError("wizard catalogue registration import failed")


__all__ = ["register_wizard_catalogue"]
