"""Structural honesty assertions for the shared locale catalogues."""

from __future__ import annotations

import tomllib
from functools import cache

import pytest

from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_continuity_locale_key,
    casilla_occurrence_locale_key,
)

from .._paths import LOCALES_DIR, SRC_DIR
from ..manager import LocaleManager, locale_catalogue_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_MODELO_SCHEMA_PREFIX = "modelo.schema."
_MODELO_SOURCE_SUFFIXES = (".label", ".title", ".official_name")


def test_runtime_locale_root_contains_no_development_metadata() -> None:
    """The shipped locale root contains catalogues, not audit dispositions."""

    assert list(LOCALES_DIR.glob("*.json")) == []


def _is_modelo_source_key(key: str) -> bool:
    """Return whether a Modelo leaf carries mandatory official source text."""

    return key.startswith(_MODELO_SCHEMA_PREFIX) and key.endswith(_MODELO_SOURCE_SUFFIXES)


# Recursive YAML node: either a leaf string or a nested mapping.
type _LocaleNode = str | dict[str, "_LocaleNode"] | None


def _flatten(mapping: dict[str, _LocaleNode], prefix: str = "") -> dict[str, str | None]:
    """Walk a nested YAML mapping and return ``{dotted_key: leaf}``."""

    result: dict[str, str | None] = {}
    for key, value in mapping.items():
        sub = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten(value, sub))
        else:
            result[sub] = value
    return result


@cache
def _parsed_catalogue(locale_code: str) -> tuple[tuple[str, str | None], ...]:
    """Parse and flatten one shipped catalogue, once per process.

    The catalogues are ~3 MB each and pure-Python YAML parsing measured ~7s
    apiece, while the five gates below read the same four files roughly
    nineteen times between them -- so this module spent almost its entire
    runtime re-parsing four unchanging files.

    ``yaml.CSafeLoader`` is libyaml, the C parser, and measured 0.773s against
    7.402s for the pure-Python loader on the largest catalogue. Both loaders
    were confirmed to produce equal documents for all four shipped locales
    before this switched; the fallback keeps the gate runnable on a build of
    PyYAML compiled without libyaml. This mirrors what the production renderer
    in ``core.i18n`` already does.

    Parsing here stays INDEPENDENT of the production locale reader on purpose.
    These gates make claims about what the shipped FILES contain, so borrowing
    the reader would let a reader that silently dropped entries certify its own
    view of the catalogue rather than the catalogue.

    The proof of scan lives here rather than at each gate because several gates
    read the same four catalogues: guarding the reader means one added later
    inherits it instead of forgetting it. An empty catalogue carries no blank
    value, no key echo and no reserved token, so each of those gates would
    report exactly what a clean catalogue reports.
    """
    source = locale_catalogue_source(LOCALES_DIR, locale_code)
    assert source is not None, f"no committed catalogue for {locale_code!r}; every honesty gate over it is vacuous"
    raw = LocaleManager(src_dir=SRC_DIR, locales_dir=LOCALES_DIR).load_locale(source)
    leaves = _flatten(raw if isinstance(raw, dict) else {})
    assert leaves, f"catalogue {locale_code!r} flattened to no leaves; every honesty gate over it is vacuous"
    return tuple(leaves.items())


def _catalogue_leaves(locale_code: str) -> dict[str, str | None]:
    """Return one shipped catalogue's flattened leaves.

    Rebuilt per call from the cached parse so each gate owns its own mapping.
    Handing out one shared dict would make every caller's correctness depend on
    no other caller ever mutating it -- safe only by convention, where the
    copy costs microseconds against a multi-second parse.
    """
    return dict(_parsed_catalogue(locale_code))


@cache
def _continuity_backing() -> dict[str, str]:
    """Map each casilla occurrence label key to its continuity label key.

    Read from the registry's casilla TOML rather than through the validated
    authority, because this gate makes a claim about the SHIPPED catalogues and
    must stay answerable while the registry is refusing validation for unrelated
    reasons. It mirrors exactly what the loader does at
    :func:`~cadrumo.domain.calculations.registry.modelo_localization._localised_casilla`:
    read ``id`` and ``continuidad_id`` off the raw casilla table and derive both
    keys with the same two canonical encoders.

    Returns:
        ``{occurrence_label_key: continuity_label_key}`` for every casilla that
        declares a ``continuidad_id``. A casilla without one is simply absent,
        which is what makes its null occurrence value a real offender.
    """
    backing: dict[str, str] = {}
    modelos_dir = SRC_DIR / "_data" / "registry" / "aeat" / "modelos"
    for casilla_file in modelos_dir.glob("*/revisions/*/casillas/*.toml"):
        modelo_id = casilla_file.parents[3].name
        try:
            document = tomllib.loads(casilla_file.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):  # pragma: no cover - unreadable fragment
            continue
        for revision_id, revision in (document.get("revisions") or {}).items():
            if not isinstance(revision, dict):
                continue
            for casilla in revision.get("casillas") or ():
                if not isinstance(casilla, dict):
                    continue
                casilla_id = casilla.get("id")
                continuidad_id = casilla.get("continuidad_id")
                if not isinstance(casilla_id, str) or not isinstance(continuidad_id, str):
                    continue
                backing[
                    casilla_occurrence_locale_key(modelo_id, revision_id, casilla_id, ModeloLocalizationFieldKind.LABEL)
                ] = casilla_continuity_locale_key(modelo_id, continuidad_id, ModeloLocalizationFieldKind.LABEL)
    assert backing, "no casilla declares a continuidad_id; the continuity exemption below would be vacuous"
    return backing


def _key_echo_offenders(flat_leaves: dict[str, str | None]) -> list[str]:
    """Return keys whose value is the key itself — the scaffold placeholder.

    Whitespace-normalised, and tolerant of trailing punctuation, so one
    stray character cannot convert a placeholder into "authored".
    """

    offenders: list[str] = []
    for key, value in flat_leaves.items():
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if stripped == key or stripped.rstrip(".:").rstrip() == key:
            offenders.append(key)
    return sorted(offenders)


def _blank_offenders(flat_leaves: dict[str, str | None]) -> list[str]:
    """Return keys whose value is empty or whitespace-only."""

    return sorted(key for key, value in flat_leaves.items() if isinstance(value, str) and not value.strip())


def _reserved_token_offenders(flat_leaves: dict[str, str | None]) -> list[str]:
    """Return keys whose value carries a token tr() can never interpolate.

    ``tr()`` consumes ``locale`` and ``default`` as rendering directives and
    strips them from the interpolation map, so a catalogue token named after
    either is permanently unfillable regardless of what a call site passes.
    """
    from cadrumo.core.i18n import extract_placeholders

    from .._status import RESERVED_INTERPOLATION_TOKENS

    return sorted(
        key
        for key, value in flat_leaves.items()
        if isinstance(value, str) and extract_placeholders(value) & RESERVED_INTERPOLATION_TOKENS
    )


def test_no_catalogue_value_carries_a_reserved_interpolation_token() -> None:
    """No locale value may name a tr() rendering directive as a placeholder.

    Such a token can never bind, so the value looks authored while being
    structurally broken. There is no allowlist and no ratchet: the shipped
    count is zero and must stay zero.
    """

    failures: list[str] = []
    for locale_code in ("ca", "en", "es", "hu"):
        leaves = _catalogue_leaves(locale_code)
        offenders = _reserved_token_offenders(leaves)
        if offenders:
            failures.append(
                f"{locale_code}.yml carries {len(offenders)} value(s) with a reserved interpolation "
                f"token (locale/default) that tr() can never fill. Rename the token (e.g. "
                f"locale_code) in the value AND the call site. Keys: {offenders[:5]}"
            )

    assert failures == [], "\n".join(failures)


def test_key_echo_offender_detection_discriminates() -> None:
    """The echo detector fires on injected echo variants and stays quiet otherwise."""

    assert _key_echo_offenders({"a.b": "a.b", "c.d": "translated"}) == ["a.b"]
    assert _key_echo_offenders({"a.b": "a.b ", "c.d": "a.b."}) == ["a.b"]
    assert _key_echo_offenders({"c.d": "c.d."}) == ["c.d"]
    assert _key_echo_offenders({"c.d": "translated"}) == []
    assert _blank_offenders({"a.b": "", "c.d": "  ", "e.f": "x"}) == ["a.b", "c.d"]


def test_no_catalogue_value_echoes_its_key() -> None:
    """A key-echo is a scaffold placeholder and the exact target is zero."""

    failures: list[str] = []
    for locale_code in ("ca", "en", "es", "hu"):
        leaves = _catalogue_leaves(locale_code)
        offenders = _key_echo_offenders(leaves)
        if offenders:
            failures.append(
                f"{locale_code}.yml carries {len(offenders)} key-echo value(s). "
                f"A key-echo is the scaffold placeholder, never a translation; author the "
                f"value via `python -m dev.locales set`. First five: {offenders[:5]}"
            )

    assert failures == [], "\n".join(failures)


def test_no_catalogue_value_is_blank() -> None:
    """No locale value may be empty or whitespace-only.

    A blank leaf reads as present to a membership check while rendering
    nothing to the operator. The CLI refuses to write one, so the shipped
    count is zero and must stay zero — no allowlist, no ratchet.
    """

    failures: list[str] = []
    for locale_code in ("ca", "en", "es", "hu"):
        leaves = _catalogue_leaves(locale_code)
        offenders = _blank_offenders(leaves)
        if offenders:
            failures.append(
                f"{locale_code}.yml carries {len(offenders)} blank value(s). Author the value via "
                f"`python -m dev.locales set`, or remove the key. Keys: {offenders[:5]}"
            )

    assert failures == [], "\n".join(failures)


def test_modelo_spanish_values_are_authority_source() -> None:
    """Every enrolled Modelo key resolves to one non-blank Spanish source value.

    A null occurrence value is NOT automatically an offender.
    :func:`~cadrumo.domain.calculations.registry.modelo_localization.resolve_modelo_localization`
    advances on the absence of a VALUE and carries the casilla's continuity key
    in the same chain, so a casilla whose ``continuidad_id`` has a populated
    continuity label already renders correct Spanish. Demanding a value on the
    occurrence key too would force a second copy of text that already has one
    curated home, and the next edit to the continuity label would silently not
    change what renders.

    What stays sharp is the other half: a null with NO continuity backing --
    no ``continuidad_id``, or one whose continuity label is itself blank --
    renders nothing, and still fails here.
    """

    es_keys = _catalogue_leaves("es")
    backing = _continuity_backing()
    offenders = sorted(
        key
        for key, value in es_keys.items()
        if _is_modelo_source_key(key)
        and (not isinstance(value, str) or not value.strip())
        and not (
            (continuity_key := backing.get(key)) is not None
            and isinstance(fallback := es_keys.get(continuity_key), str)
            and fallback.strip()
        )
    )
    assert offenders == [], (
        f"es.yml is the mandatory official Modelo source; these schema leaves are blank AND have no "
        f"populated continuity label to fall back to, so they render nothing: {offenders[:10]}"
    )
