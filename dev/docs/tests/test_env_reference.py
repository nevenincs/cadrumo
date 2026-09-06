"""Drift gates binding the environment-overrides surface to the settings model.

Three surfaces describe the same closed set of environment overrides:

- :class:`cadrumo.core.config.Settings` — the live model, the source of truth;
- ``docs/reference/environment-overrides.md`` — the generated reference page
  (:mod:`dev.docs.env_reference`);
- ``env/.env.example`` — the hand-annotated template operators copy.

These gates fail loudly when any of the three drifts: a stale generated page,
a template key the model no longer reads (a dead knob an operator could set
in vain), or a model field the template omits (an override no operator can
discover). User-facing guides carry no environment overrides at all — the
companion conformance sweep in the docs gates keeps the one sanctioned home
under ``docs/reference``.
"""

from __future__ import annotations

import re

import pytest

from ..._paths import REPO_ROOT
from ..env_reference import render_environment_reference, target_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT
_ENV_EXAMPLE = _REPO_ROOT / "env" / ".env.example"
_KEY_RE = re.compile(r"^#?\s*([A-Z][A-Z0-9_]+)=", re.MULTILINE)


def _settings_env_names() -> frozenset[str]:
    """Return the names an environment source can actually populate.

    Keyed on the model's own environment inventory rather than every field,
    so a field whose environment source has been severed is neither demanded
    in the template nor reported as a dead knob.
    """
    from cadrumo.core.config import Settings

    return frozenset(Settings.env_var_names())


def test_generated_page_is_fresh() -> None:
    """The committed page equals fresh generator output byte for byte."""
    path = target_path(_REPO_ROOT)
    assert path.is_file(), f"missing generated page: {path}; run python -m dev.docs.env_reference"
    assert path.read_bytes() == render_environment_reference().encode("utf-8"), (
        f"{path} is stale; regenerate with python -m dev.docs.env_reference"
    )


def test_env_example_keys_all_resolve_to_settings_fields() -> None:
    """Every key in env/.env.example is a live Settings env name."""
    keys = frozenset(_KEY_RE.findall(_ENV_EXAMPLE.read_text(encoding="utf-8")))
    dead = sorted(keys - _settings_env_names())
    assert not dead, f"env/.env.example keys with no Settings field (dead knobs): {dead}"


def test_settings_fields_all_present_in_env_example() -> None:
    """Every Settings env name appears in env/.env.example."""
    keys = frozenset(_KEY_RE.findall(_ENV_EXAMPLE.read_text(encoding="utf-8")))
    undocumented = sorted(_settings_env_names() - keys)
    assert not undocumented, f"Settings fields missing from env/.env.example: {undocumented}"


def test_every_settings_field_carries_a_description() -> None:
    """A field without a description renders an empty reference row."""
    from cadrumo.core.config import Settings

    assert Settings.model_fields, "Settings declares no fields; this gate would pass over an empty model"
    missing = sorted(name for name, field in Settings.model_fields.items() if not field.description)
    assert not missing, f"Settings fields without descriptions: {missing}"
