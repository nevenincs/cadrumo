from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.core.config import override_settings
from cadrumo_runtime.host.tests.frontend.cli.cli_runner import invoke_cached_cli

from ...native_profile_facts import native_general_iva_facts


@contextmanager
def isolated_cli_surface_backend(tmp_path: Path) -> Generator[None]:
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


def create_cli_surface_profile(label: str = "operator", *, log_in: bool = True) -> None:
    """Register the surface profile through the shared CLI registration door.

    ``log_in`` is forwarded to ``register_cli_profile``.
    """
    register_cli_profile(
        label=label,
        log_in=log_in,
        facts={
            **native_general_iva_facts(),
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Example",
            "activities.description": "Test",
        },
    )


def _active_bucket_id() -> str:
    from cadrumo.core.bucket_pointer import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "no active profile bucket resolved"
    return bucket_id
