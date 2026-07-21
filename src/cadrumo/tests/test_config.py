"""Tests that Settings and ``env/.env.example`` stay fully aligned.

The Settings model in ``cadrumo.core.config`` is the single source of truth for every
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

import pydantic
import pytest
from pydantic_settings import SettingsConfigDict

from ..core import AuthProviderKind
from ..core.config import (
    PROJECT_ROOT,
    Settings,
    StorageRouteKind,
    classify_storage_route,
)
from ..core.external_constants import load_external_constants
from .env_scope import isolated_aeat_env as _isolated_aeat_env
from .env_scope import settings_without_env_file

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

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

    def test_settings_instantiate_without_env(self) -> None:
        """Settings must load with all defaults when no env file and no env vars are present."""
        with _isolated_aeat_env():
            settings = settings_without_env_file()
        assert settings.aeat_base_url == load_external_constants().aeat.domains.sede
        assert settings.cadrumo_output_language == "es"


class TestAuthProviderEnum:
    """#285 — ``CADRUMO_AUTH_PROVIDER`` coerces to the settings enum strictly."""

    def test_env_value_coerces_to_enum(self) -> None:
        from ..core import AuthProviderKind

        with _isolated_aeat_env(CADRUMO_AUTH_PROVIDER="clave_movil"):
            settings = settings_without_env_file()
        assert settings.cadrumo_auth_provider is AuthProviderKind.CLAVE_MOVIL

    def test_blank_env_value_treated_as_unset(self) -> None:
        with _isolated_aeat_env(CADRUMO_AUTH_PROVIDER=""):
            settings = settings_without_env_file()
        assert settings.cadrumo_auth_provider is None

    def test_invalid_value_rejected(self) -> None:
        import pydantic

        with _isolated_aeat_env(CADRUMO_AUTH_PROVIDER="not_a_provider_kind"):
            with pytest.raises(pydantic.ValidationError):
                settings_without_env_file()


def test_certificate_backend_and_verify_url_are_not_settings_surfaces() -> None:
    """Retired certificate proof selectors are absent from the configuration schema."""
    assert "cadrumo_certificate_backend" not in Settings.model_fields
    assert "aeat_certificate_verify_url" not in Settings.model_fields
    assert "CADRUMO_CERTIFICATE_BACKEND" not in Settings.env_var_names()
    assert "AEAT_CERTIFICATE_VERIFY_URL" not in Settings.env_var_names()


class TestStatusDetailUrlTemplate:
    """#227 validator: template must contain ``{expediente_id}``."""

    def test_default_contains_placeholder(self) -> None:
        settings = Settings(aeat_status_detail_url_template="/x/{expediente_id}/y")
        assert settings.aeat_status_detail_url_template == "/x/{expediente_id}/y"

    def test_default_is_well_formed(self) -> None:
        settings = Settings()
        constants = load_external_constants()

        assert settings.aeat_status_detail_url_template == constants.aeat.sede_paths.expediente_detail_template
        assert settings.aeat_status_notificaciones_path == constants.aeat.sede_paths.notificaciones
        assert "{expediente_id}" in settings.aeat_status_detail_url_template

    def test_rejects_template_without_placeholder(self) -> None:
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            Settings(aeat_status_detail_url_template="/x/no-placeholder/y")

    def test_blank_env_values_are_ignored(self, tmp_path: Path) -> None:
        """Blank values in env/.env must not coerce optional settings into live values."""
        env_path = tmp_path / ".env"
        env_path.write_text(
            "\n".join(
                (
                    "CADRUMO_CERTIFICATE_PATH=",
                    "CADRUMO_CERTIFICATE_PASSWORD_SECRET=",
                ),
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

        with _isolated_aeat_env():
            settings = BlankEnvSettings(cadrumo_local_storage_root=tmp_path / "cadrumo-state")
        assert settings.cadrumo_certificate_path is None
        assert settings.cadrumo_certificate_password_secret is None

    def test_legacy_product_dotenv_keys_are_excluded_without_weakening_unknown_key_validation(
        self, tmp_path: Path
    ) -> None:
        """Cadrumo starts fresh while retaining strict validation for unrelated dotenv keys."""
        env_path = tmp_path / ".env"
        env_path.write_text(
            "\n".join(
                (
                    "AEAT_LOCAL_STORAGE_ROOT=legacy-state-root",
                    "AEAT_SECRET_PASSPHRASE=legacy-secret-value",
                    "CADRUMO_AUTH_PROVIDER=certificate",
                )
            )
            + "\n",
            encoding="utf-8",
        )

        class LegacyProductEnvSettings(Settings):
            """Settings variant bound to a real legacy-product dotenv file."""

            model_config = SettingsConfigDict(
                env_file=env_path,
                env_file_encoding="utf-8",
                env_ignore_empty=True,
            )

        with _isolated_aeat_env():
            settings = LegacyProductEnvSettings(cadrumo_local_storage_root=tmp_path / "cadrumo-state")
        assert settings.cadrumo_local_storage_root != Path("legacy-state-root")
        assert settings.cadrumo_auth_provider is AuthProviderKind.CERTIFICATE

        env_path.write_text("UNRELATED_CADRUMO_TYPO=1\n", encoding="utf-8")
        with _isolated_aeat_env(), pytest.raises(pydantic.ValidationError):
            LegacyProductEnvSettings(cadrumo_local_storage_root=tmp_path / "cadrumo-state")

    def test_relative_env_paths_resolve_from_project_root(self, tmp_path: Path) -> None:
        """Relative env-backed paths must anchor to PROJECT_ROOT, not the process cwd."""
        env_path = tmp_path / ".env"
        env_path.write_text(
            "CADRUMO_WORKFLOW_RUNS_DIR=env/workflow/runs\n",
            encoding="utf-8",
        )

        class RelativeEnvSettings(Settings):
            """Settings variant bound to a temp env file with relative path assignments."""

            model_config = SettingsConfigDict(
                env_file=env_path,
                env_file_encoding="utf-8",
                env_ignore_empty=True,
            )

        with _isolated_aeat_env():
            settings = RelativeEnvSettings(cadrumo_local_storage_root=tmp_path / "cadrumo-state")
        assert settings.cadrumo_workflow_runs_dir == PROJECT_ROOT / "env" / "workflow" / "runs"

    def test_blank_optional_path_env_vars_are_treated_as_unset(self) -> None:
        """Blank optional path env vars must normalize to ``None``."""
        with _isolated_aeat_env(CADRUMO_CERTIFICATE_PATH=""):
            settings = settings_without_env_file()
        assert settings.cadrumo_certificate_path is None

    def test_blank_optional_secret_env_vars_are_treated_as_unset(self) -> None:
        """Blank optional secret env vars must normalize to ``None``."""
        with _isolated_aeat_env(CADRUMO_CERTIFICATE_PASSWORD_SECRET="", CADRUMO_LLM_OPENAI_API_KEY=""):
            settings = settings_without_env_file()
        assert settings.cadrumo_certificate_password_secret is None
        assert settings.cadrumo_llm_openai_api_key is None


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
            "_normalize_repo_relative_paths in src/cadrumo/config.py: "
            f"{missing}. Either add each to the validator's field tuple or "
            "add it to TestRepoRelativePathNormalisationCoverage._EXEMPT_PATH_FIELDS "
            "with a documented justification."
        )

    def test_audit_flagged_drift_settings_are_normalised(self) -> None:
        """Three Settings fields surfaced by a security audit MUST be normalised.

        ``cadrumo_invoices_dir``, ``cadrumo_attachments_dir``, ``cadrumo_runs_dir``
        all carry user-supplied filesystem paths that the rest of the
        codebase joins with ``Path()``; without normalisation a relative
        value would resolve against the process CWD and silently leak
        files outside the configured local store.
        """
        path_validator = self._validator_field_set("_normalize_repo_relative_paths")
        for field_name in ("cadrumo_invoices_dir", "cadrumo_attachments_dir", "cadrumo_runs_dir"):
            assert field_name in path_validator, (
                f"{field_name} was flagged by the security audit as missing from "
                "_normalize_repo_relative_paths but is still not in the validator. "
                "Re-add it to the field tuple in src/cadrumo/config.py."
            )

    def test_relative_audit_flagged_paths_resolve_under_project_root(self, tmp_path: Path) -> None:
        """End-to-end: relative env values for the three audit-flagged paths anchor to
        ``PROJECT_ROOT`` (not the process cwd)."""
        env_path = tmp_path / ".env"
        env_path.write_text(
            "\n".join(
                (
                    "CADRUMO_INVOICES_DIR=var/financial/invoices",
                    "CADRUMO_ATTACHMENTS_DIR=var/financial/attachments",
                    "CADRUMO_RUNS_DIR=var/runs",
                ),
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

        with _isolated_aeat_env():
            settings = RelativeAuditSettings(cadrumo_local_storage_root=tmp_path / "cadrumo-state")
        assert settings.cadrumo_invoices_dir == PROJECT_ROOT / "var" / "financial" / "invoices"
        assert settings.cadrumo_attachments_dir == PROJECT_ROOT / "var" / "financial" / "attachments"
        assert settings.cadrumo_runs_dir == PROJECT_ROOT / "var" / "runs"


class TestDatabaseUrlDerivation:
    """``cadrumo_database_url`` must stay coherent with ``cadrumo_local_storage_root``.

    Setting ``CADRUMO_LOCAL_STORAGE_ROOT`` alone — with no explicit
    ``CADRUMO_DATABASE_URL`` and no active profile — must never leave the
    URL empty. An empty URL made first-contact CLI commands exit-5 with
    a raw internal ``cadrumo_database_url is empty`` error instead of the
    clean no-active-profile refusal.
    """

    @staticmethod
    def _isolated(env_file_path: Path) -> type[Settings]:
        class IsolatedSettings(Settings):
            """Settings variant bound to a temp env file for test isolation."""

            model_config = SettingsConfigDict(
                env_file=env_file_path,
                env_file_encoding="utf-8",
                env_ignore_empty=True,
            )

        return IsolatedSettings

    def test_storage_root_alone_derives_root_level_fallback_url(self, tmp_path: Path) -> None:
        """Storage root without an explicit URL or active profile derives the
        ``sqlite:///<root>/cadrumo.db`` fallback rather than staying empty."""
        storage_root = tmp_path / "aeat-state"
        env_path = tmp_path / ".env"
        env_path.write_text(
            f"CADRUMO_LOCAL_STORAGE_ROOT={storage_root.as_posix()}\n",
            encoding="utf-8",
        )

        with _isolated_aeat_env():
            settings = self._isolated(env_path)()

        expected = f"sqlite:///{(storage_root / 'cadrumo.db').as_posix()}"
        assert settings.cadrumo_database_url == expected
        assert settings.cadrumo_database_url, "URL must never be empty when the storage root is set"

    def test_explicit_database_url_overrides_storage_root_derivation(self, tmp_path: Path) -> None:
        """An explicit ``CADRUMO_DATABASE_URL`` wins over the derived fallback."""
        explicit_url = f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}"
        env_path = tmp_path / ".env"
        env_path.write_text(
            "\n".join(
                (
                    f"CADRUMO_LOCAL_STORAGE_ROOT={(tmp_path / 'aeat-state').as_posix()}",
                    f"CADRUMO_DATABASE_URL={explicit_url}",
                ),
            )
            + "\n",
            encoding="utf-8",
        )

        with _isolated_aeat_env():
            settings = self._isolated(env_path)()

        assert settings.cadrumo_database_url == explicit_url

    def test_active_profile_derives_per_bucket_url(self, tmp_path: Path) -> None:
        """An active profile still derives the per-bucket SQLite URL; the
        root-level fallback only applies when no bucket resolves."""
        storage_root = tmp_path / "aeat-state"
        env_path = tmp_path / ".env"
        env_path.write_text(
            "\n".join(
                (
                    f"CADRUMO_LOCAL_STORAGE_ROOT={storage_root.as_posix()}",
                    "CADRUMO_ACTIVE_PROFILE=acme",
                ),
            )
            + "\n",
            encoding="utf-8",
        )

        with _isolated_aeat_env():
            settings = self._isolated(env_path)()

        expected = f"sqlite:///{(storage_root / 'buckets' / 'acme' / 'db' / 'cadrumo.db').as_posix()}"
        assert settings.cadrumo_database_url == expected

    def test_env_example_leaves_normal_profile_storage_on_the_bucket_route(self, tmp_path: Path) -> None:
        """The shipped environment template must not force a global database route."""

        class ExampleSettings(Settings):
            """Settings loaded from the same template copied by ``just env-setup``."""

            model_config = SettingsConfigDict(
                env_file=ENV_EXAMPLE_PATH,
                env_file_encoding="utf-8",
                env_ignore_empty=True,
            )

        storage_root = tmp_path / "cadrumo-state"
        bucket_id = "profile-bucket"
        with _isolated_aeat_env():
            settings = ExampleSettings(
                cadrumo_local_storage_root=storage_root,
                cadrumo_active_profile=bucket_id,
            )

        expected = f"sqlite:///{(storage_root / 'buckets' / bucket_id / 'db' / 'cadrumo.db').as_posix()}"
        assert settings.cadrumo_database_url == expected
        assert classify_storage_route(settings).kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE
