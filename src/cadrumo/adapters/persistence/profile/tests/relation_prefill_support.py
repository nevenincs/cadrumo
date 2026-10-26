"""Small outer-test fakes for the composed relation-prefill profile port."""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.application.user_profile.profile_read_ports import ProfileReadPorts


class EmptyProfilePathValuesReader:
    """Represent an absent profile for relation-prefill repository tests."""

    def load_path_values(self, *, bucket_id: str) -> Mapping[str, str] | None:
        del bucket_id
        return None


def empty_profile_read_ports() -> ProfileReadPorts:
    """Return the required profile-read bundle for no-profile scenarios."""
    return ProfileReadPorts(path_values=EmptyProfilePathValuesReader())


__all__ = ["EmptyProfilePathValuesReader", "empty_profile_read_ports"]
