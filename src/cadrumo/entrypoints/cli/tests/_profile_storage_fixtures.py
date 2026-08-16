"""Canonical opt-in profile storage fixture for selected CLI classes."""

from ....tests.profile_storage_root_fixture import isolated_profile_storage_fixture

isolated_profile_storage = isolated_profile_storage_fixture(autouse=False, name="isolated_profile_storage")

__all__ = ["isolated_profile_storage"]
