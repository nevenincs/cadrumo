"""Centralisation contract tests for regulatory leaf constants.

This second constants sweep pins IVA rate defaults, modelo-id groups, renta
deduction values, and amortizacion scalars to ``core.external_constants`` so
application and domain consumers alias the central registry instead of carrying
local literals. The AST checks catch bare Decimal/minimum literals while identity
checks prove known consumers import the shared objects.

See Also:
    :mod:`~core.external_constants`
        Central registry that owns the typed leaf constants under test.
    :func:`~domain.iva.lookup_rate`
        IVA rate registry used to prove the default general IVA rate has not
        drifted from the dated substrate.
    :mod:`~application.aggregation._service`
        Aggregation service consumers that alias modelo-id group constants.
    :mod:`~application.inventory._service`
        Inventory service consumer of the default IVA general-rate constant.
"""

from __future__ import annotations

import ast
import importlib
import re
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from ...domain.calculations.registry.authority import bundled_authority
from ...tests import ast_for_path, leaf_name, repo_path, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _repo_tree(relative_path: str, source_tree_ast: Mapping[Path, ast.AST]) -> ast.AST:
    path = repo_path(relative_path)
    tree = ast_for_path(path, source_tree_ast)
    if tree is None:
        raise AssertionError(f"unable to parse {repo_relative(path)}")
    return tree


def _assert_module_constant_identity(
    *,
    module_name: str,
    attr_name: str,
    expected: object,
    import_message: str,
) -> None:
    mod = importlib.import_module(module_name)

    assert hasattr(mod, attr_name), import_message
    assert getattr(mod, attr_name) is expected


def _decimal_call_literal_offenders(
    *,
    relative_path: str,
    display_path: str,
    literal: str,
    replacement: str,
    source_tree_ast: Mapping[Path, ast.AST],
) -> list[str]:
    offenders: list[str] = []
    for node in ast.walk(_repo_tree(relative_path, source_tree_ast)):
        if not isinstance(node, ast.Call):
            continue
        if leaf_name(node.func) != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == literal:
            offenders.append(f"{display_path}:{node.lineno}: bare Decimal({literal!r}); use {replacement}")
    return offenders


def _min_arg_literal_offenders(
    *,
    relative_path: str,
    display_path: str,
    literal: int,
    replacement: str,
    source_tree_ast: Mapping[Path, ast.AST],
) -> list[str]:
    offenders: list[str] = []
    for node in ast.walk(_repo_tree(relative_path, source_tree_ast)):
        if not isinstance(node, ast.Call):
            continue
        if leaf_name(node.func) != "min":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and arg.value == literal:
                offenders.append(f"{display_path}:{node.lineno}: bare {literal} literal in min(); use {replacement}")
    return offenders


#: Modules that must alias the core IVA constant rather than re-declare it.
#: Empty since the inventory movement verb stopped defaulting an IVA rate: it now
#: takes taxable_base / unit_cost / acquisition_cost_stdin, so neither the service
#: nor its CLI carries a rate default to keep in step. The constant is still
#: centralised and still consumed, by domain/contribuyente assets and inventory,
#: which the literal cases below cover. Re-add a module here the moment one
#: defaults an IVA rate again.
_DEFAULT_IVA_IMPORT_CASES: tuple[tuple[str, str], ...] = ()
_DEFAULT_IVA_IMPORT_IDS: tuple[str, ...] = ()

_IVA_DECIMAL_LITERAL_CASES: tuple[tuple[str, str, str], ...] = (
    (
        "src/cadrumo/application/inventory/_service.py",
        "_service.py",
        "DEFAULT_IVA_GENERAL_RATE_PCT",
    ),
    (
        "src/cadrumo/domain/contribuyente/assets/__init__.py",
        "assets/__init__.py",
        "DEFAULT_IVA_GENERAL_RATE_PCT",
    ),
    (
        "src/cadrumo/domain/contribuyente/inventory/__init__.py",
        "inventory/__init__.py",
        "DEFAULT_IVA_GENERAL_RATE_PCT",
    ),
)
_IVA_DECIMAL_LITERAL_IDS = ("inventory-service", "contribuyente-assets", "contribuyente-inventory")

_MODELO_GROUP_CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("RETENCIONES_MODELOS", ("111", "115", "123", "180", "190", "193")),
    ("COUNTERPART_MODELOS", ("347", "349")),
    ("FOREIGN_ASSET_MODELOS", ("720",)),
    ("IVA_REGIME_MODELOS", ("303", "390")),
)
_MODELO_GROUP_IDS = ("retenciones", "counterpart", "foreign-asset", "iva-regime")

_MODELO_GROUP_ALIAS_CASES: tuple[tuple[str, str, str, str], ...] = (
    (
        "cadrumo.application.aggregation._service",
        "_RETENCIONES_MODELOS",
        "RETENCIONES_MODELOS",
        "_service must alias RETENCIONES_MODELOS from cadrumo.core.external_constants",
    ),
    (
        "cadrumo.application.aggregation._service",
        "_COUNTERPART_MODELOS",
        "COUNTERPART_MODELOS",
        "_service must alias COUNTERPART_MODELOS from cadrumo.core.external_constants",
    ),
    (
        "cadrumo.application.aggregation._service",
        "_FOREIGN_ASSET_MODELOS",
        "FOREIGN_ASSET_MODELOS",
        "_service must alias FOREIGN_ASSET_MODELOS from cadrumo.core.external_constants",
    ),
    (
        "cadrumo.application.overview._calendar",
        "_IVA_REGIME_MODELOS",
        "IVA_REGIME_MODELOS",
        "_calendar must alias IVA_REGIME_MODELOS from cadrumo.core.external_constants",
    ),
)

_MODELO_GROUP_LITERAL_CASES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "src/cadrumo/application/aggregation/_service.py",
        ("111", "115", "123", "180", "190", "193"),
        "Bare retenciones-modelos tuple literal found in _service.py; use RETENCIONES_MODELOS from core",
    ),
    (
        "src/cadrumo/application/aggregation/_service.py",
        ("347", "349"),
        "Bare counterpart-modelos tuple literal found in _service.py; use COUNTERPART_MODELOS from core",
    ),
    (
        "src/cadrumo/application/aggregation/_service.py",
        ("720",),
        "Bare foreign-asset-modelos tuple literal found in _service.py; use FOREIGN_ASSET_MODELOS from core",
    ),
    (
        "src/cadrumo/application/overview/_calendar.py",
        ("303", "390"),
        "Bare IVA-regime-modelos tuple literal found in _calendar.py; use IVA_REGIME_MODELOS from core",
    ),
)

_IRPF_INT_CONSTANT_CASES: tuple[tuple[str, int], ...] = (
    ("DEDUCCION_MATERNIDAD_MENSUAL_EUR", 100),
    ("DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR", 1200),
    ("DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR", 150),
    ("DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR", 1350),
    ("DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR", 2023),
)
_IRPF_INT_CONSTANT_IDS = (
    "maternidad-mensual",
    "maternidad-anual-cap",
    "maternidad-alta-posterior-incremento",
    "maternidad-alta-posterior-anual-cap",
    "maternidad-alta-posterior-first-filing-year",
)

_IRPF_INT_ALIAS_CASES: tuple[tuple[str, str, str, str], ...] = (
    (
        "cadrumo.domain.contribuyente._deduccion_maternidad",
        "DEDUCCION_MATERNIDAD_MENSUAL_EUR",
        "DEDUCCION_MATERNIDAD_MENSUAL_EUR",
        "_deduccion_maternidad must import DEDUCCION_MATERNIDAD_MENSUAL_EUR from cadrumo.core.external_constants",
    ),
    (
        "cadrumo.domain.contribuyente._deduccion_maternidad",
        "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR",
        "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR",
        "_deduccion_maternidad must import DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR from cadrumo.core.external_constants",
    ),
    (
        "cadrumo.domain.contribuyente._deduccion_maternidad",
        "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR",
        "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR",
        "_deduccion_maternidad must import DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR from "
        "cadrumo.core.external_constants",
    ),
    (
        "cadrumo.domain.contribuyente._deduccion_maternidad",
        "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR",
        "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR",
        "_deduccion_maternidad must import DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR from "
        "cadrumo.core.external_constants",
    ),
    (
        "cadrumo.domain.contribuyente._deduccion_maternidad",
        "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR",
        "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR",
        "_deduccion_maternidad must import DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR from "
        "cadrumo.core.external_constants",
    ),
)
_IRPF_INT_ALIAS_IDS = (
    "deduccion-maternidad-mensual",
    "deduccion-maternidad-anual-cap",
    "deduccion-maternidad-alta-posterior-incremento",
    "deduccion-maternidad-alta-posterior-anual-cap",
    "deduccion-maternidad-alta-posterior-first-filing-year",
)

_MIN_LITERAL_CASES: tuple[tuple[str, str, int, str, str], ...] = (
    (
        "src/cadrumo/domain/contribuyente/_deduccion_maternidad.py",
        "_deduccion_maternidad.py",
        1200,
        "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR",
        "Bare 1200 maternidad cap literals found in _deduccion_maternidad.py",
    ),
)
_MIN_LITERAL_IDS = ("deduccion-maternidad",)

_DECIMAL_CONSTANT_CASES: tuple[tuple[str, str], ...] = (
    ("DEFAULT_IVA_GENERAL_RATE_PCT", "21.00"),
    ("AMORTIZACION_INMUEBLE_RATE", "0.03"),
    ("REBECA_MARITIME_EXEMPTION_FRACTION", "0.50"),
)
_DECIMAL_CONSTANT_IDS = ("default-iva-general-rate", "amortizacion-inmueble-rate", "rebeca-maritime-fraction")

_DECIMAL_ALIAS_CASES: tuple[tuple[str, str, str, str], ...] = (
    (
        "cadrumo.domain.fincas._amortization_ledger",
        "AMORTIZACION_INMUEBLE_RATE",
        "AMORTIZACION_INMUEBLE_RATE",
        "_amortization_ledger must import AMORTIZACION_INMUEBLE_RATE from cadrumo.core.external_constants",
    ),
    (
        "cadrumo.domain.fincas._amortization_ledger",
        "ART_23_1_F_RATE",
        "AMORTIZACION_INMUEBLE_RATE",
        "_amortization_ledger must expose ART_23_1_F_RATE alias",
    ),
    (
        "cadrumo.domain.renta._maritime_exemption",
        "REBECA_MARITIME_EXEMPTION_FRACTION",
        "REBECA_MARITIME_EXEMPTION_FRACTION",
        "_maritime_exemption must import REBECA_MARITIME_EXEMPTION_FRACTION from cadrumo.core.external_constants",
    ),
)
_DECIMAL_ALIAS_IDS = ("amortization-rate", "amortization-art-23-alias", "rebeca-fraction")

_DECIMAL_LITERAL_CASES: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "src/cadrumo/domain/fincas/_amortization_ledger.py",
        "_amortization_ledger.py",
        "0.03",
        "AMORTIZACION_INMUEBLE_RATE",
        "Bare Decimal('0.03') amortization literals found",
    ),
    (
        "src/cadrumo/domain/renta/_maritime_exemption.py",
        "_maritime_exemption.py",
        "0.50",
        "REBECA_MARITIME_EXEMPTION_FRACTION",
        "Bare Decimal('0.50') REBECA literals found",
    ),
)
_DECIMAL_LITERAL_IDS = ("amortization-rate", "rebeca-fraction")


# ---------------------------------------------------------------------------
# contract — DEFAULT_IVA_GENERAL_RATE_PCT centralisation tests
# ---------------------------------------------------------------------------


def test_decimal_external_constant_values_and_types() -> None:
    """Decimal external constants equal their legal scalar values and remain ``Decimal`` instances."""

    from .. import external_constants

    for case_id, (constant_name, expected) in zip(_DECIMAL_CONSTANT_IDS, _DECIMAL_CONSTANT_CASES, strict=True):
        value = getattr(external_constants, constant_name)
        assert isinstance(value, Decimal), case_id
        assert value == Decimal(expected), case_id


def test_default_iva_general_rate_pct_matches_registry() -> None:
    """``DEFAULT_IVA_GENERAL_RATE_PCT`` equals the IVA-registry general rate for Spain on 2026-01-01.

    Binds the default to the dated :func:`~domain.iva.lookup_rate` registry so
    it cannot silently drift when AEAT publishes a rate change.
    """

    from datetime import date

    from ...domain.iva import EUMemberState, IvaRateKind, lookup_rate
    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    registry_rate = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2026, 1, 1))
    assert registry_rate.pct == DEFAULT_IVA_GENERAL_RATE_PCT


def test_default_iva_general_rate_pct_has_core_as_its_only_public_home() -> None:
    """The IVA default is public only from ``core.external_constants``."""
    from ...domain.contribuyente import assets, inventory
    from .. import external_constants

    constant_name = "DEFAULT_IVA_GENERAL_RATE_PCT"
    assert constant_name in vars(external_constants)
    for legacy_facade in (assets, inventory):
        assert constant_name not in legacy_facade.__all__
        assert constant_name not in vars(legacy_facade)


def test_no_verb_defaults_an_iva_rate_outside_the_core_constant() -> None:
    """No CLI verb may default an IVA rate to anything but the core constant.

    This replaces an assertion on ``inventory_movement_add``'s ``--iva-rate``
    option, which no longer exists: that verb now takes taxable_base, unit_cost
    and acquisition_cost_stdin, and the option was removed with it. Asserting a
    handler signature also predates the command-spec kernel, where parameters are
    declared on the spec rather than the function.

    Stated as the invariant instead of the site, so it keeps biting when a verb
    reintroduces a rate default -- and passes honestly while none does.
    """

    from ...entrypoints.cli import command_graph
    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    permitted = {str(DEFAULT_IVA_GENERAL_RATE_PCT), str(float(DEFAULT_IVA_GENERAL_RATE_PCT))}
    offenders: list[str] = []
    for key, spec in command_graph.by_schema_identity().items():
        for parameter in spec.parameters:
            if "iva_rate" not in parameter.name:
                continue
            literal = getattr(parameter.default, "literal", None)
            if literal is None:
                continue
            if str(literal) not in permitted:
                offenders.append(f"{key}.{parameter.name} defaults to {literal!r}")

    assert not offenders, (
        f"IVA-rate defaults must follow cadrumo.core.external_constants.DEFAULT_IVA_GENERAL_RATE_PCT: {offenders}"
    )


def test_modelo_group_values_and_types() -> None:
    """Modelo group constants equal their authoritative tuples and contain strings."""

    from .. import external_constants

    for case_id, (constant_name, expected) in zip(_MODELO_GROUP_IDS, _MODELO_GROUP_CASES, strict=True):
        value = getattr(external_constants, constant_name)
        assert value == expected, case_id
        assert isinstance(value, tuple), case_id
        assert all(isinstance(code, str) for code in value), case_id


def test_modelo_group_consumers_alias_central_constants() -> None:
    """Known consumers alias modelo group constants from core."""

    from .. import external_constants

    for _case_id, (module_name, module_attr, constant_name, message) in zip(
        _MODELO_GROUP_IDS,
        _MODELO_GROUP_ALIAS_CASES,
        strict=True,
    ):
        _assert_module_constant_identity(
            module_name=module_name,
            attr_name=module_attr,
            expected=getattr(external_constants, constant_name),
            import_message=message,
        )


def _ast_contains_modelo_group_tuple(tree: ast.AST, expected_elts: tuple[str, ...]) -> bool:
    """Return True if the AST contains a bare tuple literal whose string elements equal ``expected_elts``."""
    target_set = set(expected_elts)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Tuple):
            continue
        if len(node.elts) != len(expected_elts):
            continue
        if not all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts):
            continue
        if {e.value for e in node.elts if isinstance(e, ast.Constant)} == target_set:
            return True
    return False


def test_no_bare_modelo_group_tuple_literals_in_consumers(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """No bare modelo group tuple literals in consumers."""

    for _case_id, (relative_path, expected_elts, message) in zip(
        _MODELO_GROUP_IDS,
        _MODELO_GROUP_LITERAL_CASES,
        strict=True,
    ):
        assert not _ast_contains_modelo_group_tuple(_repo_tree(relative_path, source_tree_ast), expected_elts), message


# ---------------------------------------------------------------------------
# contract — DEDUCCION_MATERNIDAD_MENSUAL_EUR / DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR
# ---------------------------------------------------------------------------


def test_irpf_int_constant_values_types_and_maternidad_cap_relation() -> None:
    """IRPF euro constants equal their values and preserve the maternidad cap relation."""

    from .. import external_constants
    from ..external_constants import (
        DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR,
        DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR,
        DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR,
        DEDUCCION_MATERNIDAD_MENSUAL_EUR,
    )

    for case_id, (constant_name, expected) in zip(_IRPF_INT_CONSTANT_IDS, _IRPF_INT_CONSTANT_CASES, strict=True):
        value = getattr(external_constants, constant_name)
        assert isinstance(value, int), case_id
        assert value == expected, case_id

    assert DEDUCCION_MATERNIDAD_MENSUAL_EUR * 12 == DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR
    assert (
        DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR + DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR
        == DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR
    )


def test_irpf_int_constant_consumers_alias_core_constants() -> None:
    """Known consumers alias IRPF integer constants from core."""

    from .. import external_constants

    for _case_id, (module_name, module_attr, constant_name, message) in zip(
        _IRPF_INT_ALIAS_IDS,
        _IRPF_INT_ALIAS_CASES,
        strict=True,
    ):
        _assert_module_constant_identity(
            module_name=module_name,
            attr_name=module_attr,
            expected=getattr(external_constants, constant_name),
            import_message=message,
        )


# ---------------------------------------------------------------------------
# contract — IRPF cap-literal centralisation tests
# ---------------------------------------------------------------------------


def test_no_bare_irpf_cap_literals_in_min_calls(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """No bare IRPF cap literals appear as ``min()`` arguments in consumers."""

    for _case_id, (relative_path, display_path, literal, replacement, message) in zip(
        _MIN_LITERAL_IDS,
        _MIN_LITERAL_CASES,
        strict=True,
    ):
        offenders = _min_arg_literal_offenders(
            relative_path=relative_path,
            display_path=display_path,
            literal=literal,
            replacement=replacement,
            source_tree_ast=source_tree_ast,
        )

        assert offenders == [], message + ":\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# contract — Decimal-rate consumer centralisation tests
# ---------------------------------------------------------------------------


def test_decimal_constant_consumers_alias_core_constants() -> None:
    """Known consumers alias Decimal constants from core."""

    from .. import external_constants

    for _case_id, (module_name, message) in zip(_DEFAULT_IVA_IMPORT_IDS, _DEFAULT_IVA_IMPORT_CASES, strict=True):
        _assert_module_constant_identity(
            module_name=module_name,
            attr_name="DEFAULT_IVA_GENERAL_RATE_PCT",
            expected=external_constants.DEFAULT_IVA_GENERAL_RATE_PCT,
            import_message=message,
        )

    for _case_id, (module_name, module_attr, constant_name, message) in zip(
        _DECIMAL_ALIAS_IDS,
        _DECIMAL_ALIAS_CASES,
        strict=True,
    ):
        _assert_module_constant_identity(
            module_name=module_name,
            attr_name=module_attr,
            expected=getattr(external_constants, constant_name),
            import_message=message,
        )


def test_no_bare_decimal_literals_in_consumers(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """No bare Decimal literals in Decimal-constant consumers."""

    for case_id, (relative_path, display_path, replacement) in zip(
        _IVA_DECIMAL_LITERAL_IDS,
        _IVA_DECIMAL_LITERAL_CASES,
        strict=True,
    ):
        offenders = _decimal_call_literal_offenders(
            relative_path=relative_path,
            display_path=display_path,
            literal="21.00",
            replacement=replacement,
            source_tree_ast=source_tree_ast,
        )

        assert offenders == [], (
            f"Local IVA 21.00 literals found in {display_path} ({case_id}); "
            "import DEFAULT_IVA_GENERAL_RATE_PCT from core instead:\n" + "\n".join(offenders)
        )

    for _case_id, (relative_path, display_path, literal, replacement, message) in zip(
        _DECIMAL_LITERAL_IDS,
        _DECIMAL_LITERAL_CASES,
        strict=True,
    ):
        offenders = _decimal_call_literal_offenders(
            relative_path=relative_path,
            display_path=display_path,
            literal=literal,
            replacement=replacement,
            source_tree_ast=source_tree_ast,
        )

        assert offenders == [], message + ":\n" + "\n".join(offenders)


_EXTERNAL_CONSTANTS_RELATIVE_PATH = "src/cadrumo/core/external_constants.py"
_DOC_COMMENT_PREFIX = "#:"
_CATALOGUE_ID_RE = re.compile(r"``([a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9.\-]*)``")
_QUOTED_PROVISION_RE = re.compile(r"\u201c([^\u201d]+)\u201d|\"([^\"]+)\"")

#: Spanish cardinal for each plazo length a notification window could plausibly
#: carry. The grounding test looks the CONSTANT's value up here and demands the
#: corpus say that word, so changing the constant without the law changing reds.
_SPANISH_CARDINAL_BY_DIAS: Mapping[int, str] = {
    5: "cinco",
    10: "diez",
    15: "quince",
    20: "veinte",
    30: "treinta",
}


def _doc_comment_above(constant_name: str) -> str:
    """Return the ``#:`` doc-comment block immediately above ``constant_name``.

    Doc comments are not AST nodes, so the block is recovered from the source
    text: walk up from the assignment line collecting contiguous ``#:`` lines.
    """
    lines = repo_path(_EXTERNAL_CONSTANTS_RELATIVE_PATH).read_text(encoding="utf-8").splitlines()
    index = next(
        (position for position, line in enumerate(lines) if line.startswith(f"{constant_name}:")),
        None,
    )
    assert index is not None, f"{constant_name} not found in {_EXTERNAL_CONSTANTS_RELATIVE_PATH}"
    block: list[str] = []
    cursor = index - 1
    while cursor >= 0 and lines[cursor].lstrip().startswith(_DOC_COMMENT_PREFIX):
        block.append(lines[cursor].lstrip()[len(_DOC_COMMENT_PREFIX) :].strip())
        cursor -= 1
    assert block, f"{constant_name} carries no doc comment"
    return " ".join(reversed(block))


def test_dehu_rechazo_tacito_window_resolves_to_the_reviewed_legal_entry() -> None:
    """The DEHu rechazo-tácito constant's citation resolves against the legal catalogue.

    The constant is a bare ``10`` in source; what makes it a legal value rather
    than a magic number is the provision its doc comment names. This proves that
    citation is real end to end: the catalogue entry id resolves, the entry is
    corpus-backed and passes the same verification registry build applies, the
    Spanish clause quoted in the doc comment is the entry's own corpus text
    rather than a restatement, and the corpus states the plazo in the cardinal
    matching the constant's value. Changing the constant without the law
    changing fails at the last assertion.
    """
    from ...domain.calculations.registry.legal import legal_reference_quotes_corpus, verify_legal_catalogue
    from ..external_constants import DEHU_RECHAZO_TACITO_DIAS_NATURALES
    from ..resources import bundled_path

    doc_comment = _doc_comment_above("DEHU_RECHAZO_TACITO_DIAS_NATURALES")

    cited_ids = sorted(set(_CATALOGUE_ID_RE.findall(doc_comment)))
    assert cited_ids == ["ley-39-2015:art-43.2"], (
        "the DEHu rechazo-tácito constant must name exactly its legal-catalogue entry "
        f"in double backticks; found {cited_ids}"
    )
    entry_id = cited_ids[0]

    catalogue = bundled_authority().catalogues.legal
    assert entry_id in catalogue, f"cited legal-catalogue entry {entry_id!r} absent from the registry"
    reference = catalogue[entry_id]
    verify_legal_catalogue({entry_id: reference}, source_root=bundled_path())

    assert reference.article == "43.2"
    assert reference.document_id == "BOE-A-2015-10565"

    quoted = next(
        (match.group(1) or match.group(2) for match in _QUOTED_PROVISION_RE.finditer(doc_comment)),
        None,
    )
    assert quoted is not None, "the doc comment must quote the provision verbatim"
    assert legal_reference_quotes_corpus(reference, quoted, source_root=bundled_path()), (
        f"the clause quoted in the doc comment is not present in {entry_id}'s corpus text: {quoted!r}"
    )

    cardinal = _SPANISH_CARDINAL_BY_DIAS.get(DEHU_RECHAZO_TACITO_DIAS_NATURALES)
    assert cardinal is not None, (
        f"no Spanish cardinal known for a {DEHU_RECHAZO_TACITO_DIAS_NATURALES}-day window; "
        "extend _SPANISH_CARDINAL_BY_DIAS alongside a corpus that states it"
    )
    assert legal_reference_quotes_corpus(reference, f"{cardinal} días naturales", source_root=bundled_path()), (
        f"{entry_id}'s corpus does not state a {cardinal} días naturales window, so "
        f"DEHU_RECHAZO_TACITO_DIAS_NATURALES = {DEHU_RECHAZO_TACITO_DIAS_NATURALES} is ungrounded"
    )
