"""Gates for the registry-backed LIRPF art. 101.2 administrador retención rates.

The three figures (35 %, 19 %, the 100.000 € INCN threshold) are legal data,
not Python constants. These gates pin the chain the
``aeat-registry-authority-flow`` and ``aeat-calculation-grounding`` rules
require:

    bundled BOE corpus excerpt -> registry parameter -> typed record -> the
    rate set the statutory-rate advisory actually compares withheld amounts
    against.

The expected figures are not recomputed from anything the loader does; they
are read out of the bundled BOE corpus excerpts for LIRPF art. 101 and RIRPF
art. 80 and compared against the registry parameters, so a drift in either the
excerpt or the parameter reds the gate rather than agreeing with itself.

See Also:
    :mod:`domain.transactions.retencion_parameters`
        The loader under test.
    :mod:`domain.transactions.tests.test_retencion_parameters`
        The sibling RIRPF art. 95 gate this module mirrors.
"""

from __future__ import annotations

import re
import tomllib
from decimal import Decimal

import pytest

from ....core.directory_scan import scan_directory
from ....core.resources._boundary import bundled_path
from ..retencion_parameters import (
    AdministradorRetencionRates,
    administrador_retencion_legal_refs,
    load_administrador_retencion_rates,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_GENERAL_PARAM_ID = "lirpf-art-101:retencion-administrador-general"
_REDUCIDA_PARAM_ID = "lirpf-art-101:retencion-administrador-reducida"
_UMBRAL_PARAM_ID = "lirpf-art-101:retencion-administrador-incn-umbral-eur"
_LIRPF_REF = "ley-35-2006:art-101"
_RIRPF_REF = "rd-439-2007:art-80"


def _parameters_toml() -> dict[str, dict[str, object]]:
    path = bundled_path("registry", "aeat", "legal", "irpf-retencion-administradores.toml")
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    parameters = payload["parameters"]
    assert isinstance(parameters, dict)
    typed_parameters: dict[str, dict[str, object]] = {}
    for key, value in parameters.items():
        assert isinstance(key, str)
        assert isinstance(value, dict)
        typed_value: dict[str, object] = {}
        for field_name, field_value in value.items():
            assert isinstance(field_name, str)
            typed_value[field_name] = field_value
        typed_parameters[key] = typed_value
    return typed_parameters


def _corpus_text(filename: str) -> str:
    path = bundled_path("corpus", "normatives", "html") / filename
    raw = path.read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw.replace("\xa0", " ")))


def test_the_bundled_lirpf_excerpt_states_every_administrador_figure() -> None:
    """First link: the LIRPF art. 101 excerpt carries all three operative figures."""
    text = _corpus_text("ley-35-2006-art-101.html")
    assert "35 por ciento" in text
    assert "19 por ciento" in text
    assert "100.000 euros" in text


def test_the_bundled_rirpf_excerpt_states_every_administrador_figure() -> None:
    """The RIRPF art. 80 excerpt states the same three figures, developing the LIRPF rate."""
    text = _corpus_text("rd-439-2007-art-80.html")
    assert "35 por ciento" in text
    assert "19 por ciento" in text
    assert "100.000 euros" in text


def test_registry_parameters_match_the_percentages_the_excerpts_state() -> None:
    """Second link: the registry values equal the BOE percentages as fractions."""
    parameters = _parameters_toml()
    assert Decimal(str(parameters[_GENERAL_PARAM_ID]["value"])) == Decimal("35") / Decimal("100")
    assert Decimal(str(parameters[_REDUCIDA_PARAM_ID]["value"])) == Decimal("19") / Decimal("100")
    assert Decimal(str(parameters[_UMBRAL_PARAM_ID]["value"])) == Decimal("100000")


@pytest.mark.parametrize(
    "parameter_id",
    (_GENERAL_PARAM_ID, _REDUCIDA_PARAM_ID, _UMBRAL_PARAM_ID),
    ids=("general", "reducida", "incn-umbral"),
)
def test_every_administrador_parameter_cites_both_binding_provisions(parameter_id: str) -> None:
    """A regulatory value without its binding provision is ungrounded.

    Both the LIRPF (the establishing law) and the RIRPF (the developing
    reglamento) are cited, mirroring the pairing the advisory's message already
    names.
    """
    parameter = _parameters_toml()[parameter_id]
    assert parameter["evidence_tier"] == "legal_authority"
    legal_refs = parameter["legal_refs"]
    assert isinstance(legal_refs, list), "legal_refs must be a list in the parameters table"
    assert _LIRPF_REF in legal_refs
    assert _RIRPF_REF in legal_refs


def test_both_cited_provisions_resolve_in_the_bundled_legal_catalogue() -> None:
    """Both cited ids must exist as legal entries with a corpus_ref."""
    legal_root = bundled_path("registry", "aeat", "legal")
    entries: dict[str, object] = {}
    for path in scan_directory(legal_root, pattern="*.toml"):
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
        legal_table = payload.get("legal")
        if isinstance(legal_table, dict):
            entries.update(legal_table)

    lirpf_entry = entries.get(_LIRPF_REF)
    assert isinstance(lirpf_entry, dict), f"{_LIRPF_REF} is not declared in the legal catalogue"
    assert lirpf_entry["corpus_ref"] == "corpus/normatives/html/ley-35-2006-art-101.html#a101"

    rirpf_entry = entries.get(_RIRPF_REF)
    assert isinstance(rirpf_entry, dict), f"{_RIRPF_REF} is not declared in the legal catalogue"
    assert rirpf_entry["corpus_ref"] == "corpus/normatives/html/rd-439-2007-art-80.html#a80"


def test_loader_returns_the_registry_values_as_a_typed_record() -> None:
    """Third link: the typed record carries exactly the committed parameters."""
    parameters = _parameters_toml()
    rates = load_administrador_retencion_rates()

    assert isinstance(rates, AdministradorRetencionRates)
    assert rates.general_rate == Decimal(str(parameters[_GENERAL_PARAM_ID]["value"]))
    assert rates.reduced_rate == Decimal(str(parameters[_REDUCIDA_PARAM_ID]["value"]))
    assert rates.reduced_incn_threshold_eur == Decimal(str(parameters[_UMBRAL_PARAM_ID]["value"]))


def test_the_reduced_rate_is_strictly_below_the_general_rate() -> None:
    """A sanity ordering: the INCN-conditioned rate is the LOWER of the two."""
    rates = load_administrador_retencion_rates()
    assert rates.reduced_rate < rates.general_rate


def test_administrador_legal_refs_names_both_provisions() -> None:
    """Fourth link: the grounding function the advisory calls names both refs."""
    refs = administrador_retencion_legal_refs()
    assert _LIRPF_REF in refs
    assert _RIRPF_REF in refs


def test_no_feature_module_redeclares_the_administrador_rates_as_literals() -> None:
    """The literals this loader replaced must not reappear anywhere in the tree.

    ``aeat-registry-authority-flow`` bars inlined regulatory values; the
    retired ``core.aggregation`` constants are the specific regression this
    guards.

    The retired names are assembled from fragments rather than written out, so
    this module does not match its own scan and the gate needs no
    self-exempting allowlist -- an allowlist is how a scan quietly stops
    covering the thing it was written for.
    """
    # Whole-identifier boundaries: a bare substring match would false-fire on
    # the still-live ``ADMINISTRADOR_RETENCION_RATE_SOURCE_KIND`` diagnostic
    # kind, which legitimately shares the retired constant's prefix.
    retired_patterns = tuple(
        re.compile(r"(?<![A-Za-z0-9_])" + re.escape(literal) + r"(?![A-Za-z0-9_])")
        for literal in (
            "ADMINISTRADOR_RETENCION" + "_RATE",
            "ADMINISTRADOR_RETENCION_REDUCED" + "_RATE",
            "ADMINISTRADOR_RETENCION_REDUCED_INCN" + "_THRESHOLD_EUR",
        )
    )
    package_root = bundled_path().parent
    offenders: list[str] = []
    for path in scan_directory(package_root, pattern="*.py", recursive=True):
        text = path.read_text(encoding="utf-8")
        offenders.extend(str(path.relative_to(package_root)) for pattern in retired_patterns if pattern.search(text))
    assert offenders == [], f"retired administrador retención-rate literal reintroduced in: {offenders}"
