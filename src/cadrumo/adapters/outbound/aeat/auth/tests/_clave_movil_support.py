"""Shared Cl@ve Movil provider test harness."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from ......core.config import Settings

EXTERNAL = Settings.external_constants()
_DOMAINS = EXTERNAL.aeat.domains
_CLAVE_SURFACE = EXTERNAL.aeat.clave_movil
_PRE303_SURFACE = EXTERNAL.aeat.pre303


def _run[T](coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)


def _aeat_url(origin: str, path: str) -> str:
    return f"{origin}{path}"


def _settings_for(tmp_path: Path, **env: str) -> Settings:
    env_overrides = {key.lower(): value for key, value in env.items()}
    expected_keys = {
        "cadrumo_clave_movil_dni_fecha",
        "cadrumo_clave_movil_dni_nie",
        "cadrumo_clave_movil_nie_soporte",
        "cadrumo_clave_prefer_non_qr",
    }
    unexpected = set(env_overrides) - expected_keys
    assert unexpected == set()
    return Settings(
        cadrumo_token_dir=tmp_path,
        cadrumo_local_storage_root=tmp_path / "storage",
        cadrumo_clave_prefer_non_qr=_bool_setting(env_overrides.get("cadrumo_clave_prefer_non_qr")),
        cadrumo_clave_movil_dni_nie=_secret_or_none(env_overrides.get("cadrumo_clave_movil_dni_nie")),
        cadrumo_clave_movil_dni_fecha=env_overrides.get("cadrumo_clave_movil_dni_fecha"),
        cadrumo_clave_movil_nie_soporte=_secret_or_none(env_overrides.get("cadrumo_clave_movil_nie_soporte")),
    )


def _secret_or_none(value: str | None) -> SecretStr | None:
    return None if value is None else SecretStr(value)


def _bool_setting(value: str | None) -> bool:
    return False if value is None else value.lower() == "true"
