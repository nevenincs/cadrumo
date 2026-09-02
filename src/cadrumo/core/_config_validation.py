"""Private Settings validator implementations; decorators remain in ``config``."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from .config_state_root import refuse_former_product_database
from .errors.hierarchy import ActiveProfilePointerError, CoreValidationError

if TYPE_CHECKING:
    from .bucket_pointer import BucketPointer
    from .config import Settings

_LOGGER = logging.getLogger(__name__)


def validate_live_iva_timeout_hierarchy(settings: Settings) -> Settings:
    if settings.cadrumo_live_iva_declaration_capture_timeout_ms >= settings.cadrumo_live_iva_surface_timeout_ms:
        raise CoreValidationError(
            translated_message="errors.integrity.integrity_cadrumo_core_validation",
            context={
                "capture_timeout_ms": settings.cadrumo_live_iva_declaration_capture_timeout_ms,
                "surface_timeout_ms": settings.cadrumo_live_iva_surface_timeout_ms,
                "capture_below_surface": False,
            },
        )
    return settings


def resolve_database_url_for_active_profile(
    settings: Settings, *, pointer_observation: tuple[Path, BucketPointer] | None
) -> Settings:
    """Resolve ``cadrumo_database_url`` through the active-profile chain.

    When the field is left empty (the production default), this
    validator computes the per-bucket SQLite URL at
    ``sqlite:///<cadrumo_local_storage_root>/buckets/<bucket-id>/db/cadrumo.db``.
    Tests that pass an explicit URL bypass the resolution — the
    validator only fires the computation when the field is empty.

    Active-profile resolution honours the operator-facing
    precedence chain:

    1. ``settings.cadrumo_active_profile`` (the in-process override the
       ``--profile`` flag and ``override_settings`` write; no
       environment variable reaches it).
    2. ``<cadrumo_local_storage_root>/active-profile`` plaintext
       pointer file written by ``profile create`` / ``config
       login``.

    When neither rung resolves, the field derives a root-level
    fallback at ``sqlite:///<cadrumo_local_storage_root>/cadrumo.db`` so
    the two storage settings stay coherent: setting
    ``CADRUMO_LOCAL_STORAGE_ROOT`` alone never leaves
    ``cadrumo_database_url`` empty. Cold-start commands still refuse
    before touching this fallback database — every profile-scoped
    path checks for an active profile first — so the fallback
    database is a placeholder that real per-profile data never
    lands in.
    """
    if settings.cadrumo_database_url:
        return settings
    bucket_id = (settings.cadrumo_active_profile or "").strip()
    if not bucket_id:
        # Delegate to the canonical pointer-file reader rather
        # than re-implementing the TOML parse inline. The reader
        # uses strict pydantic validation; this preserves the
        # one-resolver invariant for the active-profile pointer.
        #
        # Reached through the owning submodule, never the ``cadrumo.core``
        # facade. Both helpers are served by the package's PEP 562
        # ``__getattr__``, which is defined near the END of
        # ``core/__init__``; any module imported EARLIER in that file that
        # reaches this validator therefore asks a half-built package for an
        # attribute whose accessor does not exist yet, and the whole package
        # becomes unimportable. Naming the submodule keeps this resolvable
        # no matter how early the caller sits.
        from .bucket_pointer import pointer_path, read_pointer

        try:
            captured = pointer_observation
            pointer = (
                captured[1]
                if captured is not None and captured[0] == settings.cadrumo_local_storage_root
                else read_pointer(settings.cadrumo_local_storage_root)
            )
        except (OSError, ValueError) as exc:
            pointer_file = pointer_path(settings.cadrumo_local_storage_root)
            _LOGGER.debug(
                "Invalid active-profile pointer at %s; refusing root storage fallback",
                pointer_file,
                exc_info=True,
            )
            raise ActiveProfilePointerError(path=pointer_file) from exc
        if pointer.bucket_id is not None:
            bucket_id = pointer.bucket_id.strip()
    from .storage_taxonomy import StorageCategory, bucket_scoped_storage_path, storage_path

    if not bucket_id:
        refuse_former_product_database(settings.cadrumo_local_storage_root)
        fallback_db_path = storage_path(StorageCategory.ROOT_FALLBACK_DATABASE, settings=settings)
        object.__setattr__(
            settings,
            "cadrumo_database_url",
            f"sqlite:///{fallback_db_path.as_posix()}",
        )
        return settings
    refuse_former_product_database(settings.cadrumo_local_storage_root, bucket_id=bucket_id)
    # The layout comes from the one core storage authority. This fallback
    # used to re-type it, unpinned against the code that actually
    # provisions a bucket, so a rename would have routed the cold-start
    # database at a directory nothing else agreed on.
    bucket_db_path = bucket_scoped_storage_path(StorageCategory.BUCKET_DATABASE_FILE, bucket_id, settings=settings)
    object.__setattr__(
        settings,
        "cadrumo_database_url",
        f"sqlite:///{bucket_db_path.as_posix()}",
    )
    return settings


def resolve_output_dirs_under_storage_root(settings: Settings) -> Settings:
    """Root every derived output directory under ``cadrumo_local_storage_root``.

    Auth tokens, the diagnostic log, the encrypted-store substrate (secret,
    blob, audit), the append-only telemetry logs, the regenerable caches,
    and the durable generated-output directories all default to a subpath
    under the one state root that ``CADRUMO_LOCAL_STORAGE_ROOT`` scopes, per
    the core storage taxonomy. That root is the platform
    user-data location in every run mode, never inside a virtualenv or uv
    cache — the hazard a checkout-relative ``var/...`` default carries on
    an installed distribution. A developer who wants the tree inside their
    checkout sets ``CADRUMO_LOCAL_STORAGE_ROOT``.

    An explicit per-field env override (``CADRUMO_TOKEN_DIR``,
    ``CADRUMO_RUNS_DIR``, …) or a value supplied via an ``override_settings``
    block registers the field in ``model_fields_set`` and wins: the
    validator only computes the derived path when the field was left at its
    placeholder default. The validator only computes paths; provider
    factories and custody loaders decide how those directories are opened.

    Which fields those are, and what subpath each takes, is not decided
    here: the typed declaration is iterated directly so this validator
    cannot drift from it by carrying a table of its own. Members whose
    field is a deliberate opt-in override are excluded by the declaration
    rather than by a special case here -- deriving a default into one would
    silently retire the branch that selects on the field being unset.

    ``mode="after"`` guarantees ``cadrumo_local_storage_root`` is already
    populated when this runs.
    """
    from .storage_taxonomy import ROOT_DERIVED_STORAGE_LOCATIONS

    for location in ROOT_DERIVED_STORAGE_LOCATIONS:
        field_name = location.settings_field
        if field_name is None or field_name in settings.model_fields_set:
            continue
        object.__setattr__(settings, field_name, settings.cadrumo_local_storage_root / location.relative_path())
    return settings


def empty_optional_paths_are_none[ValueT](value: ValueT) -> ValueT | None:
    """Treat blank env vars for optional path fields as unset."""
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def empty_optional_secrets_are_none[ValueT](value: ValueT) -> ValueT | None:
    """Treat blank env vars for optional secret fields as unset."""
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def detail_url_template_has_expediente_id(value: str) -> str:
    """Reject templates that omit the ``{expediente_id}`` placeholder."""
    if "{expediente_id}" not in value:
        raise CoreValidationError(
            translated_message="errors.integrity.integrity_cadrumo_core_validation",
            context={
                "setting": "aeat_status_detail_url_template",
                "required_placeholder": "{expediente_id}",
                "placeholder_present": False,
            },
        )
    return value


def empty_optional_clave_fields_are_none[ValueT](value: ValueT) -> ValueT | None:
    """Treat blank env vars for optional Cl@ve identity/password fields as unset."""
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def clave_dni_fecha_is_iso_date(value: str | None) -> str | None:
    """Reject DNI validity dates that are not canonical ``YYYY-MM-DD``.

    Python 3.11's ``date.fromisoformat`` also accepts the compact
    ``YYYYMMDD`` form and ISO week dates, but AEAT's Cl@ve Móvil
    ``FECHA`` input expects the hyphenated canonical form. The
    regex rejects anything else before we delegate the semantic
    check to the stdlib parser.
    """
    if value is None:
        return None
    import re as _re

    if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise CoreValidationError(
            translated_message="errors.integrity.integrity_cadrumo_core_validation",
            context={
                "env_var": "CADRUMO_CLAVE_MOVIL_DNI_FECHA",
                "required_format": "YYYY-MM-DD",
                "canonical_form": False,
            },
        )
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise CoreValidationError(
            translated_message="errors.integrity.integrity_cadrumo_core_validation",
            context={
                "env_var": "CADRUMO_CLAVE_MOVIL_DNI_FECHA",
                "required_format": "YYYY-MM-DD",
                "resolvable_date": False,
            },
        ) from exc
    return value


def clave_sede_access_url_template_has_target(value: str) -> str:
    """Reject templates that omit the ``{target}`` placeholder."""
    if "{target}" not in value:
        raise CoreValidationError(
            translated_message="errors.integrity.integrity_cadrumo_core_validation",
            context={
                "required_placeholder": "{target}",
                "placeholder_present": False,
                "placeholder_purpose": "url_encoded_post_auth_path",
            },
        )
    return value


def normalize_repo_relative_paths(
    value: Path | None, *, normalizer: Callable[[Path | None], Path | None]
) -> Path | None:
    """Anchor repo-relative path settings to the application data root."""
    return normalizer(value)
