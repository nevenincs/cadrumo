from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from ....application.wizard import compiler as _wizard  # noqa: F401 -- side effect: registers PROFILE_KEYS
from ....core.config import override_settings
from ....tests.cli_envelope import unwrap_cli_result as _json  # noqa: F401 -- imported by surface suites
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile


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


def create_cli_surface_profile(label: str = "operator") -> None:
    """Register the surface profile through the shared CLI registration door."""
    register_cli_profile(
        label=label,
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Example",
            "activities.description": "Test",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.regime": "GENERAL",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )


def _active_bucket_id() -> str:
    from ....core.bucket_pointer import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "no active profile bucket resolved"
    return bucket_id
