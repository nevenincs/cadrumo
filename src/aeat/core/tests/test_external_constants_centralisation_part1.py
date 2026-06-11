"""Centralisation contract tests (part 1): MIME types, currency, classified-by-manual, and threshold constants."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# contract — BINARY_MIME_TYPE centralisation tests
# ---------------------------------------------------------------------------


def test_binary_mime_type_value() -> None:
    """``BINARY_MIME_TYPE`` equals the IANA-registered opaque-binary MIME type."""

    from ..external_constants import BINARY_MIME_TYPE

    assert BINARY_MIME_TYPE == "application/octet-stream"


def test_google_drive_reads_binary_mime_from_external_constants() -> None:
    """The Google Drive adapter imports ``BINARY_MIME_TYPE`` rather than a local literal."""

    import importlib
    import importlib.util

    from ..external_constants import BINARY_MIME_TYPE

    spec = importlib.util.find_spec("aeat.adapters.outbound.storage._google_drive")
    assert spec is not None, "_google_drive module not found"
    mod = importlib.import_module("aeat.adapters.outbound.storage._google_drive")

    # The module-level alias resolves to the canonical constant.
    assert mod._BINARY_MIME_TYPE is BINARY_MIME_TYPE


# ---------------------------------------------------------------------------
# contract / contract — DEFAULT_CURRENCY centralisation tests
# ---------------------------------------------------------------------------


def test_default_currency_value() -> None:
    """``DEFAULT_CURRENCY`` equals the ISO 4217 Euro code."""

    from ..external_constants import DEFAULT_CURRENCY

    assert DEFAULT_CURRENCY == "EUR"


def test_default_currency_is_final_str() -> None:
    """``DEFAULT_CURRENCY`` is a ``str`` instance (typed ``Final[str]``)."""

    from ..external_constants import DEFAULT_CURRENCY

    assert isinstance(DEFAULT_CURRENCY, str)


def test_ledger_transaction_command_reads_currency_from_external_constants() -> None:
    """The manual ledger transaction command default currency comes from ``DEFAULT_CURRENCY``."""

    # Construct with no explicit currency — the field default must resolve to DEFAULT_CURRENCY.
    # We verify by inspecting that the module imports DEFAULT_CURRENCY (not a local literal).
    from ...application.ledger import _models as _models_mod
    from ...application.ledger._models import ManualLedgerTransactionCommand
    from ..external_constants import DEFAULT_CURRENCY

    assert hasattr(_models_mod, "DEFAULT_CURRENCY"), (
        "_models module must import DEFAULT_CURRENCY from external_constants"
    )
    assert _models_mod.DEFAULT_CURRENCY is DEFAULT_CURRENCY

    # Also verify the field default is not a hardcoded literal in the model schema.
    schema = ManualLedgerTransactionCommand.model_json_schema()
    props = schema.get("properties", {})
    currency_prop = props.get("currency", {})
    assert currency_prop.get("default") == DEFAULT_CURRENCY


def test_currency_service_reads_native_eur_from_external_constants() -> None:
    """The currency normalisation service uses ``DEFAULT_CURRENCY`` for native EUR check."""

    from ...domain.currency import _service as _service_mod
    from ..external_constants import DEFAULT_CURRENCY

    assert hasattr(_service_mod, "DEFAULT_CURRENCY"), (
        "_service module must import DEFAULT_CURRENCY from external_constants"
    )
    assert _service_mod.DEFAULT_CURRENCY is DEFAULT_CURRENCY


def test_aggregation_predicates_read_currency_from_external_constants() -> None:
    """The aggregation currency predicate uses ``DEFAULT_CURRENCY``, not a local literal."""

    from ...application.aggregation import _currency_predicates as _pred_mod
    from ..external_constants import DEFAULT_CURRENCY

    assert hasattr(_pred_mod, "DEFAULT_CURRENCY"), (
        "_currency_predicates must import DEFAULT_CURRENCY from external_constants"
    )
    assert _pred_mod.DEFAULT_CURRENCY is DEFAULT_CURRENCY


def test_config_financial_base_currency_default_equals_default_currency() -> None:
    """``Settings.financial_base_currency`` default equals ``DEFAULT_CURRENCY``."""

    from ..external_constants import DEFAULT_CURRENCY

    settings = Settings()
    assert settings.financial_base_currency == DEFAULT_CURRENCY


def test_blob_store_put_default_content_type_reads_from_external_constants() -> None:
    """``EncryptedBlobStore.put`` default ``content_type`` is bound to ``BINARY_MIME_TYPE``."""

    import inspect

    from ...adapters.persistence.storage.blob_store._blob_store import EncryptedBlobStore
    from ..external_constants import BINARY_MIME_TYPE

    sig = inspect.signature(EncryptedBlobStore.put)
    default = sig.parameters["content_type"].default
    assert default == BINARY_MIME_TYPE


def test_declarations_filed_artefact_uses_binary_mime_constant() -> None:
    """``FiledDeclaracionArtefact`` content_type field no longer carries a raw literal.

    We assert that the module imports ``BINARY_MIME_TYPE`` from
    ``aeat.core.external_constants`` and that the imported value equals the
    expected MIME type, giving a transitive identity guarantee without
    executing the live AEAT browser path.
    """

    import importlib

    from ..external_constants import BINARY_MIME_TYPE

    mod = importlib.import_module("aeat.adapters.outbound.aeat.sede._declarations")

    # The module must expose the constant under the local alias used at the call site.
    assert mod._BINARY_MIME_TYPE is BINARY_MIME_TYPE
    assert mod._BINARY_MIME_TYPE == "application/octet-stream"


# ---------------------------------------------------------------------------
# contract / contract / contract — CLASSIFIED_BY_MANUAL single-source-of-truth tests
# ---------------------------------------------------------------------------


def test_classified_by_manual_value() -> None:
    """``CLASSIFIED_BY_MANUAL`` equals the sentinel stored in persisted records."""

    from ..external_constants import CLASSIFIED_BY_MANUAL

    assert CLASSIFIED_BY_MANUAL == "manual"


def test_classified_by_manual_is_final_str() -> None:
    """``CLASSIFIED_BY_MANUAL`` is a ``str`` instance (typed ``Final[str]``)."""

    from ..external_constants import CLASSIFIED_BY_MANUAL

    assert isinstance(CLASSIFIED_BY_MANUAL, str)


def test_application_ledger_imports_classified_by_manual_from_core() -> None:
    """The application ledger public surface re-exports ``CLASSIFIED_BY_MANUAL`` from core.

    The application layer must not define a local copy; it must import the
    canonical constant from ``aeat.core.external_constants`` and expose it
    through the package ``__init__``.
    """

    import importlib

    from ..external_constants import CLASSIFIED_BY_MANUAL

    ledger_init = importlib.import_module("aeat.application.ledger")

    # The public surface exposes the constant and it is the same object.
    assert hasattr(ledger_init, "CLASSIFIED_BY_MANUAL"), "aeat.application.ledger must expose CLASSIFIED_BY_MANUAL"
    assert ledger_init.CLASSIFIED_BY_MANUAL is CLASSIFIED_BY_MANUAL


def test_application_ledger_models_does_not_define_classified_by_manual_locally() -> None:
    """``_models.py`` must not carry a local definition of ``CLASSIFIED_BY_MANUAL``.

    It imports the constant from ``aeat.core.external_constants``; the
    imported name must be identical to the core constant (not a shadow).
    """

    import importlib

    from ..external_constants import CLASSIFIED_BY_MANUAL

    models_mod = importlib.import_module("aeat.application.ledger._models")

    # The module still exposes the constant (via import), and it is the same object.
    assert hasattr(models_mod, "CLASSIFIED_BY_MANUAL"), "_models must import CLASSIFIED_BY_MANUAL from core"
    assert models_mod.CLASSIFIED_BY_MANUAL is CLASSIFIED_BY_MANUAL


def test_domain_transactions_service_imports_classified_by_manual_from_core() -> None:
    """The domain service must not shadow ``CLASSIFIED_BY_MANUAL`` with a local string literal.

    The constant must be imported from ``aeat.core.external_constants`` so
    that the domain layer reads a single authoritative value.
    """

    import importlib

    from ..external_constants import CLASSIFIED_BY_MANUAL

    service_mod = importlib.import_module("aeat.domain.transactions._service")

    # The domain service module must import the constant from core (not define its own).
    assert hasattr(service_mod, "CLASSIFIED_BY_MANUAL"), (
        "_service must import CLASSIFIED_BY_MANUAL from aeat.core.external_constants"
    )
    assert service_mod.CLASSIFIED_BY_MANUAL is CLASSIFIED_BY_MANUAL


def test_no_local_classified_by_manual_shadow_in_application_or_domain() -> None:
    """No production file in application/ or domain/ may define a local ``classified_by``
    sentinel by assigning the bare string ``"manual"`` to a module-level variable whose
    name contains ``classified_by`` or ``manual_classified``.

    This is the regression guard against the pattern removed in contract/contract:
    ``_MANUAL_CLASSIFIED_BY = "manual"`` or ``CLASSIFIED_BY_MANUAL = "manual"`` defined
    locally instead of imported from ``aeat.core.external_constants``.
    """

    repo_root = Path(__file__).parents[4]
    search_roots = (
        repo_root / "src/aeat/application",
        repo_root / "src/aeat/domain",
    )

    # Names that signal a classified_by sentinel re-definition.
    _SENTINEL_NAME_FRAGMENTS = ("classified_by", "manual_classified")

    offenders: list[str] = []
    for search_root in search_roots:
        for py_file in search_root.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                # Look for module-level or function-level simple assignments:
                # TARGET = "manual"
                if not isinstance(node, ast.Assign):
                    continue
                value = node.value
                if not isinstance(value, ast.Constant) or value.value != "manual":
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    name_lower = target.id.lower()
                    if any(frag in name_lower for frag in _SENTINEL_NAME_FRAGMENTS):
                        offenders.append(
                            f"{py_file.relative_to(repo_root)}:{node.lineno}: "
                            f"local classified_by sentinel '{target.id} = \"manual\"'; "
                            f"import CLASSIFIED_BY_MANUAL from aeat.core.external_constants",
                        )

    assert offenders == [], (
        "Local classified_by manual sentinels found; "
        "import CLASSIFIED_BY_MANUAL from aeat.core.external_constants instead:\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# contract / contract / contract — JSON_MIME_TYPE and CSV_MIME_TYPE centralisation tests
# ---------------------------------------------------------------------------


def test_json_mime_type_value() -> None:
    """``JSON_MIME_TYPE`` equals the IANA-registered JSON MIME type."""

    from ..external_constants import JSON_MIME_TYPE

    assert JSON_MIME_TYPE == "application/json"


def test_csv_mime_type_value() -> None:
    """``CSV_MIME_TYPE`` equals the IANA-registered CSV MIME type."""

    from ..external_constants import CSV_MIME_TYPE

    assert CSV_MIME_TYPE == "text/csv"


def test_jsonl_mime_type_value() -> None:
    """``JSONL_MIME_TYPE`` equals the newline-delimited JSON MIME type."""

    from ..external_constants import JSONL_MIME_TYPE

    assert JSONL_MIME_TYPE == "application/x-ndjson"


def test_xlsx_mime_type_value() -> None:
    """``XLSX_MIME_TYPE`` equals the Office Open XML workbook MIME type."""

    from ..external_constants import XLSX_MIME_TYPE

    assert XLSX_MIME_TYPE == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_json_mime_type_is_final_str() -> None:
    """``JSON_MIME_TYPE`` is a ``str`` instance (typed ``Final[str]``)."""

    from ..external_constants import JSON_MIME_TYPE

    assert isinstance(JSON_MIME_TYPE, str)


def test_csv_mime_type_is_final_str() -> None:
    """``CSV_MIME_TYPE`` is a ``str`` instance (typed ``Final[str]``)."""

    from ..external_constants import CSV_MIME_TYPE

    assert isinstance(CSV_MIME_TYPE, str)


def test_jsonl_mime_type_is_final_str() -> None:
    """``JSONL_MIME_TYPE`` is a ``str`` instance (typed ``Final[str]``)."""

    from ..external_constants import JSONL_MIME_TYPE

    assert isinstance(JSONL_MIME_TYPE, str)


def test_xlsx_mime_type_is_final_str() -> None:
    """``XLSX_MIME_TYPE`` is a ``str`` instance (typed ``Final[str]``)."""

    from ..external_constants import XLSX_MIME_TYPE

    assert isinstance(XLSX_MIME_TYPE, str)


def test_declarations_uses_json_mime_constant() -> None:
    """``_declarations.py`` imports ``JSON_MIME_TYPE`` rather than a bare literal.

    The module must expose ``_JSON_MIME_TYPE`` and its value must equal
    ``JSON_MIME_TYPE`` from ``aeat.core.external_constants``, giving an
    identity guarantee without executing the live AEAT browser path.
    """

    import importlib

    from ..external_constants import JSON_MIME_TYPE

    mod = importlib.import_module("aeat.adapters.outbound.aeat.sede._declarations")

    assert hasattr(mod, "_JSON_MIME_TYPE"), (
        "_declarations must import JSON_MIME_TYPE from aeat.core.external_constants under the alias _JSON_MIME_TYPE"
    )
    assert mod._JSON_MIME_TYPE is JSON_MIME_TYPE
    assert mod._JSON_MIME_TYPE == "application/json"


def test_tabular_export_uses_csv_mime_constant() -> None:
    """``_tabular.py`` imports ``CSV_MIME_TYPE`` rather than a bare ``"text/csv"`` literal.

    The module must expose ``_CSV_MIME_TYPE`` and its value must equal
    ``CSV_MIME_TYPE`` from ``aeat.core.external_constants``.
    """

    import importlib

    from ..external_constants import CSV_MIME_TYPE

    mod = importlib.import_module("aeat.application.export._tabular")

    assert hasattr(mod, "_CSV_MIME_TYPE"), (
        "_tabular must import CSV_MIME_TYPE from aeat.core.external_constants under the alias _CSV_MIME_TYPE"
    )
    assert mod._CSV_MIME_TYPE is CSV_MIME_TYPE
    assert mod._CSV_MIME_TYPE == "text/csv"


def test_tabular_export_uses_jsonl_and_xlsx_mime_constants() -> None:
    """``_tabular.py`` imports JSONL/XLSX MIME constants from core."""

    import importlib

    from ..external_constants import JSONL_MIME_TYPE, XLSX_MIME_TYPE

    mod = importlib.import_module("aeat.application.export._tabular")

    assert hasattr(mod, "_JSONL_MIME_TYPE"), (
        "_tabular must import JSONL_MIME_TYPE from aeat.core.external_constants under the alias _JSONL_MIME_TYPE"
    )
    assert hasattr(mod, "_XLSX_MIME_TYPE"), (
        "_tabular must import XLSX_MIME_TYPE from aeat.core.external_constants under the alias _XLSX_MIME_TYPE"
    )
    assert mod._JSONL_MIME_TYPE is JSONL_MIME_TYPE
    assert mod._XLSX_MIME_TYPE is XLSX_MIME_TYPE


def test_no_bare_json_mime_literal_in_declarations() -> None:
    """No bare ``"application/json"`` literal in ``_declarations.py`` argument positions.

    Anti-tautology: parses the real AST so any future re-introduction of
    the literal triggers immediate failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/adapters/outbound/aeat/sede/_declarations.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or node.value != "application/json":
            continue
        offenders.append(f"_declarations.py:{node.lineno}: bare 'application/json' literal")

    assert offenders == [], "Bare 'application/json' literals found; use _JSON_MIME_TYPE instead:\n" + "\n".join(
        offenders,
    )


# ---------------------------------------------------------------------------
# contract — M347_THRESHOLD_EUR centralisation tests
# ---------------------------------------------------------------------------


def test_m347_threshold_eur_value() -> None:
    """``M347_THRESHOLD_EUR`` equals €3,005.06 per RD 1065/2007 art. 31.1."""

    from decimal import Decimal

    from ..external_constants import M347_THRESHOLD_EUR

    assert Decimal("3005.06") == M347_THRESHOLD_EUR


def test_m347_threshold_eur_is_final_decimal() -> None:
    """``M347_THRESHOLD_EUR`` is a ``Decimal`` instance (typed ``Final[Decimal]``)."""

    from decimal import Decimal

    from ..external_constants import M347_THRESHOLD_EUR

    assert isinstance(M347_THRESHOLD_EUR, Decimal)


def test_counterpart_aggregator_reads_threshold_from_external_constants() -> None:
    """``_counterpart.py`` must import ``M347_THRESHOLD_EUR`` from core, not define it locally."""

    import importlib

    from ..external_constants import M347_THRESHOLD_EUR

    mod = importlib.import_module("aeat.application.aggregation._counterpart")

    assert hasattr(mod, "M347_THRESHOLD_EUR"), (
        "_counterpart must import M347_THRESHOLD_EUR from aeat.core.external_constants"
    )
    assert mod.M347_THRESHOLD_EUR is M347_THRESHOLD_EUR


def test_no_bare_threshold_347_literal_in_counterpart() -> None:
    """No bare ``Decimal("3005.06")`` threshold literal in ``_counterpart.py``.

    Anti-tautology: parses the real AST so any future re-introduction of the
    local constant triggers immediate failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/aggregation/_counterpart.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        # Flag any Decimal("3005.06") call-expression literal in the file.
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "3005.06":
            offenders.append(f"_counterpart.py:{node.lineno}: bare Decimal('3005.06'); use M347_THRESHOLD_EUR")

    assert offenders == [], (
        "Local M347 threshold literals found; import M347_THRESHOLD_EUR from core instead:\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# contract — MODELO_720_REPORTING_THRESHOLD_EUR centralisation tests
# ---------------------------------------------------------------------------


def test_modelo_720_reporting_threshold_eur_value() -> None:
    """``MODELO_720_REPORTING_THRESHOLD_EUR`` equals €50,000.00 per AEAT instrucciones."""

    from decimal import Decimal

    from ..external_constants import MODELO_720_REPORTING_THRESHOLD_EUR

    assert Decimal("50000.00") == MODELO_720_REPORTING_THRESHOLD_EUR


def test_modelo_720_reporting_threshold_eur_is_final_decimal() -> None:
    """``MODELO_720_REPORTING_THRESHOLD_EUR`` is a ``Decimal`` instance."""

    from decimal import Decimal

    from ..external_constants import MODELO_720_REPORTING_THRESHOLD_EUR

    assert isinstance(MODELO_720_REPORTING_THRESHOLD_EUR, Decimal)


def test_foreign_assets_aggregator_reads_threshold_from_external_constants() -> None:
    """``_foreign_assets.py`` must import ``MODELO_720_REPORTING_THRESHOLD_EUR`` from core."""

    import importlib

    from ..external_constants import MODELO_720_REPORTING_THRESHOLD_EUR

    mod = importlib.import_module("aeat.application.aggregation._foreign_assets")

    assert hasattr(mod, "MODELO_720_REPORTING_THRESHOLD_EUR"), (
        "_foreign_assets must import MODELO_720_REPORTING_THRESHOLD_EUR from aeat.core.external_constants"
    )
    assert mod.MODELO_720_REPORTING_THRESHOLD_EUR is MODELO_720_REPORTING_THRESHOLD_EUR


def test_no_bare_threshold_720_literal_in_foreign_assets() -> None:
    """No bare ``Decimal("50000.00")`` threshold literal in ``_foreign_assets.py``.

    Anti-tautology: parses the real AST so any future re-introduction of the
    local constant triggers immediate failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/aggregation/_foreign_assets.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "50000.00":
            offenders.append(
                f"_foreign_assets.py:{node.lineno}: bare Decimal('50000.00'); use MODELO_720_REPORTING_THRESHOLD_EUR",
            )

    assert offenders == [], (
        "Local Modelo 720 threshold literals found; import MODELO_720_REPORTING_THRESHOLD_EUR from core instead:\n"
        + "\n".join(offenders)
    )


def test_no_bare_csv_mime_literal_in_tabular() -> None:
    """No bare ``"text/csv"`` literal in ``_tabular.py`` argument positions.

    Anti-tautology: parses the real AST so any future re-introduction of
    the literal triggers immediate failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/export/_tabular.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or node.value != "text/csv":
            continue
        offenders.append(f"_tabular.py:{node.lineno}: bare 'text/csv' literal")

    assert offenders == [], "Bare 'text/csv' literals found; use _CSV_MIME_TYPE instead:\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# contract — ART_7P_EXEMPTION_CAP_EUR centralisation tests
# ---------------------------------------------------------------------------


def test_art_7p_exemption_cap_eur_value() -> None:
    """``ART_7P_EXEMPTION_CAP_EUR`` equals €60,100 per Art. 7.p) LIRPF (Ley 35/2006)."""

    from decimal import Decimal

    from ..external_constants import ART_7P_EXEMPTION_CAP_EUR

    assert Decimal("60100") == ART_7P_EXEMPTION_CAP_EUR


def test_art_7p_exemption_cap_eur_is_final_decimal() -> None:
    """``ART_7P_EXEMPTION_CAP_EUR`` is a ``Decimal`` instance (typed ``Final[Decimal]``)."""

    from decimal import Decimal

    from ..external_constants import ART_7P_EXEMPTION_CAP_EUR

    assert isinstance(ART_7P_EXEMPTION_CAP_EUR, Decimal)


def test_maritime_exemption_imports_art_7p_cap_from_core() -> None:
    """``domain/renta/_maritime_exemption.py`` reads ``ART_7P_EXEMPTION_CAP_EUR`` from core."""

    import importlib

    from ..external_constants import ART_7P_EXEMPTION_CAP_EUR

    mod = importlib.import_module("aeat.domain.renta._maritime_exemption")

    assert hasattr(mod, "ART_7P_EXEMPTION_CAP_EUR"), (
        "_maritime_exemption must import ART_7P_EXEMPTION_CAP_EUR from aeat.core.external_constants"
    )
    assert mod.ART_7P_EXEMPTION_CAP_EUR is ART_7P_EXEMPTION_CAP_EUR


def test_renta_package_reexports_art_7p_cap_from_core() -> None:
    """``aeat.domain.renta`` re-exports ``ART_7P_EXEMPTION_CAP_EUR`` and it resolves to the core constant."""

    import importlib

    from ..external_constants import ART_7P_EXEMPTION_CAP_EUR

    renta = importlib.import_module("aeat.domain.renta")

    assert hasattr(renta, "ART_7P_EXEMPTION_CAP_EUR"), "aeat.domain.renta must re-export ART_7P_EXEMPTION_CAP_EUR"
    assert renta.ART_7P_EXEMPTION_CAP_EUR is ART_7P_EXEMPTION_CAP_EUR


def test_no_bare_art_7p_cap_decimal_literal_in_maritime_exemption() -> None:
    """No bare ``Decimal("60100")`` literal in ``domain/renta/_maritime_exemption.py``.

    Anti-tautology: parses the real AST so any future re-introduction triggers failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/domain/renta/_maritime_exemption.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "60100":
            offenders.append(
                f"_maritime_exemption.py:{node.lineno}: bare Decimal('60100'); use ART_7P_EXEMPTION_CAP_EUR",
            )

    assert offenders == [], (
        "Local Art. 7.p cap literals found; import ART_7P_EXEMPTION_CAP_EUR from core instead:\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# contract — MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR centralisation tests
# ---------------------------------------------------------------------------


def test_multiple_pagadores_secondary_threshold_eur_value() -> None:
    """``MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR`` equals €1,500 per Art. 96.3 LIRPF."""

    from decimal import Decimal

    from ..external_constants import MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR

    assert Decimal("1500") == MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR


def test_multiple_pagadores_secondary_threshold_eur_is_final_decimal() -> None:
    """``MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR`` is a ``Decimal`` instance."""

    from decimal import Decimal

    from ..external_constants import MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR

    assert isinstance(MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR, Decimal)


def test_deadlines_models_imports_multiple_pagadores_threshold_from_core() -> None:
    """``domain/deadlines/_models.py`` imports ``MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR`` from core."""

    import importlib

    from ..external_constants import MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR

    mod = importlib.import_module("aeat.domain.deadlines._models")

    assert hasattr(mod, "MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR"), (
        "_models must import MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR from aeat.core.external_constants"
    )
    assert mod.MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR is MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR


def test_no_bare_multiple_pagadores_threshold_literal_in_deadlines_models() -> None:
    """No bare ``Decimal("1500")`` literal in ``domain/deadlines/_models.py``.

    Anti-tautology: parses the real AST so any future re-introduction triggers failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/domain/deadlines/_models.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "1500":
            offenders.append(
                f"_models.py:{node.lineno}: bare Decimal('1500'); use MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR",
            )

    assert offenders == [], (
        "Local pagadores threshold literals found; import MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR from core:\n"
        + "\n".join(offenders)
    )
