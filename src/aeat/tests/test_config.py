"""Tests that Settings and ``env/.env.example`` stay fully aligned.

The Settings model in ``aeat.core.config`` is the single source of truth for every
environment variable the application reads.  These tests enforce that:

1. Every Settings field has a matching line in ``env/.env.example``.
2. Every variable in ``env/.env.example`` has a matching Settings field.
3. Settings can be instantiated with no env vars at all (all fields have defaults).
"""

from __future__ import annotations

import re
from pathlib import Path
from types import UnionType
from typing import Union, get_args, get_origin

import pytest
from pydantic_settings import SettingsConfigDict

from aeat.core.config import PROJECT_ROOT, CertificateBackend, Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

ENV_EXAMPLE_PATH = PROJECT_ROOT / "env" / ".env.example"


def _parse_env_example_vars() -> set[str]:
    """Extract variable names from ``env/.env.example``."""
    env_file = ENV_EXAMPLE_PATH
    names: set[str] = set()
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        # Skip blank lines and comments
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([A-Z_][A-Z0-9_]*)=", stripped)
        if match:
            names.add(match.group(1))
    return names


class TestEnvExampleAlignment:
    """Ensure .env.example and Settings stay fully synchronized."""

    def test_env_example_file_exists(self) -> None:
        """``env/.env.example`` must exist at the canonical env container path."""
        assert ENV_EXAMPLE_PATH.exists(), f".env.example not found at {ENV_EXAMPLE_PATH}"

    def test_settings_fields_documented_in_env_example(self) -> None:
        """Every Settings field must have a corresponding entry in env/.env.example."""
        settings_vars = Settings.env_var_names()
        example_vars = _parse_env_example_vars()
        missing = sorted(settings_vars - example_vars)
        assert not missing, (
            f"Settings fields not documented in .env.example: {missing}. Add an entry for each to .env.example."
        )

    def test_env_example_vars_defined_in_settings(self) -> None:
        """Every .env.example variable must have a corresponding Settings field."""
        settings_vars = Settings.env_var_names()
        example_vars = _parse_env_example_vars()
        extra = sorted(example_vars - settings_vars)
        assert not extra, (
            f"env/.env.example variables with no Settings field: {extra}. "
            "Add a corresponding field to Settings in config.py."
        )

    def test_settings_instantiate_without_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings must load with all defaults when no env file and no env vars are present."""
        for name in Settings.env_var_names():
            monkeypatch.delenv(name, raising=False)
            monkeypatch.delenv(name.lower(), raising=False)

        class IsolatedSettings(Settings):
            """Settings variant that skips the on-disk env file for test isolation."""

            model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")

        settings = IsolatedSettings()
        assert settings.aeat_base_url == "https://sede.agenciatributaria.gob.es"
        assert settings.aeat_output_language == "es"


class TestAuthProviderEnum:
    """#285 — ``AEAT_AUTH_PROVIDER`` coerces to the settings enum strictly."""

    def test_env_value_coerces_to_enum(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from aeat.core.config import AuthProviderKindSetting

        for name in Settings.env_var_names():
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("AEAT_AUTH_PROVIDER", "clave_movil")

        class IsolatedSettings(Settings):
            model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")

        settings = IsolatedSettings()
        assert settings.aeat_auth_provider is AuthProviderKindSetting.CLAVE_MOVIL

    def test_blank_env_value_treated_as_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in Settings.env_var_names():
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("AEAT_AUTH_PROVIDER", "")

        class IsolatedSettings(Settings):
            model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8", env_ignore_empty=True)

        settings = IsolatedSettings()
        assert settings.aeat_auth_provider is None

    def test_invalid_value_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import pydantic

        for name in Settings.env_var_names():
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("AEAT_AUTH_PROVIDER", "not_a_provider_kind")

        class IsolatedSettings(Settings):
            model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")

        with pytest.raises(pydantic.ValidationError):
            IsolatedSettings()


class TestCertificateBackendEnum:
    """Certificate backend settings accept canonical values only."""

    def test_lowercase_setting_value_is_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in Settings.env_var_names():
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("AEAT_CERTIFICATE_BACKEND", "playwright_context")

        class IsolatedSettings(Settings):
            model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")

        settings = IsolatedSettings()
        assert settings.aeat_certificate_backend is CertificateBackend.PLAYWRIGHT_CONTEXT

    def test_uppercase_enum_name_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import pydantic

        for name in Settings.env_var_names():
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("AEAT_CERTIFICATE_BACKEND", "PLAYWRIGHT_CONTEXT")

        class IsolatedSettings(Settings):
            model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")

        with pytest.raises(pydantic.ValidationError):
            IsolatedSettings()


class TestStatusDetailUrlTemplate:
    """#227 validator: template must contain ``{expediente_id}``."""

    def test_default_contains_placeholder(self) -> None:
        settings = Settings(aeat_status_detail_url_template="/x/{expediente_id}/y")
        assert settings.aeat_status_detail_url_template == "/x/{expediente_id}/y"

    def test_default_is_well_formed(self) -> None:
        settings = Settings()
        assert "{expediente_id}" in settings.aeat_status_detail_url_template

    def test_rejects_template_without_placeholder(self) -> None:
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            Settings(aeat_status_detail_url_template="/x/no-placeholder/y")

    def test_blank_env_values_are_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Blank values in env/.env must not coerce optional settings into live values."""
        for name in Settings.env_var_names():
            monkeypatch.delenv(name, raising=False)

        env_path = tmp_path / ".env"
        env_path.write_text(
            "\n".join(
                (
                    "AEAT_CERTIFICATE_PATH=",
                    "AEAT_CERTIFICATE_PASSWORD_SECRET=",
                )
            )
            + "\n",
            encoding="utf-8",
        )

        class BlankEnvSettings(Settings):
            """Settings variant bound to a temp env file that contains blank assignments."""

            model_config = SettingsConfigDict(
                env_file=env_path,
                env_file_encoding="utf-8",
                env_ignore_empty=True,
            )

        settings = BlankEnvSettings()
        assert settings.aeat_certificate_path is None
        assert settings.aeat_certificate_password_secret is None

    def test_relative_env_paths_resolve_from_project_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Relative env-backed paths must anchor to PROJECT_ROOT, not the process cwd."""
        for name in Settings.env_var_names():
            monkeypatch.delenv(name, raising=False)

        env_path = tmp_path / ".env"
        env_path.write_text(
            "AEAT_WORKFLOW_RUNS_DIR=env/workflow/runs\n",
            encoding="utf-8",
        )

        class RelativeEnvSettings(Settings):
            """Settings variant bound to a temp env file with relative path assignments."""

            model_config = SettingsConfigDict(
                env_file=env_path,
                env_file_encoding="utf-8",
                env_ignore_empty=True,
            )

        settings = RelativeEnvSettings()
        assert settings.aeat_workflow_runs_dir == PROJECT_ROOT / "env" / "workflow" / "runs"

    def test_blank_optional_path_env_vars_are_treated_as_unset(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Blank optional path env vars must normalize to ``None``."""
        monkeypatch.setenv("AEAT_CERTIFICATE_PATH", "")

        class IsolatedSettings(Settings):
            """Settings variant that skips the on-disk env file for test isolation."""

            model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")

        settings = IsolatedSettings()
        assert settings.aeat_certificate_path is None

    def test_blank_optional_secret_env_vars_are_treated_as_unset(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Blank optional secret env vars must normalize to ``None``."""
        monkeypatch.setenv("AEAT_CERTIFICATE_PASSWORD_SECRET", "")
        monkeypatch.setenv("AEAT_LLM_OPENAI_API_KEY", "")

        class IsolatedSettings(Settings):
            """Settings variant that skips the on-disk env file for test isolation."""

            model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")

        settings = IsolatedSettings()
        assert settings.aeat_certificate_password_secret is None
        assert settings.aeat_llm_openai_api_key is None


class TestRepoRelativePathNormalisationCoverage:
    """#216 — every Path-typed settings field must route through the repo-relative
    path normaliser, otherwise relative env values silently escape into cwd-anchored
    locations. The 2026-04-27 security storage audit graded this MEDIUM-HIGH after
    spotting drift on three financial / observability settings.
    """

    _PATH_FIELD_SUFFIXES: tuple[str, ...] = ("_dir", "_path", "_root")
    """Suffixes that mark a settings field as a repo-relative path."""

    _EXEMPT_PATH_FIELDS: frozenset[str] = frozenset()
    """Path-typed `_dir`/`_path`/`_root` fields legitimately exempt from normalisation.

    Empty today — every such field must be normalised. Adding a new
    exemption is a deliberate departure from the secure-persistence
    invariant and must be justified in the field's docstring.
    """

    @staticmethod
    def _validator_field_set(validator_name: str) -> set[str]:
        """Return the field names a Settings field-validator covers."""
        decorators = Settings.__pydantic_decorators__.field_validators
        info = decorators[validator_name]
        return set(info.info.fields)

    def test_every_path_typed_setting_is_normalised(self) -> None:
        """Every `_dir`/`_path`/`_root` Path-typed settings field must be covered by
        ``_normalize_repo_relative_paths`` (or its string-mode sibling) — modulo the
        explicit exempt list above.
        """
        path_validator = self._validator_field_set("_normalize_repo_relative_paths")
        path_typed_settings: set[str] = set()
        for field_name, field_info in Settings.model_fields.items():
            if not field_name.endswith(self._PATH_FIELD_SUFFIXES):
                continue
            annotation = field_info.annotation
            origin = get_origin(annotation)
            members: tuple[object, ...] = get_args(annotation) if origin in (Union, UnionType) else (annotation,)
            if any(member is Path for member in members):
                path_typed_settings.add(field_name)

        missing = sorted(path_typed_settings - path_validator - self._EXEMPT_PATH_FIELDS)
        assert not missing, (
            "Path-typed Settings fields missing from "
            "_normalize_repo_relative_paths in src/aeat/config.py: "
            f"{missing}. Either add each to the validator's field tuple or "
            "add it to TestRepoRelativePathNormalisationCoverage._EXEMPT_PATH_FIELDS "
            "with a documented justification."
        )

    def test_audit_flagged_drift_settings_are_normalised(self) -> None:
        """Three Settings fields surfaced by a security audit MUST be normalised.

        ``aeat_invoices_dir``, ``aeat_attachments_dir``, ``aeat_runs_dir``
        all carry user-supplied filesystem paths that the rest of the
        codebase joins with ``Path()``; without normalisation a relative
        value would resolve against the process CWD and silently leak
        files outside the configured local store.
        """
        path_validator = self._validator_field_set("_normalize_repo_relative_paths")
        for field_name in ("aeat_invoices_dir", "aeat_attachments_dir", "aeat_runs_dir"):
            assert field_name in path_validator, (
                f"{field_name} was flagged by the security audit as missing from "
                "_normalize_repo_relative_paths but is still not in the validator. "
                "Re-add it to the field tuple in src/aeat/config.py."
            )

    def test_relative_audit_flagged_paths_resolve_under_project_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """End-to-end: relative env values for the three audit-flagged paths anchor to
        ``PROJECT_ROOT`` (not the process cwd)."""
        for name in Settings.env_var_names():
            monkeypatch.delenv(name, raising=False)

        env_path = tmp_path / ".env"
        env_path.write_text(
            "\n".join(
                (
                    "AEAT_INVOICES_DIR=var/financial/invoices",
                    "AEAT_ATTACHMENTS_DIR=var/financial/attachments",
                    "AEAT_RUNS_DIR=var/runs",
                )
            )
            + "\n",
            encoding="utf-8",
        )

        class RelativeAuditSettings(Settings):
            """Settings variant bound to a temp env file with the audit-flagged paths."""

            model_config = SettingsConfigDict(
                env_file=env_path,
                env_file_encoding="utf-8",
                env_ignore_empty=True,
            )

        settings = RelativeAuditSettings()
        assert settings.aeat_invoices_dir == PROJECT_ROOT / "var" / "financial" / "invoices"
        assert settings.aeat_attachments_dir == PROJECT_ROOT / "var" / "financial" / "attachments"
        assert settings.aeat_runs_dir == PROJECT_ROOT / "var" / "runs"
