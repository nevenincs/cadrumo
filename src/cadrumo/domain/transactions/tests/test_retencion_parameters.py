"""Gates for the registry-backed RIRPF art. 95 retención rates.

The two rate figures are legal data, not Python constants. These gates pin the
chain the ``aeat-registry-authority-flow`` and
``aeat-calculation-grounding`` rules require:

    bundled BOE corpus excerpt → registry parameter → typed record → the
    inference bound the transaction model actually applies.

The expected percentages are not recomputed from anything the loader does;
they are read out of the bundled BOE corpus excerpt for RD 439/2007 art. 95
and compared against the registry parameter, so a drift in either the excerpt
or the parameter reds the gate rather than agreeing with itself.

See Also:
    :mod:`domain.transactions.retencion_parameters`
        The loader under test.
    :mod:`domain.iva.tests.test_legal_basis_rate_grounding`
        The sibling corpus → registry → substrate chain for IVA rates.
"""

from __future__ import annotations

import re
import tomllib
from decimal import Decimal

import pytest

from ....core.directory_scan import scan_directory
from ....core.resources._boundary import bundled_path
from ..retencion_parameters import (
    RirpfArt95RetencionRates,
    load_retencion_actividades_rates,
    maximum_supported_activity_retencion_rate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_GENERAL_PARAM_ID = "rirpf-art-95:retencion-actividades-profesionales-general"
_INICIO_PARAM_ID = "rirpf-art-95:retencion-actividades-profesionales-inicio"
_LEGAL_REF = "rd-439-2007:art-95"


def _parameters_toml() -> dict[str, dict[str, object]]:
    path = bundled_path("registry", "aeat", "legal", "irpf-retencion-actividades.toml")
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


def _corpus_text() -> str:
    path = bundled_path("corpus", "normatives", "html") / "rd-439-2007-art-95.html"
    raw = path.read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw.replace("\xa0", " ")))


def test_the_bundled_boe_excerpt_states_both_retencion_rates() -> None:
    """First link: the corpus excerpt carries the operative percentage strings."""
    text = _corpus_text()
    assert "15 por ciento sobre los ingresos íntegros satisfechos" in text
    assert "7 por ciento en el período impositivo de inicio de actividades" in text


def test_registry_parameters_match_the_percentages_the_excerpt_states() -> None:
    """Second link: the registry values equal the BOE percentages as fractions."""
    parameters = _parameters_toml()
    assert Decimal(str(parameters[_GENERAL_PARAM_ID]["value"])) == Decimal("15") / Decimal("100")
    assert Decimal(str(parameters[_INICIO_PARAM_ID]["value"])) == Decimal("7") / Decimal("100")


@pytest.mark.parametrize(
    "parameter_id",
    (_GENERAL_PARAM_ID, _INICIO_PARAM_ID),
    ids=("general", "inicio-actividad"),
)
def test_every_retencion_parameter_cites_its_binding_provision(parameter_id: str) -> None:
    """A regulatory value without its binding provision is ungrounded."""
    parameter = _parameters_toml()[parameter_id]
    assert parameter["evidence_tier"] == "legal_authority"
    legal_refs = parameter["legal_refs"]
    assert isinstance(legal_refs, list), "legal_refs must be a list in the parameters table"
    assert _LEGAL_REF in legal_refs


def test_the_cited_provision_resolves_in_the_bundled_legal_catalogue() -> None:
    """The cited id must exist as a legal entry with a corpus_ref."""
    legal_root = bundled_path("registry", "aeat", "legal")
    entries: dict[str, object] = {}
    for path in scan_directory(legal_root, pattern="*.toml"):
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
        legal_table = payload.get("legal")
        if isinstance(legal_table, dict):
            entries.update(legal_table)
    entry = entries.get(_LEGAL_REF)
    assert isinstance(entry, dict), f"{_LEGAL_REF} is not declared in the legal catalogue"
    assert entry["corpus_ref"] == "corpus/normatives/html/rd-439-2007-art-95.html#a95"


def test_loader_returns_the_registry_values_as_a_typed_record() -> None:
    """Third link: the typed record carries exactly the committed parameters."""
    parameters = _parameters_toml()
    rates = load_retencion_actividades_rates()

    assert isinstance(rates, RirpfArt95RetencionRates)
    assert rates.general_rate == Decimal(str(parameters[_GENERAL_PARAM_ID]["value"]))
    assert rates.inicio_actividad_rate == Decimal(str(parameters[_INICIO_PARAM_ID]["value"]))


def test_the_inference_bound_is_the_general_rate() -> None:
    """Fourth link: the bound the transaction model applies is the registry rate.

    The inicio-de-actividades rate is lower, so the general rate is the correct
    upper bound for a bounded inference that must not reject a legitimate 15 %
    withholding.
    """
    rates = load_retencion_actividades_rates()
    assert maximum_supported_activity_retencion_rate() == rates.general_rate
    assert rates.inicio_actividad_rate < rates.general_rate


def test_no_feature_module_redeclares_the_retencion_rates_as_literals() -> None:
    """The literal this loader replaced must not reappear anywhere in the tree.

    ``aeat-registry-authority-flow`` bars inlined regulatory values; the retired
    ``_MAX_SUPPORTED_ACTIVITY_WITHHOLDING`` ``_RATE`` constant is the specific
    regression this guards.

    The retired name is assembled from fragments rather than written out, so
    this module does not match its own scan and the gate needs no self-exempting
    allowlist — an allowlist is how a scan quietly stops covering the thing it
    was written for.
    """
    retired_literal = "_MAX_SUPPORTED_ACTIVITY" + "_WITHHOLDING_RATE"
    package_root = bundled_path().parent
    offenders = [
        str(path.relative_to(package_root))
        for path in scan_directory(package_root, pattern="*.py", recursive=True)
        if retired_literal in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"retired retención-rate literal reintroduced in: {offenders}"
