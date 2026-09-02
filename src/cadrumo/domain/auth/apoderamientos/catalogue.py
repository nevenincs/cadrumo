"""Apoderamiento scope catalogue loader and parser.

Defines :class:`ApoderadoScope` and :class:`ApoderamientosCatalogue`, loads the
shipped registry through :func:`load_default_catalogue`, and validates
operator-supplied tokens with :func:`parse_scope_tokens`.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from ....core.errors.hierarchy import CadrumoError
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.resources.bundled_data import bundled_path

_DEFAULT_CATALOGUE_PATH = bundled_path("registry", "aeat", "apoderamientos", "scopes.toml")

ALL_TOKEN = "ALL"


ApoderadoScopeCode = Annotated[str, StringConstraints(min_length=1, max_length=32)]
"""The AEAT code naming one apoderamiento scope."""

ApoderadoScopeName = Annotated[str, StringConstraints(min_length=1, max_length=200)]
"""One scope's printed name, in either catalogue language."""


class UnknownScopeError(CadrumoError):
    """Raised when a CLI-supplied scope is not in the shipped catalogue."""


class ApoderadoScope(BaseModel):
    """One scope entry: code plus localized names plus optional modelo binding."""

    model_config = STRICT_FROZEN_CONFIG

    code: ApoderadoScopeCode
    name_es: ApoderadoScopeName
    name_en: ApoderadoScopeName
    modelo_codes: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("code")
    @classmethod
    def _code_is_uppercase_alnum(cls, value: str) -> str:
        if not value.isupper():
            raise ValueError(f"scope code must be uppercase, got {value!r}")
        if not value.replace("_", "").isalnum():
            raise ValueError(f"scope code must be alphanumeric (underscores allowed), got {value!r}")
        return value


class ApoderamientosCatalogue(BaseModel):
    """Loaded scope catalogue with version metadata."""

    model_config = STRICT_FROZEN_CONFIG

    catalogue_version: str = Field(min_length=1)
    scopes: tuple[ApoderadoScope, ...]

    def code_set(self) -> frozenset[str]:
        """Return the set of every scope code declared in this catalogue."""
        return frozenset(scope.code for scope in self.scopes)

    def get(self, code: str) -> ApoderadoScope | None:
        """Return the :class:`ApoderadoScope` for ``code``, or ``None`` if absent."""
        for scope in self.scopes:
            if scope.code == code:
                return scope
        return None


def load_default_catalogue(path: Path | None = None) -> ApoderamientosCatalogue:
    """Load the shipped scope catalogue from disk.

    Returns:
        The validated :class:`ApoderamientosCatalogue` with all registered scopes.
    """
    resolved = path or _DEFAULT_CATALOGUE_PATH
    raw = tomllib.loads(resolved.read_text(encoding="utf-8"))
    scopes = tuple(
        ApoderadoScope(
            code=entry["code"],
            name_es=entry["name_es"],
            name_en=entry["name_en"],
            modelo_codes=tuple(entry.get("modelo_codes", [])),
        )
        for entry in raw.get("scopes", [])
    )
    return ApoderamientosCatalogue(
        catalogue_version=raw["catalogue_version"],
        scopes=scopes,
    )


def expand_all_token(catalogue: ApoderamientosCatalogue) -> tuple[str, ...]:
    """Expand the literal ``ALL`` into every catalogue code, alphabetically sorted."""
    return tuple(sorted(catalogue.code_set()))


def parse_scope_tokens(
    raw_tokens: tuple[str, ...],
    catalogue: ApoderamientosCatalogue,
) -> tuple[str, ...]:
    """Parse and validate a tuple of operator-supplied scope tokens.

    Rules:
      * each token must be uppercase (lower-case input is rejected)
      * comma-separated values rejected at this boundary
      * unknown codes refuse with :class:`UnknownScopeError`
      * the literal ``ALL`` expands into every catalogue code
      * duplicates are silently deduplicated; order is preserved by
        first occurrence with ``ALL`` placed at expansion site
    """
    known = catalogue.code_set()
    result: list[str] = []
    seen: set[str] = set()
    for token in raw_tokens:
        _validate_scope_token_shape(token)
        for code in _resolve_scope_token(token, catalogue=catalogue, known=known):
            if code not in seen:
                seen.add(code)
                result.append(code)
    return tuple(result)


def _validate_scope_token_shape(token: str) -> None:
    """Reject comma-separated and lowercase tokens before catalogue lookup.

    The diagnostic preserves the rejected token and validation rule as factual
    context. The catalogue-lookup step is the only side-effecting check that
    needs the catalogue handle, so keeping these shape checks separate lets the
    resolver run on already-clean input.
    """
    if "," in token:
        raise UnknownScopeError(
            translated_message="errors.refused.refused_apoderado_unknown_scope",
            context={"scope_token": token, "validation_rule": "no_comma_separated_values"},
        )
    if token != token.upper():
        raise UnknownScopeError(
            translated_message="errors.refused.refused_apoderado_unknown_scope",
            context={"scope_token": token, "validation_rule": "uppercase"},
        )


def _resolve_scope_token(
    token: str,
    *,
    catalogue: ApoderamientosCatalogue,
    known: frozenset[str],
) -> tuple[str, ...]:
    """Resolve one validated scope token to the catalogue codes it expands to.

    The literal ``ALL`` token expands to every catalogue code in sorted
    catalogue-code order. Any other token must be a known catalogue
    code; otherwise an :class:`UnknownScopeError` is raised with the
    catalogue version that rejected it so the operator can spot
    catalogue drift versus their local fixture.
    """
    if token == ALL_TOKEN:
        return tuple(expand_all_token(catalogue))
    if token not in known:
        raise UnknownScopeError(
            translated_message="errors.refused.refused_apoderado_unknown_scope",
            context={
                "catalogue_version": catalogue.catalogue_version,
                "scope_token": token,
                "validation_rule": "declared_catalogue_code",
            },
        )
    return (token,)


__all__ = [
    "ALL_TOKEN",
    "ApoderadoScope",
    "ApoderamientosCatalogue",
    "UnknownScopeError",
    "expand_all_token",
    "load_default_catalogue",
    "parse_scope_tokens",
]
