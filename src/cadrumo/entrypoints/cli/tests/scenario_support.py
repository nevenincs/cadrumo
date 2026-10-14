"""Tax scenario operations through injected world and invocation ports."""

from __future__ import annotations

from .cli_fixture_worlds import cli_world_provider, invoke_joined_cli


def _invoke(args, **kwargs):
    return invoke_joined_cli(args, **kwargs)


def _active_bucket_id() -> str:
    return cli_world_provider().active_bucket_id()


def create_cli_surface_profile(label: str = "operator", *, log_in: bool = True) -> None:
    cli_world_provider().create_surface_profile(label, log_in=log_in)


def _set_profile_axis(key: str, value: str) -> None:
    cli_world_provider().set_profile_axis(key, value)
