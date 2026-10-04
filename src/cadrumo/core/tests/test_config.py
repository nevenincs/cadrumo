"""Tests that Settings and ``env/.env.example`` stay fully aligned.

The Settings model in ``cadrumo.core.config`` is the single source of truth for every
environment variable the application reads.  These tests enforce that:

1. Every Settings field has a matching line in ``env/.env.example``.
2. Settings can be instantiated with no env vars at all (all fields have defaults).

The reverse direction -- every ``env/.env.example`` variable resolves to either a
Settings field or a known development-tooling override -- is enforced by a
separate development-tooling gate, which owns the exemption list and therefore
that half of the parity check.

There is no ``.env`` file support: production reads configuration from the process
environment only. ``env/.env.example`` documents the accepted variable names for a
developer's own shell/``uv --env-file`` workflow; it is never read by ``Settings``
itself. Tests that need a variable in force construct it through the real process
environment (``env_scope.isolated_aeat_env``), never through a dotenv-bound
``Settings`` subclass.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import UnionType
from typing import Union, get_args, get_origin

import pytest

from ...tests.env_scope import isolated_aeat_env as _isolated_aeat_env
from ...tests.env_scope import settings_without_env_file
from ...tests.inventory import REPO_ROOT
from ..auth_provider import AuthProviderKind
from ..bucket_pointer import BucketPointer
from ..config import (
    Settings,
    classify_storage_route,
    load_settings,
    reset_settings_cache,
)
from ..config_support import StorageRouteKind
from ..external_constants import load_external_constants
from ..storage_environment import project_root
from ..storage_taxonomy import StorageCategory
from ..storage_taxonomy_locations import storage_location

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.usefixtures("operation")]

ENV_EXAMPLE_PATH = REPO_ROOT / "env" / ".env.example"


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

    def test_the_env_parity_corpora_did_not_collapse(self) -> None:
        """A green parity result below must mean 'compared', not 'compared nothing'.

        The set difference asserted empty below only means something if both
        corpora it draws from are actually populated. If either side resolved
        to an empty set -- the example file moved, or the line matcher stopped
        matching -- the difference is empty too and the gate reports exactly
        what a correct tree reports. The floors are deliberately low: the
        point is to distinguish a populated corpus from a collapsed one, not
        to pin a count that drifts with every new setting.
        """
        settings_vars = Settings.env_var_names()
        example_vars = _parse_env_example_vars()
        assert len(settings_vars) > 5, (
            f"Settings.env_var_names() yielded {len(settings_vars)} names; the parity gates below "
            "compare against this set, so a collapsed one makes them vacuous"
        )
        assert len(example_vars) > 5, (
            f"{ENV_EXAMPLE_PATH} parsed to {len(example_vars)} variables; the parity gates below "
            "compare against this set, so a collapsed one makes them vacuous"
        )

    def test_settings_fields_documented_in_env_example(self) -> None:
        """Every Settings field must have a corresponding entry in env/.env.example."""
        settings_vars = Settings.env_var_names()
        example_vars = _parse_env_example_vars()
        missing = sorted(settings_vars - example_vars)
        assert not missing, (
            f"Settings fields not documented in .env.example: {missing}. Add an entry for each to .env.example."
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
        from ..auth_provider import AuthProviderKind

        with _isolated_aeat_env(CADRUMO_AUTH_PROVIDER="clave_movil"):
            settings = settings_without_env_file()
        assert settings.cadrumo_auth_provider is AuthProviderKind.CLAVE_MOVIL

    def test_blank_env_value_treated_as_unset(self) -> None:
        with _isolated_aeat_env(CADRUMO_AUTH_PROVIDER=""):
            settings = settings_without_env_file()
        assert settings.cadrumo_auth_provider is None

    def test_invalid_value_rejected(self) -> None:
        import pydantic

        with (
            _isolated_aeat_env(CADRUMO_AUTH_PROVIDER="not_a_provider_kind"),
            pytest.raises(pydantic.ValidationError),
        ):
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
        """Blank env values must not coerce optional settings into live values."""
        with _isolated_aeat_env(
            CADRUMO_CERTIFICATE_PATH="",
            CADRUMO_CERTIFICATE_PASSWORD_SECRET="",
        ):
            settings = settings_without_env_file(cadrumo_local_storage_root=tmp_path / "cadrumo-state")
        assert settings.cadrumo_certificate_path is None
        assert settings.cadrumo_certificate_password_secret is None

    def test_unknown_env_var_name_is_silently_ignored_not_refused(self, tmp_path: Path) -> None:
        """A stale/mistyped env var name is ignored, never refused.

        Former-product settings names (``AEAT_LOCAL_STORAGE_ROOT``,
        ``AEAT_SECRET_PASSPHRASE`` and their siblings) once had a dedicated
        exclusion list filtering them out of the settings sources; that list
        was deleted deliberately once dotenv support was removed. The
        pydantic-settings env source only reads the process environment for
        names matching a DECLARED field (``field_name.upper()``); it never
        enumerates the ambient environment, so an unmapped name is simply
        never looked up and cannot trip the model's ``extra="forbid"``
        boundary. That exhaustive-scan-and-refuse behaviour was dotenv-only
        (``DotEnvSettingsSource`` forwards every key found in the file, known
        or not) and has no equivalent left once dotenv reading is gone.

        Pinning the current (weaker) contract deliberately: a stale key is a
        silent no-op, not a startup refusal. A neighbouring, correctly-named
        key is asserted alongside it so the test cannot pass by accident (a
        wholesale env-reading failure would also leave the valid field unset).
        """
        legacy_env_values = {"AEAT_SECRET_PASSPHRASE": "legacy-secret-value"}
        with _isolated_aeat_env(
            AEAT_LOCAL_STORAGE_ROOT="legacy-state-root",
            **legacy_env_values,
            UNRELATED_CADRUMO_TYPO="1",
            CADRUMO_AUTH_PROVIDER="certificate",
        ):
            settings = settings_without_env_file(cadrumo_local_storage_root=tmp_path / "cadrumo-state")
        assert settings.cadrumo_auth_provider is AuthProviderKind.CERTIFICATE

    def test_relative_env_paths_resolve_from_project_root(self, tmp_path: Path) -> None:
        """Relative storage refinements follow the explicit storage root on every platform."""
        with _isolated_aeat_env(CADRUMO_WORKFLOW_RUNS_DIR="env/workflow/runs"):
            settings = settings_without_env_file(cadrumo_local_storage_root=tmp_path / "cadrumo-state")
        assert settings.cadrumo_workflow_runs_dir == tmp_path / "cadrumo-state" / "env" / "workflow" / "runs"

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

    _EXEMPT_PATH_FIELDS: frozenset[str] = frozenset[str]()
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
        """Arbitrary relative storage refinements follow the explicit local root."""
        with _isolated_aeat_env(
            CADRUMO_INVOICES_DIR="var/probe-category/invoices",
            CADRUMO_ATTACHMENTS_DIR="var/probe-category/attachments",
            CADRUMO_RUNS_DIR="var/probe-runs",
        ):
            settings = settings_without_env_file(cadrumo_local_storage_root=tmp_path / "cadrumo-state")
        app_root = tmp_path / "cadrumo-state"
        assert settings.cadrumo_invoices_dir == app_root / "var" / "probe-category" / "invoices"
        assert settings.cadrumo_attachments_dir == app_root / "var" / "probe-category" / "attachments"
        assert settings.cadrumo_runs_dir == app_root / "var" / "probe-runs"


def _parse_env_example_kv() -> dict[str, str]:
    """Extract ``NAME=value`` pairs from ``env/.env.example``.

    Mirrors :func:`_parse_env_example_vars` but keeps the value, so a test can
    replay the shipped template through the real process environment — the
    only channel a developer's own ``uv run --env-file env/.env`` (or an
    exported shell profile) actually uses. There is no dotenv reading inside
    ``Settings`` itself to bind a subclass to.
    """
    pairs: dict[str, str] = {}
    for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([A-Z_][A-Z0-9_]*)=(.*)$", stripped)
        if match:
            pairs[match.group(1)] = match.group(2)
    return pairs


class TestDatabaseUrlDerivation:
    """``cadrumo_database_url`` must stay coherent with ``cadrumo_local_storage_root``.

    Setting ``CADRUMO_LOCAL_STORAGE_ROOT`` alone — with no explicit
    ``CADRUMO_DATABASE_URL`` and no active profile — must never leave the
    URL empty. An empty URL made first-contact CLI commands exit-5 with
    a raw internal ``cadrumo_database_url is empty`` error instead of the
    clean no-active-profile refusal.
    """

    def test_storage_root_alone_derives_root_level_fallback_url(self, tmp_path: Path) -> None:
        """Storage root without an explicit URL or active profile derives the
        ``sqlite:///<root>/cadrumo.db`` fallback rather than staying empty."""
        storage_root = tmp_path / "aeat-state"

        with _isolated_aeat_env(CADRUMO_LOCAL_STORAGE_ROOT=storage_root.as_posix()):
            settings = settings_without_env_file()

        expected = (
            f"sqlite:///{(storage_root / storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath).as_posix()}"
        )
        assert settings.cadrumo_database_url == expected
        assert settings.cadrumo_database_url, "URL must never be empty when the storage root is set"

    def test_explicit_database_url_overrides_storage_root_derivation(self, tmp_path: Path) -> None:
        """An explicit ``CADRUMO_DATABASE_URL`` wins over the derived fallback."""
        explicit_url = f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}"

        with _isolated_aeat_env(
            CADRUMO_LOCAL_STORAGE_ROOT=(tmp_path / "aeat-state").as_posix(),
            CADRUMO_DATABASE_URL=explicit_url,
        ):
            settings = settings_without_env_file()

        assert settings.cadrumo_database_url == explicit_url

    def test_active_profile_derives_per_bucket_url(self, tmp_path: Path) -> None:
        """An active profile still derives the per-bucket SQLite URL; the
        root-level fallback only applies when no bucket resolves.

        The selection arrives through the in-process channel the ``--profile``
        flag writes, because no environment source populates it.
        """
        storage_root = tmp_path / "aeat-state"

        with _isolated_aeat_env(CADRUMO_LOCAL_STORAGE_ROOT=storage_root.as_posix()):
            settings = settings_without_env_file(cadrumo_active_profile="acme")

        expected_database_file = (
            storage_root
            / storage_location(StorageCategory.BUCKETS).relative_path()
            / "acme"
            / storage_location(StorageCategory.BUCKET_DATABASE_FILE).relative_path()
        )
        expected = f"sqlite:///{expected_database_file.as_posix()}"
        assert settings.cadrumo_database_url == expected

    def test_load_settings_routes_from_its_single_atomic_pointer_observation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A switch after the cache observation cannot construct B under A's key."""
        from .. import bucket_pointer, config

        storage_root = tmp_path / "aeat-state"
        observed = [
            BucketPointer.selected(bucket_id="profile-a", transition_revision=4),
            BucketPointer.selected(bucket_id="profile-b", transition_revision=5),
        ]
        calls = 0

        def switch_after_observation(root: Path) -> BucketPointer:
            nonlocal calls
            assert root == storage_root
            selected = observed[min(calls, 1)]
            calls += 1
            return selected

        monkeypatch.setattr(bucket_pointer, "read_pointer", switch_after_observation)
        override_token = config.settings_override.set(None)
        reset_settings_cache()
        try:
            with _isolated_aeat_env(CADRUMO_LOCAL_STORAGE_ROOT=storage_root.as_posix()):
                settings = load_settings()
        finally:
            reset_settings_cache()
            config.settings_override.reset(override_token)

        assert calls == 1
        assert classify_storage_route(settings).bucket_id == "profile-a"

    def test_load_settings_normalizes_a_relative_root_before_the_atomic_observation(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A relative root cannot reread B while constructing the cache entry for A.

        The cache-key observation and the settings field anchor the relative
        root through the same declaration, so both name one canonical root.
        """
        from .. import bucket_pointer, config

        relative_root = Path("relative-s168-root")
        canonical_root = (project_root() / relative_root).resolve()
        observed = [
            BucketPointer.selected(bucket_id="profile-a", transition_revision=4),
            BucketPointer.selected(bucket_id="profile-b", transition_revision=5),
        ]
        calls = 0

        def switch_after_observation(root: Path) -> BucketPointer:
            nonlocal calls
            assert root == canonical_root
            selected = observed[min(calls, 1)]
            calls += 1
            return selected

        monkeypatch.setattr(bucket_pointer, "read_pointer", switch_after_observation)
        override_token = config.settings_override.set(None)
        reset_settings_cache()
        try:
            with _isolated_aeat_env(CADRUMO_LOCAL_STORAGE_ROOT=relative_root.as_posix()):
                settings = load_settings()
        finally:
            reset_settings_cache()
            config.settings_override.reset(override_token)

        assert calls == 1
        assert settings.cadrumo_local_storage_root == canonical_root
        assert classify_storage_route(settings).bucket_id == "profile-a"

    def test_env_example_leaves_normal_profile_storage_on_the_bucket_route(self, tmp_path: Path) -> None:
        """The shipped environment template must not force a global database route.

        Replays every ``NAME=value`` pair from ``env/.env.example`` through the
        real process environment (the only channel a developer's own
        ``uv run --env-file env/.env`` actually populates), then confirms the
        template's blank ``CADRUMO_DATABASE_URL`` still leaves storage on the
        per-bucket route rather than forcing a global database.
        """
        storage_root = tmp_path / "cadrumo-state"
        bucket_id = "profile-bucket"
        template_vars = _parse_env_example_kv()
        assert template_vars, "env/.env.example must declare at least one variable"

        with _isolated_aeat_env(**template_vars):
            settings = settings_without_env_file(
                cadrumo_local_storage_root=storage_root,
                cadrumo_active_profile=bucket_id,
            )

        expected_database_file = (
            storage_root
            / storage_location(StorageCategory.BUCKETS).relative_path()
            / bucket_id
            / storage_location(StorageCategory.BUCKET_DATABASE_FILE).relative_path()
        )
        expected = f"sqlite:///{expected_database_file.as_posix()}"
        assert settings.cadrumo_database_url == expected
        assert classify_storage_route(settings).kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE
