from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ....application import wizard as _wizard  # noqa: F401 -- side effect: registers PROFILE_KEYS
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root


@contextmanager
def isolated_cli_surface_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(
            aeat_auth_provider=None,
            aeat_certificate_path=None,
            aeat_certificate_password_secret=None,
            aeat_clave_movil_dni_nie=None,
            aeat_clave_movil_dni_fecha=None,
            aeat_clave_movil_nie_soporte=None,
        ),
    ):
        yield


def _json(result) -> dict[str, Any]:
    payload = json.loads(result.output)
    if isinstance(payload, dict) and "result" in payload and "schema_version" in payload:
        inner = payload["result"]
        if isinstance(inner, dict):
            return inner
    return payload


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
