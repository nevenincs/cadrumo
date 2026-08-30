"""Parity gate: every key the ``--descendiente`` help advertises is one the parser honours.

The help string is the only place an operator learns how to express a descendant
fact non-interactively, and it drifted from the parser more than once.
Three keys the parser had accepted were missing from it, so a
filer refused at the write door and reaching for ``--help`` could not discover
how to state a rentas figure at all.

The sharper failure was in the Catalan catalogue, and it is the reason this gate
tests BEHAVIOUR rather than comparing the help against a hand-written key list.
That translation had localised the key TOKENS themselves, offering
``Convivència=`` and ``Custòdia=``. The parser upper-cases and compares tokens
literally, so those were not refused -- they were silently DROPPED, leaving
``convive_con_contribuyente`` at its cohabiting default. A Catalan operator
following the shipped help to declare a NON-cohabiting descendant therefore got
one marked as cohabiting, granting a mínimo por descendientes they were not
entitled to. A key list restated here would have matched the English help and
missed that entirely.

So the gate extracts whatever tokens the help actually advertises, in every
locale, and drives each one through the real parser. A token the parser ignores
fails, whether it was mistranslated, renamed, or never implemented.
"""

from __future__ import annotations

import re

import pytest

from ....core.i18n import tr
from ....domain.contribuyente.descendant_facts import parse_descendiente_flag

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: EVERY string describing the ``--descendiente`` format. There are two, and
#: guarding one is how the other drifted: the flag-verb help was corrected and
#: gated together, while this sibling — describing the same surface — sat
#: outside that frame from birth and accumulated four missing keys before this
#: campaign added three more.
_HELP_KEYS = (
    "cli.config.profile.descendiente.add_flag_help",
    "wizard.setup.flags.descendiente.help",
)
_LOCALES = ("en", "es", "ca", "hu")

#: Every (locale, string) pair both directions are asserted over.
_SURFACES = [(locale, key) for locale in _LOCALES for key in _HELP_KEYS]

#: A token is a bare ``KEY=`` occurrence in the help copy.
_TOKEN_RE = re.compile(r"([A-Za-zÀ-ÿ_]+)=")

#: The birth date every probe carries, since the parser requires it.
_BIRTH = "NACIMIENTO=2015-01-01"

#: One probe value per advertised key, chosen so the parsed record differs from
#: the value a DROPPED token would leave behind. Each pairs the flag fragment
#: with a predicate that is True only when the parser HONOURED it.
_PROBES: dict[str, tuple[str, str]] = {
    "NACIMIENTO": ("NACIMIENTO=2015-01-01", "birth_date"),
    # RELACION probes with a NON-entitling member on purpose. An entitling one
    # would also be produced by the INSCRIPCION probe's inference, so a parser
    # that dropped RELACION entirely could still look honoured; temporal
    # acogimiento is reachable only by reading the token itself.
    "RELACION": ("RELACION=acogimiento_temporal", "relacion"),
    "INSCRIPCION": ("INSCRIPCION=2016-01-01", "inscripcion_registro_civil_date"),
    # The acogimiento date needs an entitling relación to be accepted at all, so
    # its probe carries one. That makes the fragment a two-key probe, which is
    # correct here: the coherence rule is part of what the key means.
    "ACOGIMIENTO": (
        "RELACION=acogimiento_preadoptivo_o_permanente,ACOGIMIENTO=2016-01-01",
        "acogimiento_resolucion_date",
    ),
    "DISCAPACIDAD": ("DISCAPACIDAD=33", "discapacidad_grado"),
    "CONVIVENCIA": ("CONVIVENCIA=false", "convive_con_contribuyente"),
    # Probes the TRI-STATE: the baseline leaves it unset (None), so an
    # explicit false is a real change. A parser that collapsed unset onto
    # false would make this probe indistinguishable from a dropped token.
    "DEPENDENCIA": ("DEPENDENCIA=false", "dependencia_economica"),
    "CUSTODIA": ("CUSTODIA=true", "custodia_compartida"),
    "RENTAS": ("RENTAS=9500", "rentas_anuales_euros"),
    "DECLARACION_PROPIA": ("DECLARACION_PROPIA=true", "presenta_declaracion_propia"),
    "PRORRATA": ("PRORRATA=true", "prorrata_minimo"),
    # Probes the RANGE form for the same reason the guarderia map below does:
    # a mother entitled across a contiguous span is the dominant real shape.
    "MESES_TRABAJO": ("MESES_TRABAJO=1-6", "meses_madre_trabajo"),
    # The alta month must OPEN the declared span, so the probe declares 5-12.
    "ALTA_POSTERIOR_MES": ("ALTA_POSTERIOR_MES=5,MESES_TRABAJO=5-12", "alta_posterior_nacimiento_mes"),
    "GASTOS_GUARDERIA": ("GASTOS_GUARDERIA=900", "gastos_guarderia_euros"),
    # Probes the RANGE form as well as the map, because the range is the shape a
    # taxpayer reads off a certificate (a constant fee across an enrolment span)
    # and it is the half a parser could drop while still honouring bare months.
    "GASTOS_GUARDERIA_MENSUAL": ("GASTOS_GUARDERIA_MENSUAL=9-12:210;1:180", "gastos_guarderia_mensuales"),
    "NIF": ("NIF=12345678Z", "nif"),
}


def _advertised_tokens(locale: str, help_key: str) -> set[str]:
    """Tokens a given string advertises in a given locale.

    Extracted from the COPY, never from the parser source. The accepted set
    below is the parser's; deriving both from the same place would let the two
    strings agree with each other while both drifted from what is accepted.
    """
    return set(_TOKEN_RE.findall(tr(help_key, locale=locale)))


def _rendered_option_tokens() -> set[str]:
    """Tokens on the option as the CLI actually renders it to an operator.

    Read off the live ``OptionInfo`` rather than the locale catalogue, so this
    covers the whole path -- key, resolution, and the inline fallback behind it
    -- as one surface. If ``tr`` ever stopped resolving, this is what the
    operator would see, and it still has to name every accepted key.
    """
    import inspect

    from .._config._descendiente import descendiente_add

    option = inspect.signature(descendiente_add).parameters["descendiente"].default
    return set(_TOKEN_RE.findall(getattr(option, "help", "") or ""))


@pytest.mark.parametrize(("locale", "help_key"), _SURFACES)
def test_every_advertised_key_is_honoured_by_the_parser(locale: str, help_key: str) -> None:
    """No locale may advertise a token the parser drops.

    This is the Catalan-token regression: a mistranslated key parses without
    error and silently keeps the claiming default, so only round-tripping the
    advertised token through the real parser catches it.
    """
    advertised = _advertised_tokens(locale, help_key)
    assert advertised, f"{locale}/{help_key}: help advertises no KEY= tokens at all"

    unknown = advertised - set(_PROBES)
    assert not unknown, (
        f"{locale}/{help_key}: help advertises token(s) the parser does not accept: {sorted(unknown)}. "
        "Key tokens are part of the parse contract and must not be translated."
    )

    baseline = parse_descendiente_flag(_BIRTH)
    for token in sorted(advertised - {"NACIMIENTO"}):
        fragment, attribute = _PROBES[token]
        parsed = parse_descendiente_flag(f"{_BIRTH},{fragment}")
        assert getattr(parsed, attribute) != getattr(baseline, attribute), (
            f"{locale}/{help_key}: help advertises {token}= but the parser ignored it -- "
            f"{attribute} stayed at {getattr(baseline, attribute)!r}"
        )


@pytest.mark.parametrize(("locale", "help_key"), _SURFACES)
def test_every_parser_key_is_advertised(locale: str, help_key: str) -> None:
    """The discoverability half: a key the parser accepts must appear in the help.

    Three keys the parser had accepted were missing from this string, so
    the only surface an operator consults could not lead them to the facts the
    write door was refusing them for.
    """
    missing = set(_PROBES) - _advertised_tokens(locale, help_key)
    assert not missing, f"{locale}/{help_key}: parser accepts {sorted(missing)} but the help never mentions them"


def test_the_rendered_option_names_every_accepted_key() -> None:
    """The surface an operator actually reads must name every key the parser takes."""
    assert _rendered_option_tokens() == set(_PROBES)


def test_the_help_names_no_euro_figure() -> None:
    """Copy must not restate a registry ceiling.

    The Art. 58.1 and Art. 61 norma 2ª limits live as registry parameters per
    filing year. Naming one here would decouple the copy from the figure the
    engine resolves and drift the moment a revision moved it.
    """
    for locale, help_key in _SURFACES:
        help_text = tr(help_key, locale=locale)
        for figure in ("8.000", "8000", "1.800", "1800"):
            assert figure not in help_text, f"{locale}/{help_key}: help restates the registry figure {figure!r}"
