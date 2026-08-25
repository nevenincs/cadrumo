"""Absence gate: no aggregation refusal reaches the operator as authored English.

Every refusal this package raises must carry a REGISTERED locale key plus
machine facts. Asserting the key and the context alone cannot hold that line.
Message resolution prefers ``translated_message``, so an English sentence
passed positionally beside a registered key stays invisible to every
key-and-context assertion in the suite -- while
:meth:`cadrumo.core.errors.CadrumoError.__init__` resolves ``str(exc)`` as
``message or translated_message``, so the positional sentence is what reaches
tracebacks, structured logs and every boundary that renders the exception
directly, in all four locales.

Two defect shapes are gated here, because both were live in this package:

* the *positional-beside-a-key* shape, which nine service-contract refusals
  carried;
* the *prose-as-the-key* shape, where the authored sentence was passed to
  ``t(...)`` and so BECAME the translation key. python-i18n humanises an
  unresolvable key rather than failing, so those refusals rendered
  English-derived text in Spanish, Catalan and Hungarian sessions while
  looking, at the call site, exactly like a migrated producer.

The runtime half of the gate is the ABSENCE assertion ``str(exc) == <key>``.
The static half walks the package's own source with :mod:`ast`, so a refusal
added later cannot reintroduce either shape unnoticed.

Real registry, real catalogues, real ``Settings`` through the real override
seam; no doubles, no monkeypatching.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory
from ....core.config import override_settings
from ....core.i18n import tr
from ..errors import AggregationConfigError, AggregationValidationError, t

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: A registered translation key: dotted, lowercase, no whitespace.
_REGISTERED_KEY = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent

#: The message-bearing keywords a producer may use to supply refusal text.
_MESSAGE_KEYWORDS = frozenset({"message", "translated_message"})

#: Wrappers that mark a string as a translation key rather than prose.
_KEY_WRAPPERS = frozenset({"t", "tr", "Translatable"})

#: Every refusal key the migration moved, by owning module. A key that stops
#: resolving -- or a module renamed out from under the gate -- must fail loudly
#: rather than let the roster shrink silently.
_MIGRATED_KEYS: tuple[str, ...] = (
    "aggregation.iva_ledger.errors.differentiated_sector_inactive_for_filing_year",
    "aggregation.iva_ledger.errors.differentiated_sector_without_filing_year_entry",
    "aggregation.iva_ledger.errors.differentiated_sector_without_provisional_percentage",
    "aggregation.iva_ledger.errors.injected_repositories_missing_bienes_inversion_authority",
    "aggregation.iva_ledger.errors.input_facts_missing_deduction_authority",
    "aggregation.iva_ledger.errors.investment_observations_missing_bienes_inversion_authority",
    "aggregation.iva_ledger.errors.output_facts_carry_deduction_authority",
    "aggregation.iva_ledger.errors.rectification_consumed_more_than_once",
    "aggregation.iva_ledger.errors.sectorized_apportionment_duplicate_sectors",
    "aggregation.iva_ledger.errors.sectorized_especial_missing_input_classification",
    "aggregation.iva_ledger.errors.sectorized_input_inactive_sector",
    "aggregation.iva_ledger.errors.sectorized_input_missing_sector_identity",
    "aggregation.iva_ledger.errors.sectorized_input_unknown_sector",
    "aggregation.invoice_retencion.errors.euro_figures_unavailable_after_defect_sweep",
    "aggregation.invoice_retencion.errors.perceptor_tax_id_unavailable_after_defect_sweep",
    "aggregation.invoice_retencion.errors.projection_defects_repeat",
    "aggregation.invoice_retencion.errors.projection_outcome_ambiguous",
    "aggregation.m303_arrivals.errors.prorrata_register_contradictory_transition_evidence",
    "aggregation.m303_arrivals.errors.prorrata_register_incomplete_current_year_declaration",
    "aggregation.m303_arrivals.errors.prorrata_revocacion_without_prior_year_especial",
    "aggregation.m303_arrivals.errors.prorrata_transition_contradictory_evidence",
    "aggregation.m303_arrivals.errors.prorrata_transition_entry_without_evidence",
    "aggregation.m303_arrivals.errors.prorrata_transition_evidence_without_declared_transition",
    "aggregation.m303_arrivals.errors.prorrata_transition_evidence_wrong_filing_year",
    "aggregation.m303_arrivals.errors.prorrata_transition_missing_register_evidence",
    "aggregation.m303_arrivals.errors.prorrata_transition_not_applicable_for_period",
    "aggregation.m303_arrivals.errors.recipient_fact_disagrees_with_ledger_evidence",
    "aggregation.m303_arrivals.errors.supplier_regime_aggregation_period_mismatch",
    "aggregation.m303_arrivals.errors.supplier_regime_blank_ledger_identity",
    "aggregation.m303_arrivals.errors.supplier_regime_duplicate_ledger_evidence",
    "aggregation.m303_arrivals.errors.supplier_regime_observations_outside_period",
    "aggregation.oss_ioss.errors.iva_amount_mismatches_destination_rate",
    "aggregation.service.errors.envelope_modelo_mismatch",
    "aggregation.service.errors.envelope_period_mismatch",
    "aggregation.service.errors.envelope_provider_payload_mismatch",
    "aggregation.service.errors.observations_mismatch",
    "aggregation.service.errors.per_modelo_modelos_not_unique",
    "aggregation.service.errors.per_modelo_providers_not_unique",
    "aggregation.service.errors.provider_modelos_not_unique",
    "aggregation.service.errors.result_source_kinds_not_unique",
    "aggregation.service.errors.source_kinds_mismatch",
)

#: Modules whose refusals this gate covers. Anchored so a rename cannot let the
#: static sweep pass vacuously over a package that no longer contains them.
_COVERED_MODULES: tuple[str, ...] = (
    "errors.py",
    "_invoice_retencion.py",
    "_iva_ledger.py",
    "_m303_arrivals.py",
    "_oss_ioss.py",
    "_service.py",
)


def _literal_text(node: ast.expr) -> str | None:
    """Return the authored literal a message expression resolves to, if any."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):
        return "".join(
            part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else "{}"
            for part in node.values
        )
    if isinstance(node, ast.Call):
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name in _KEY_WRAPPERS and node.args:
            return _literal_text(node.args[0])
    return None


def _production_modules() -> tuple[Path, ...]:
    """Return every non-test module in the aggregation package."""
    return tuple(
        path
        for path in scan_directory(_PACKAGE_ROOT, pattern="*.py", recursive=True)
        if "tests" not in path.relative_to(_PACKAGE_ROOT).parts
    )


def _authored_prose_sites() -> tuple[str, ...]:
    """Return every refusal site whose message text is not a registered key.

    Only producers carrying a translation channel are examined: a construction
    is an offender when the text it routes to ``str(exc)`` or to
    ``translated_message`` is a sentence rather than a dotted key.
    """
    offenders: list[str] = []
    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if not name or not name.endswith("Error"):
                continue
            keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg in _MESSAGE_KEYWORDS}
            carries_key_channel = "translated_message" in keywords or (
                bool(node.args)
                and isinstance(node.args[0], ast.Call)
                and getattr(node.args[0].func, "id", None) in _KEY_WRAPPERS
            )
            if not carries_key_channel:
                continue
            candidates = [node.args[0]] if node.args else []
            candidates.extend(keywords.values())
            for candidate in candidates:
                text = _literal_text(candidate)
                if text is None or _REGISTERED_KEY.match(text.strip()):
                    continue
                offenders.append(f"{path.name}:{node.lineno} {name} -> {text!r}")
    return tuple(offenders)


def test_no_aggregation_refusal_authors_an_english_sentence() -> None:
    """No refusal in the package routes a sentence to str(exc) or to the key."""
    offenders = _authored_prose_sites()
    assert not offenders, "aggregation refusals carrying authored prose:\n" + "\n".join(offenders)


def test_the_static_sweep_actually_reaches_the_covered_modules() -> None:
    """A rename must not let the sweep pass over an empty package."""
    scanned = {path.name for path in _production_modules()}
    missing = sorted(set(_COVERED_MODULES) - scanned)
    assert not missing, f"gate no longer reaches its own subject modules: {missing}"


@pytest.mark.parametrize("key", _MIGRATED_KEYS)
def test_every_migrated_refusal_key_resolves_to_real_text(key: str) -> None:
    """A key that never landed in a catalogue must fail, not render humanised."""
    humanised = key.rsplit(".", 1)[-1].replace("_", " ").capitalize()
    for language in ("en", "es", "ca", "hu"):
        with override_settings(cadrumo_output_language=language):
            rendered = tr(key)
        assert rendered != key, f"{key} is unauthored in {language}"
        assert rendered != humanised, f"{key} falls back to a humanised key in {language}"
        assert rendered.strip()


def test_config_refusal_renders_as_its_key_only() -> None:
    """The service-contract refusal degrades to its key, carrying no sentence."""
    error = AggregationConfigError(
        translated_message="aggregation.service.errors.provider_modelos_not_unique",
    )

    assert str(error) == "aggregation.service.errors.provider_modelos_not_unique"


def test_validation_refusal_renders_as_its_key_only() -> None:
    """A ``t(...)``-keyed refusal degrades to its key, carrying no sentence."""
    error = AggregationValidationError(
        t("aggregation.m303_arrivals.errors.supplier_regime_blank_ledger_identity"),
        context={"source_ledger_id_count": 2},
    )

    assert str(error) == "aggregation.m303_arrivals.errors.supplier_regime_blank_ledger_identity"
