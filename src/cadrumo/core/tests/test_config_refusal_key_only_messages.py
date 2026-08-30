"""Absence gate: no Settings or storage-tree refusal carries an authored sentence.

Every refusal raised out of :mod:`core.config` must reach the operator through
its registered locale key plus machine facts on the error context. Pinning the
key and the facts alone cannot hold that line: message resolution prefers
``translated_message``, so English passed alongside the key stays green under a
key-and-context assertion while ``str(exc)`` still prefers the positional
argument and carries the sentence into tracebacks, logs, and every boundary
rendering the exception directly, in every locale.

Each producer is therefore asserted for the *absence* of that text.

Real ``Settings`` validation, real ``override_settings`` seam, real filesystem
under ``tmp_path``. No doubles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from ..config import load_settings, override_settings
from ..errors.error_codes import get_registered_error_code
from ..errors.hierarchy import CoreValidationError
from ..storage_materialization import ensure_storage_tree

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CORE_VALIDATION_KEY = "errors.integrity.integrity_cadrumo_core_validation"


def _assert_key_only(error: CoreValidationError, expected_context: dict[str, object]) -> None:
    """Assert the refusal renders as its key and carries only machine facts."""
    assert error.translated_message == _CORE_VALIDATION_KEY
    assert str(error) == error.translated_message, f"the raise site carries an authored sentence: {str(error)!r}"
    assert str(error) == _CORE_VALIDATION_KEY
    assert error.context == expected_context
    assert get_registered_error_code(error).code == "INTEGRITY_CADRUMO_CORE_VALIDATION"


def _settings_refusal(excinfo: pytest.ExceptionInfo[ValidationError]) -> CoreValidationError:
    """Recover the typed refusal pydantic wrapped when a Settings validator raised.

    Pydantic embeds ``str(exc)`` of the raised ``ValueError`` in the rendered
    ``ValidationError``, so an authored sentence would leak through the wrapper
    too. The original exception survives under the error's ``ctx``, which lets
    this module assert on the refusal itself rather than on pydantic's
    rendering of it.
    """
    inner = excinfo.value.errors()[0].get("ctx", {}).get("error")
    assert isinstance(inner, CoreValidationError)
    return inner


def test_live_iva_timeout_hierarchy_refusal_is_key_only() -> None:
    """A capture timeout at or above the surface timeout refuses key-only."""
    with (
        pytest.raises(ValidationError) as excinfo,
        override_settings(
            cadrumo_live_iva_declaration_capture_timeout_ms=90_000,
            cadrumo_live_iva_surface_timeout_ms=90_000,
        ),
    ):
        pytest.fail("the with-block must not execute when the timeout hierarchy is violated")

    _assert_key_only(
        _settings_refusal(excinfo),
        {
            "capture_timeout_ms": 90_000,
            "surface_timeout_ms": 90_000,
            "capture_below_surface": False,
        },
    )


def test_url_template_placeholder_refusals_are_key_only() -> None:
    """Both URL-template placeholder refusals render as the key with typed facts."""
    with (
        pytest.raises(ValidationError) as excinfo,
        override_settings(aeat_status_detail_url_template="https://example.invalid/no-placeholder"),
    ):
        pytest.fail("the with-block must not execute when the template omits its placeholder")
    _assert_key_only(
        _settings_refusal(excinfo),
        {
            "setting": "aeat_status_detail_url_template",
            "required_placeholder": "{expediente_id}",
            "placeholder_present": False,
        },
    )

    with (
        pytest.raises(ValidationError) as excinfo,
        override_settings(aeat_clave_sede_access_url_template="https://example.invalid/no-target"),
    ):
        pytest.fail("the with-block must not execute when the template omits its target placeholder")
    _assert_key_only(
        _settings_refusal(excinfo),
        {
            "required_placeholder": "{target}",
            "placeholder_present": False,
            "placeholder_purpose": "url_encoded_post_auth_path",
        },
    )


def test_clave_dni_fecha_refusals_are_key_only() -> None:
    """Both DNI-validity-date refusals render as the key with typed facts.

    The two branches are distinct failures: a value the canonical-form regex
    rejects outright, and a value shaped like the canonical form that no
    calendar date resolves.
    """
    with (
        pytest.raises(ValidationError) as excinfo,
        override_settings(cadrumo_clave_movil_dni_fecha="20300101"),
    ):
        pytest.fail("the with-block must not execute when the date is not canonical")
    _assert_key_only(
        _settings_refusal(excinfo),
        {
            "env_var": "CADRUMO_CLAVE_MOVIL_DNI_FECHA",
            "required_format": "YYYY-MM-DD",
            "canonical_form": False,
        },
    )

    with (
        pytest.raises(ValidationError) as excinfo,
        override_settings(cadrumo_clave_movil_dni_fecha="2030-02-31"),
    ):
        pytest.fail("the with-block must not execute when the date does not resolve")
    _assert_key_only(
        _settings_refusal(excinfo),
        {
            "env_var": "CADRUMO_CLAVE_MOVIL_DNI_FECHA",
            "required_format": "YYYY-MM-DD",
            "resolvable_date": False,
        },
    )


def test_storage_tree_occupancy_refusal_is_key_only(tmp_path: Path) -> None:
    """A taxonomy directory occupied by a file refuses through the key alone."""
    root = tmp_path / "occupied-root"
    root.mkdir()
    (root / "tokens").write_text("a file where a directory belongs", encoding="utf-8")

    with override_settings(cadrumo_local_storage_root=str(root)), pytest.raises(CoreValidationError) as excinfo:
        ensure_storage_tree(load_settings())

    _assert_key_only(
        excinfo.value,
        {
            "state_directory_target": str(root / "tokens"),
            "occupied_by_file": True,
            "directory_created": False,
        },
    )


def test_storage_tree_mkdir_failure_refusal_is_key_only(tmp_path: Path) -> None:
    """An unmakeable taxonomy directory refuses through the key alone.

    A file planted at an intermediate path the taxonomy expects to be a
    directory makes the nested target both unstattable and unmakeable, which is
    the second of the two refusal branches: the tree could not be completed,
    rather than a target being occupied outright.
    """
    root = tmp_path / "unmakeable-root"
    root.mkdir()
    (root / "cache").write_text("a file blocking the nested taxonomy branch", encoding="utf-8")

    with override_settings(cadrumo_local_storage_root=str(root)), pytest.raises(CoreValidationError) as excinfo:
        ensure_storage_tree(load_settings())

    context = excinfo.value.context
    assert context is not None
    assert context["state_directory_target"] == str(root / "cache" / "llm-cache")
    assert context["occupied_by_file"] is False
    assert context["directory_created"] is False
    assert isinstance(context["mkdir_error_type"], str)
    assert str(excinfo.value) == _CORE_VALIDATION_KEY, (
        f"the raise site carries an authored sentence: {str(excinfo.value)!r}"
    )
