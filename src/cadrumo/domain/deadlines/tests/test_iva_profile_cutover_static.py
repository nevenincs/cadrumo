"""Static regression gates for the strict canonical IVA profile shape."""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory
from ....tests.inventory import parse_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IVA_SECTION = "iva"
_IVA_REGIME_PATH = _IVA_SECTION + ".regime"
_REQUIRED_IVA_FACT_PATHS = frozenset(
    (
        "tax_residence.jurisdiction_scope",
        _IVA_SECTION + ".m303_regime_composition",
        _IVA_SECTION + ".redeme_enrolled",
        _IVA_SECTION + ".cash_accounting_regime_enrolled",
        _IVA_SECTION + ".voluntary_sii_enrolled",
        _IVA_SECTION + ".hydrocarbon_deposit_advance_payment_deduction_entitled",
    ),
)
_REQUIRED_MODELO_IVA_KEYWORDS = frozenset(
    (
        "tax_territory",
        "regime_composition",
        "redeme_enrolled",
        "cash_accounting_regime_enrolled",
        "voluntary_sii_enrolled",
        "hydrocarbon_deposit_advance_payment_deduction_entitled",
    ),
)


@dataclass(frozen=True)
class _ProfileShapeExclusion:
    """One deliberately non-profile fixture fragment, keyed by its enclosing scope.

    Keyed by ``(path, function)`` rather than by line number: a line-keyed
    exemption silently detaches the moment anything above it shifts, which
    turns a reasoned exclusion into a stale one nobody re-reads. ``function``
    is ``None`` for a module-level map.
    """

    path: str
    function: str | None
    reason: str
    expected_count: int = 1


# These are deliberately non-profile maps: legal-reference
# metadata, blank-IVA refusal input, warning metadata, and raw calendar diagnostics.
_LITERAL_NON_PROFILE_EXCLUSIONS = (
    _ProfileShapeExclusion(
        "src/cadrumo/domain/user_profile/tests/test_taxpayer_type_schema_fields.py",
        "test_iva_profile_selector_legal_refs_resolve_against_catalogue",
        "legal-reference metadata",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/domain/deadlines/tests/test_m303_tax_territory_profile.py",
        "test_blank_wizard_iva_answers_do_not_claim_an_iva_block",
        "blank IVA answers prove no block is claimed",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/overview/calendar_warnings.py",
        None,
        "warning metadata",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/user_profile/tests/test_profile_key_schema_required_parity.py",
        None,
        "schema-divergence metadata",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/user_profile/tests/test_filing_baseline_flag_spelling.py",
        None,
        "a deliberately owed IVA block and the path-to-flag metadata that names what it owes",
        expected_count=2,
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/modelo/tests/test_simplificado_ledger_bypass.py",
        "test_simplificado_bypasses_ledger_preflight_when_transactions_are_unclassified",
        "profile_values fragment carries only the regime selector the ledger-preflight bypass reads",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/modelo/tests/test_simplificado_ledger_bypass.py",
        "test_general_profile_raises_preflight_error_when_transactions_are_unclassified",
        "profile_values fragment carries only the regime selector the ledger-preflight bypass reads",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/user_profile/tests/test_iva_block_profile_completeness.py",
        "test_declared_iva_regime_reports_the_whole_block_as_missing",
        "deliberately incomplete profile proves the canonical IVA block is demanded",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/user_profile/tests/test_iva_block_profile_completeness.py",
        "test_the_general_regime_settles_the_composition_but_not_the_rest_of_the_block",
        "deliberately incomplete general-regime profile proves only the composition is settled",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/domain/deadlines/tests/test_general_regime_m303_composition.py",
        "_facts",
        "the composition is deliberately left unstated to prove the general regime settles it",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/user_profile/tests/test_iva_block_profile_completeness.py",
        "test_completeness_demands_exactly_what_the_resolver_refuses_without",
        "incremental incomplete maps compare completeness demands with resolver refusals",
        expected_count=2,
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/overview/tests/test_calendar.py",
        "test_calendar_completeness_lists_uncomputable_with_reason",
        "raw calendar completeness diagnostics",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/overview/tests/test_calendar.py",
        "test_calendar_warnings_include_registry_deadline_window_predicates",
        "raw calendar warning diagnostics",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/overview/tests/test_calendar_profile_context.py",
        "test_calendar_warnings_carry_their_sentence_in_the_read_language",
        "raw calendar values that provoke the warnings whose read-language sentence is checked",
    ),
)

_FACT_CONTAINER_NON_PROFILE_EXCLUSIONS = (
    _ProfileShapeExclusion(
        "src/cadrumo/application/tests/test_workbench_generation_home.py",
        "test_an_incomplete_profile_publishes_reasoned_zones_instead_of_failing",
        "deliberately incomplete profile proves the workbench reasons about the gap instead of failing",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/user_profile/tests/test_overview_lists_conditional_requirements.py",
        "test_a_claimed_iva_block_lists_every_path_it_owes",
        "deliberately incomplete IVA claim proves the overview lists every path the block owes",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/user_profile/tests/test_overview_lists_conditional_requirements.py",
        "test_the_general_regime_does_not_ask_for_the_modelo_303_composition",
        "deliberately incomplete general-regime claim proves the overview owes no composition",
    ),
)


def _source_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _called_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _fact_path(call: ast.Call) -> str | None:
    if _called_name(call) != "UserProfileFact":
        return None
    value = next((keyword.value for keyword in call.keywords if keyword.arg == "path"), None)
    return value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None


def _profile_fact_paths(
    container: ast.Tuple | ast.List, shared: Mapping[str, frozenset[str]] | None = None
) -> frozenset[str]:
    """Return the fact paths a container names, including those of a module-level fact tuple it unpacks."""
    paths = {
        path
        for element in container.elts
        if isinstance(element, ast.Call)
        if ((path := _fact_path(element)) is not None and path)
    }
    for element in container.elts:
        if isinstance(element, ast.Starred) and isinstance(element.value, ast.Name):
            paths |= shared.get(element.value.id, frozenset()) if shared is not None else frozenset()
    return frozenset(paths)


def _shared_fact_tuples(module: ast.Module) -> dict[str, frozenset[str]]:
    """Map each module-level fact tuple or list to its paths, so a fixture can unpack it."""
    return {
        statement.targets[0].id: paths
        for statement in module.body
        if isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and isinstance(statement.value, ast.Tuple | ast.List)
        if (paths := _profile_fact_paths(statement.value))
    }


_PERSONA_COMPOSER = "persona_facts_beneath"
"""The fixture seam that lays stated facts over a catalogue persona's complete profile."""


def _local_containers(scope: ast.AST) -> dict[str, list[ast.expr]]:
    """Map each name a scope assigns to the expressions assigned to it, without entering nested scopes."""
    assigned: dict[str, list[ast.expr]] = {}
    pending = list(ast.iter_child_nodes(scope))
    while pending:
        node = pending.pop()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda):
            continue
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            assigned.setdefault(node.targets[0].id, []).append(node.value)
        pending.extend(ast.iter_child_nodes(node))
    return assigned


def _resolved(expression: ast.expr, assigned: Mapping[str, list[ast.expr]]) -> list[ast.expr]:
    if isinstance(expression, ast.Name):
        return assigned.get(expression.id, [])
    return [expression]


def _omits_a_required_iva_path(call: ast.Call, assigned: Mapping[str, list[ast.expr]]) -> bool:
    """Whether the composer's ``without`` drops a required path or a section prefix holding one."""
    without = next((keyword.value for keyword in call.keywords if keyword.arg == "without"), None)
    if without is None:
        return False
    names = {
        node.value
        for expression in _resolved(without, assigned)
        for node in ast.walk(expression)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    return any(
        name == path or (name.endswith(".") and path.startswith(name))
        for name in names
        for path in _REQUIRED_IVA_FACT_PATHS
    )


def _persona_overlays(module: ast.Module) -> frozenset[int]:
    """Return the identities of fact containers stated over a persona's complete profile.

    A fragment handed to the persona composer replaces the persona's facts only at the paths it
    states, so the persona's own IVA block supplies every axis the fragment leaves out. The
    fragment is still incomplete when the composer is told to omit one of those axes.
    """
    overlays: set[int] = set()
    scopes = [module, *(node for node in ast.walk(module) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef))]
    for scope in scopes:
        assigned = _local_containers(scope)
        pending = list(ast.iter_child_nodes(scope))
        while pending:
            node = pending.pop()
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda):
                continue
            pending.extend(ast.iter_child_nodes(node))
            if not isinstance(node, ast.Call) or _called_name(node) != _PERSONA_COMPOSER:
                continue
            stated = (
                node.args[0]
                if node.args
                else next((keyword.value for keyword in node.keywords if keyword.arg == "stated"), None)
            )
            if stated is None or _omits_a_required_iva_path(node, assigned):
                continue
            overlays.update(
                id(expression)
                for expression in _resolved(stated, assigned)
                if isinstance(expression, ast.Tuple | ast.List)
            )
    return frozenset(overlays)


def _iter_modules() -> Iterator[tuple[Path, ast.Module]]:
    """Yield every shipped module and its AST, refusing an empty walk.

    Measured: with `_source_root()` pointed at a directory that does not exist
    this yielded 0 modules silently, against 5,939 in the healthy tree, so the
    cutover assertions held over nothing. A generator makes that worse than
    usual -- a caller consuming an empty iterator sees a clean result, not an
    error -- so the refusal is raised before the first yield.
    """
    package = _source_root() / "src" / "cadrumo"
    modules = scan_directory(package, pattern="*.py", recursive=True, require_root=True)
    if not modules:
        message = (
            f"the IVA-profile cutover walk reached no module under {package}; "
            "a walk matching nothing cannot find a retired profile shape"
        )
        raise AssertionError(message)
    for path in modules:
        yield path, parse_source(path.read_text(encoding="utf-8"), filename=str(path))


def _relative(path: Path) -> str:
    return path.relative_to(_source_root()).as_posix()


_LEAF_NODES = (ast.Name, ast.Constant, ast.expr_context, ast.operator, ast.unaryop, ast.boolop, ast.cmpop)
"""Nodes that hold nothing this gate reads, so a walk need not enter them."""


class _ProfileShapeFindings:
    """The three incomplete-shape tallies, accumulated over the tree."""

    def __init__(self) -> None:
        self.fact_containers: Counter[tuple[str, str | None]] = Counter()
        self.modelo_iva_constructors: list[tuple[str, int, frozenset[str]]] = []
        self.literal_maps: Counter[tuple[str, str | None]] = Counter()

    def scan(self, relative_path: str, module: ast.Module) -> None:
        """Read every shape in one walk, tracking the enclosing function."""
        shared_fact_tuples = _shared_fact_tuples(module)
        persona_overlays = _persona_overlays(module)

        def walk(node: ast.AST, enclosing: str | None) -> None:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                enclosing = node.name
            elif isinstance(node, ast.Call):
                self._read_constructor(relative_path, node)
            elif isinstance(node, ast.Tuple | ast.List):
                fact_paths = _profile_fact_paths(node, shared_fact_tuples)
                if (
                    _IVA_REGIME_PATH in fact_paths
                    and _REQUIRED_IVA_FACT_PATHS - fact_paths
                    and id(node) not in persona_overlays
                ):
                    self.fact_containers[(relative_path, enclosing)] += 1
            elif isinstance(node, ast.Dict):
                literal_paths = frozenset(
                    key.value for key in node.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)
                )
                if _IVA_REGIME_PATH in literal_paths and _REQUIRED_IVA_FACT_PATHS - literal_paths:
                    self.literal_maps[(relative_path, enclosing)] += 1
            for child in ast.iter_child_nodes(node):
                if not isinstance(child, _LEAF_NODES):
                    walk(child, enclosing)

        walk(module, None)

    def _read_constructor(self, relative_path: str, node: ast.Call) -> None:
        if _called_name(node) != "ModeloIVAProfile":
            return
        provided = frozenset(keyword.arg for keyword in node.keywords if keyword.arg is not None)
        missing = _REQUIRED_MODELO_IVA_KEYWORDS - provided
        if missing:
            self.modelo_iva_constructors.append((relative_path, node.lineno, missing))


def test_every_claimed_current_iva_profile_has_the_canonical_required_axes() -> None:
    findings = _ProfileShapeFindings()
    for path, module in _iter_modules():
        findings.scan(_relative(path), module)

    assert findings.fact_containers == Counter(
        (entry.path, entry.function) for entry in _FACT_CONTAINER_NON_PROFILE_EXCLUSIONS
    )
    assert findings.modelo_iva_constructors == []
    assert findings.literal_maps == Counter(
        {(entry.path, entry.function): entry.expected_count for entry in _LITERAL_NON_PROFILE_EXCLUSIONS}
    )


_BARE_FRAGMENT = "facts = (UserProfileFact(path='iva.regime', value='GENERAL'),)"
_PERSONA_OVERLAY = "facts = persona_facts_beneath((UserProfileFact(path='iva.regime', value='GENERAL'),))"
_OVERLAY_THROUGH_A_LOCAL = """
def build():
    stated = [UserProfileFact(path='iva.regime', value='GENERAL')]
    return persona_facts_beneath(stated)
"""
_OVERLAY_OMITTING_THE_SECTION = (
    "facts = persona_facts_beneath((UserProfileFact(path='iva.regime', value='GENERAL'),), without=('iva.',))"
)
_OVERLAY_OMITTING_AN_AXIS_THROUGH_A_LOCAL = """
def build():
    omitted = ('iva.voluntary_sii_enrolled',)
    return persona_facts_beneath((UserProfileFact(path='iva.regime', value='GENERAL'),), without=omitted)
"""


@pytest.mark.parametrize(
    ("source", "flagged"),
    (
        pytest.param(_BARE_FRAGMENT, True, id="bare-fragment"),
        pytest.param(_PERSONA_OVERLAY, False, id="persona-overlay"),
        pytest.param(_OVERLAY_THROUGH_A_LOCAL, False, id="persona-overlay-through-a-local"),
        pytest.param(_OVERLAY_OMITTING_THE_SECTION, True, id="persona-overlay-omitting-the-iva-section"),
        pytest.param(
            _OVERLAY_OMITTING_AN_AXIS_THROUGH_A_LOCAL, True, id="persona-overlay-omitting-one-axis-through-a-local"
        ),
    ),
)
def test_a_regime_fragment_is_complete_only_over_a_persona_that_keeps_its_iva_block(source: str, flagged: bool) -> None:
    findings = _ProfileShapeFindings()
    findings.scan("fixture.py", ast.parse(source))
    assert bool(findings.fact_containers) is flagged
