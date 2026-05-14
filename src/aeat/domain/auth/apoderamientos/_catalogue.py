"""Scope catalogue loader and scope-token parser."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ....core.errors import AeatError

_DEFAULT_CATALOGUE_PATH = (
    Path(__file__).resolve().parents[5]
    / "registry"
    / "aeat"
    / "apoderamientos"
    / "scopes.toml"
)

ALL_TOKEN = "ALL"


class UnknownScopeError(AeatError):
    """Raised when a CLI-supplied scope is not in the shipped catalogue."""


class ApoderadoScope(BaseModel):
    """One scope entry: code plus optional modelo binding."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    code: str = Field(min_length=1, max_length=32)
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

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    catalogue_version: str = Field(min_length=1)
    scopes: tuple[ApoderadoScope, ...]

    def code_set(self) -> frozenset[str]:
        return frozenset(scope.code for scope in self.scopes)

    def get(self, code: str) -> ApoderadoScope | None:
        for scope in self.scopes:
            if scope.code == code:
                return scope
        return None


def load_default_catalogue(path: Path | None = None) -> ApoderamientosCatalogue:
    """Load the shipped scope catalogue from disk."""
    resolved = path or _DEFAULT_CATALOGUE_PATH
    raw = tomllib.loads(resolved.read_text(encoding="utf-8"))
    scopes = tuple(
        ApoderadoScope(
            code=entry["code"],
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
        if "," in token:
            raise UnknownScopeError(
                f"scope token {token!r} contains a comma; pass --scope repeatedly instead",
                suggestion="aeat config auth apoderado configure --scope SCOPE1 --scope SCOPE2",
            )
        if token != token.upper():
            raise UnknownScopeError(
                f"scope token {token!r} must be uppercase",
                suggestion="aeat config auth apoderado configure",
            )
        if token == ALL_TOKEN:
            for code in expand_all_token(catalogue):
                if code not in seen:
                    seen.add(code)
                    result.append(code)
            continue
        if token not in known:
            raise UnknownScopeError(
                f"scope code {token!r} is not in catalogue version {catalogue.catalogue_version!r}",
                suggestion="aeat config auth apoderado configure --scope ALL",
            )
        if token not in seen:
            seen.add(token)
            result.append(token)
    return tuple(result)


__all__ = [
    "ALL_TOKEN",
    "ApoderadoScope",
    "ApoderamientosCatalogue",
    "UnknownScopeError",
    "expand_all_token",
    "load_default_catalogue",
    "parse_scope_tokens",
]
