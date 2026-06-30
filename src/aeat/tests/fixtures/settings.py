from __future__ import annotations

from pydantic_settings import SettingsConfigDict

from ...core.config import Settings


class EnvFileFreeSettings(Settings):
    model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")
