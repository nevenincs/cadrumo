"""Malformed user-profile schema sources are refused by the development capture parser."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from dev.registry.compiler.profile_schema import capture_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Structurally well-formed TOML whose values do not satisfy the strict schema
#: model: the ``[schema]`` table declares only an id, so title, version and both
#: policies are absent and the section carries no fields.
_CONTRACT_VIOLATING_SCHEMA: Final[str] = '[schema]\nid = "cadrumo.user_profile"\n\n[[sections]]\nkey = "a"\n'

#: The same document with a top-level scalar where an array of tables belongs.
#: The scalar precedes every table header because TOML binds a bare key to the
#: table most recently opened.
_SCALAR_DERIVED_SELECTORS_SCHEMA: Final[str] = (
    'derived_selectors = 3\n\n[schema]\nid = "cadrumo.user_profile"\n\n[[sections]]\nkey = "a"\n'
)

#: A quote that is never closed, so the parser refuses before any table exists.
_UNPARSEABLE_SCHEMA: Final[str] = "id = 'unterminated\n"

#: A valid document declaring no sections at all.
_SECTIONLESS_SCHEMA: Final[str] = '[schema]\nid = "cadrumo.user_profile"\n'


@pytest.mark.parametrize(
    ("filename", "payload", "message"),
    [
        ("unparseable.toml", _UNPARSEABLE_SCHEMA, "not valid UTF-8 TOML"),
        ("sectionless.toml", _SECTIONLESS_SCHEMA, "invalid envelope"),
        ("scalar-selectors.toml", _SCALAR_DERIVED_SELECTORS_SCHEMA, "invalid derived_selectors member"),
        ("contract-violating.toml", _CONTRACT_VIOLATING_SCHEMA, "failed typed validation"),
    ],
)
def test_schema_load_refusals_use_the_development_parser_contract(
    tmp_path: Path,
    filename: str,
    payload: str,
    message: str,
) -> None:
    """Every malformed custom source is refused by the development parser.

    Driven by real files on disk: an unterminated quote the parser refuses, a
    document declaring no sections, a scalar where an array of tables belongs,
    and a well-formed document whose values violate the strict model. No patch,
    stub or monkeypatch participates.
    """
    schema_path = tmp_path / filename
    schema_path.write_text(payload, encoding="utf-8")

    with pytest.raises(RegistryValidationError, match=message):
        capture_profile_schema(schema_path)


def test_schema_model_validation_refusal_counts_violations_without_restating_them(tmp_path: Path) -> None:
    """The strict-model failure reports how many constraints failed, not which values.

    The count is the fact; the typed detail survives as the exception's cause
    rather than being flattened into the refusal, which is what the previous
    shape did with an interpolated ``{exc}``.
    """
    schema_path = tmp_path / "contract-violating.toml"
    schema_path.write_text(_CONTRACT_VIOLATING_SCHEMA, encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="failed typed validation") as exc_info:
        capture_profile_schema(schema_path)

    assert isinstance(exc_info.value.__cause__, ValidationError)
    assert len(exc_info.value.__cause__.errors()) >= 1
