from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ....application import wizard as _wizard  # noqa: F401 -- side effect: registers PROFILE_KEYS
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .envelope_helpers import unwrap_cli_result as _json  # noqa: F401 -- imported by surface suites


@contextmanager
def isolated_cli_surface_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(
            cadrumo_auth_provider=None,
            cadrumo_certificate_path=None,
            cadrumo_certificate_password_secret=None,
            cadrumo_clave_movil_dni_nie=None,
            cadrumo_clave_movil_dni_fecha=None,
            cadrumo_clave_movil_nie_soporte=None,
        ),
    ):
        yield


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def create_cli_surface_profile(label: str = "operator") -> None:
    result = _invoke(
        [
            "config",
            "profile",
            "create",
            label,
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "12345678Z",
            "--entity-type",
            "natural_person",
            "--name",
            "Operator",
            "--surnames",
            "Example",
            "--activity",
            "Test",
        ],
    )
    assert result.exit_code == 0, result.output


def _active_bucket_id() -> str:
    from ....core import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "no active profile bucket resolved"
    return bucket_id
