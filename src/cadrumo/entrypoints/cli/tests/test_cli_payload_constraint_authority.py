"""The CLI projects canonical constraints; it never declares its own.

A CLI payload is a PROJECTION of a canonical model. It may loosen a type for
the wire. It may not declare a constraint of its own, and it may not restate
one: a rule written beside a command handler is a rule the backend does not
enforce, so a value refused at the CLI is accepted by every other caller of the
same domain surface.

The discriminator this gate reads is syntactic, and deliberately so. A field
typed with an imported ``Annotated`` alias -- ``FilingRecordId``, ``CasillaId``,
``Period`` -- carries its constraint from the canonical defining module and is a
projection. A field whose annotation or default *spells out* a constraint in
this file -- ``Field(min_length=...)``, ``StringConstraints(...)``, ``conint(...)``
-- declares it here, whatever else may also hold the same rule. The first is
invisible to this gate by construction; the second is what it refuses.

``field_validator`` and ``model_validator`` bodies are refused on the same
reasoning: an invariant spanning several fields is domain logic, and the
sanctioned ways for a payload to reach one are a shared validator function or a
reconstruction of the canonical model, both of which leave the rule in its
canonical home.

Enforcement is per module and property-based, never a tally. Every CLI module
defining payload classes falls in exactly one of three sets below. A module
absent from all three that declares a constraint fails, so a NEW payload cannot
introduce one. A module listed as outstanding that no longer declares anything
also fails, so the carry-forward list cannot go stale: reconciling a module
means moving it into ``RECONCILED_MODULES`` in the same change.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLI_ROOT = Path(__file__).resolve().parent.parent

_CONSTRAINT_KWARGS = frozenset(
    {
        "min_length",
        "max_length",
        "pattern",
        "gt",
        "ge",
        "lt",
        "le",
        "multiple_of",
        "max_digits",
        "decimal_places",
        "strict",
    }
)
_CONSTRAINT_CALLS = frozenset({"Field", "StringConstraints", "conint", "confloat", "condecimal", "constr", "conlist"})
_VALIDATOR_DECORATORS = frozenset({"field_validator", "model_validator"})

_MODEL_ROOTS = frozenset({"BaseModel", "TypedDict", "OutputSchema", "OutputRootSchema"})

# Modules whose payloads carry no constraint of their own. Enforced strictly:
# any declaration reappearing here fails.
RECONCILED_MODULES: frozenset[str] = frozenset()

# CLI-native contracts whose canonical home IS the CLI. The verb grammar, the
# leaf-key spelling and the command path are the command surface's own domain;
# there is no backend model they could restate, so projecting them elsewhere
# would invent a domain concept rather than honour one.
EXEMPT_MODULES: dict[str, str] = {
    "_verb_input_schema.py": (
        "the verb input schema describes the CLI's own parameter grammar; "
        "no application or domain model declares a command's leaf key"
    ),
    "_common.py": (
        "RequestedCliLeaf spells a canonical CLI path, which is a fact about "
        "the command surface and has no counterpart outside entrypoints"
    ),
}

# Payload modules still restating canonical constraints, carried forward under
# the semantic-consolidation campaign. Each entry is asserted to STILL declare
# something, so a reconciled module cannot be left behind here.
OUTSTANDING_MODULES: dict[str, str] = {
    "_app_live_borrador_payloads.py": "borrador capture payloads await sede-evidence model reconciliation",
    "_app_live_iva_wallet_payloads.py": "shares the IVA wallet decision surface with _modelo_iva_wallet_payloads",
    "_app_live_justificante_payloads.py": "justificante identity constraints belong with the justificante model",
    "_app_live_notifications_payloads.py": "notification payloads restate sede notification metadata bounds",
    "_config/_archive_reconcile_payloads.py": "archive reconcile bounds belong with the archive tier model",
    "_config/_censo_payloads.py": "censo payload invariant belongs on CensoSnapshot",
    "_config/_check_payloads.py": "config check payloads restate diagnostic bounds",
    "_config/_collab_payloads.py": "collaboration payload invariant belongs with the apoderamiento model",
    "_config/_google_credential_source_payloads.py": "credential-source invariant belongs with the OAuth config model",
    "_config/_profile_list_payloads.py": "profile listing restates profile label bounds",
    "_config/_provision_payloads.py": "provisioning payloads restate bucket provisioning bounds",
    "_config/_storage_payloads.py": "storage payloads restate secure-storage configuration bounds",
    "_config_bucket_history_payloads.py": "bucket history restates bucket event bounds",
    "_config_descendiente_payloads.py": "descendiente invariants belong on the contribuyente model",
    "_config_help_payloads.py": "help payloads restate locale-key and label bounds",
    "_config_payloads.py": "the largest config surface; reconciled after its canonical profile models are public",
    "_diagnostics_payloads.py": "diagnostics payloads restate connectivity and probe bounds",
    "_ledger_business_payloads.py": "business-activity payloads restate ledger business model bounds",
    "_ledger_catalogue_invoice_payloads.py": "invoice payloads restate canonical invoice identity and amount rules",
    "_ledger_counterparty_payloads.py": "counterparty payloads restate counterparty identity bounds",
    "_ledger_payloads.py": "the ledger mutation quintet restates transaction amount and direction bounds",
    "_ledger_ratios_payloads.py": "usage-ratio invariants belong with the usage_ratios service",
    "_ledger_rule_payloads.py": "classification-rule payloads restate the rule model's bounds",
    "_modelo_amend_wizard_payloads.py": "amendment_reason restates the canonical discard/amendment reason alias",
    "_modelo_aux_payloads.py": "workflow-run payloads restate the locale-key grammar",
    "_modelo_bindings_payloads.py": "binding payloads restate binding provenance bounds",
    "_modelo_iva_wallet_payloads.py": "IVA wallet payloads restate the wallet decision invariant",
    "_modelo_payloads.py": "filing-record payloads restate evidence reference bounds and the evidence-match invariant",
    "_modelo_payloads_m036.py": "M036 payloads restate censo declaration bounds",
    "_modelo_review_package_payloads.py": "review-package payloads restate review model bounds",
    "_modelo_revision_payload_parts.py": "revision parts restate calculation-revision bounds",
    "_modelo_spreadsheet_payloads.py": "spreadsheet payloads restate workbook plan bounds",
    "_modelo_work_wizard_payloads.py": "work wizard payloads restate work-unit bounds",
    "_overview_payloads.py": "overview payloads restate agenda and backlog invariants",
    "_payloads_modelo_reconcile.py": "reconcile payloads restate reconciliation diff bounds",
    "_registry_payloads.py": "registry payloads restate registry report bounds",
    "_root_payloads.py": "root guard payloads restate refusal-boundary invariants",
}


def _base_names(node: ast.ClassDef) -> list[str]:
    names: list[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
        elif isinstance(base, ast.Subscript):
            value = base.value
            names.append(value.id if isinstance(value, ast.Name) else getattr(value, "attr", ""))
    return [name for name in names if name]


def _declared_constraints(node: ast.AST | None) -> set[str]:
    """Constraint kwarg names spelled out in this expression."""
    if node is None:
        return set()
    found: set[str] = set()
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name not in _CONSTRAINT_CALLS:
            continue
        found.update(str(kw.arg) for kw in call.keywords if kw.arg in _CONSTRAINT_KWARGS)
    return found


def _validator_decorators(statement: ast.AST) -> list[str]:
    if not isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
        return []
    found: list[str] = []
    for decorator in statement.decorator_list:
        name: str | None = None
        if isinstance(decorator, ast.Call):
            func = decorator.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        elif isinstance(decorator, ast.Name):
            name = decorator.id
        elif isinstance(decorator, ast.Attribute):
            name = decorator.attr
        if name in _VALIDATOR_DECORATORS:
            found.append(f"{name} on {statement.name}()")
    return found


def _payload_modules() -> dict[str, ast.Module]:
    modules: dict[str, ast.Module] = {}
    for path in sorted(_CLI_ROOT.rglob("*.py")):
        relative = path.relative_to(_CLI_ROOT).as_posix()
        if relative.startswith("tests/") or "/tests/" in relative:
            continue
        modules[relative] = ast.parse(path.read_text(encoding="utf-8"))
    return modules


def _model_class_names(modules: dict[str, ast.Module]) -> set[str]:
    """Names whose ancestry reaches a pydantic model root, resolved tree-wide."""
    bases_by_name: dict[str, set[str]] = {}
    for module in modules.values():
        for node in ast.walk(module):
            if isinstance(node, ast.ClassDef):
                bases_by_name.setdefault(node.name, set()).update(_base_names(node))
    models = set(_MODEL_ROOTS)
    changed = True
    while changed:
        changed = False
        for name, bases in bases_by_name.items():
            if name not in models and bases & models:
                models.add(name)
                changed = True
    return models


def _declarations_by_module() -> dict[str, list[str]]:
    modules = _payload_modules()
    models = _model_class_names(modules)
    findings: dict[str, list[str]] = {}
    for relative, module in modules.items():
        declarations: list[str] = []
        for node in ast.walk(module):
            if not isinstance(node, ast.ClassDef) or not (set(_base_names(node)) & models):
                continue
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                    spelled = _declared_constraints(statement.value) | _declared_constraints(statement.annotation)
                    if spelled:
                        declarations.append(
                            f"{relative}:{statement.lineno} {node.name}.{statement.target.id} "
                            f"declares {sorted(spelled)}"
                        )
                for validator in _validator_decorators(statement):
                    declarations.append(f"{relative}:{statement.lineno} {node.name} declares {validator}")
        if declarations:
            findings[relative] = declarations
    return findings


def test_unlisted_cli_module_declares_no_constraint() -> None:
    """A payload module in no set may not declare a constraint or validator."""
    findings = _declarations_by_module()
    known = RECONCILED_MODULES | EXEMPT_MODULES.keys() | OUTSTANDING_MODULES.keys()
    undeclared = {module: lines for module, lines in findings.items() if module not in known}
    assert not undeclared, (
        "CLI payload modules declare constraints the canonical model must own. "
        "Project an imported Annotated alias, or move the rule to its canonical "
        f"home: {undeclared}"
    )


def test_reconciled_cli_modules_stay_clean() -> None:
    """A module recorded as reconciled may never regain a declaration."""
    findings = _declarations_by_module()
    regressed = {module: findings[module] for module in sorted(RECONCILED_MODULES) if module in findings}
    assert not regressed, f"reconciled CLI payload modules declared constraints again: {regressed}"


def test_outstanding_entries_are_not_stale() -> None:
    """A carried-forward module that is now clean must be moved, not left."""
    findings = _declarations_by_module()
    stale = sorted(module for module in OUTSTANDING_MODULES if module not in findings)
    assert not stale, (
        "these CLI payload modules no longer declare constraints; move them from "
        f"OUTSTANDING_MODULES to RECONCILED_MODULES: {stale}"
    )


def test_exempt_entries_are_not_stale() -> None:
    """An exemption that stopped applying must be removed, not left standing."""
    findings = _declarations_by_module()
    stale = sorted(module for module in EXEMPT_MODULES if module not in findings)
    assert not stale, f"these CLI payload modules no longer need their exemption: {stale}"


def test_every_listed_module_exists() -> None:
    """A renamed or deleted module may not keep a silent entry in any set."""
    missing = sorted(
        module
        for module in (RECONCILED_MODULES | EXEMPT_MODULES.keys() | OUTSTANDING_MODULES.keys())
        if not (_CLI_ROOT / module).is_file()
    )
    assert not missing, f"listed CLI payload modules do not exist: {missing}"


def test_every_listed_reason_is_stated() -> None:
    """The judgement lives in the reason, so an empty one is not an entry."""
    unreasoned = sorted(
        module for module, reason in (EXEMPT_MODULES | OUTSTANDING_MODULES).items() if len(reason.strip()) < 20
    )
    assert not unreasoned, f"listed CLI payload modules carry no stated reason: {unreasoned}"


def test_no_module_is_listed_twice() -> None:
    """One module, one disposition -- overlap hides which rule governs it."""
    overlaps = sorted(
        (RECONCILED_MODULES & EXEMPT_MODULES.keys())
        | (RECONCILED_MODULES & OUTSTANDING_MODULES.keys())
        | (EXEMPT_MODULES.keys() & OUTSTANDING_MODULES.keys())
    )
    assert not overlaps, f"CLI payload modules listed in more than one set: {overlaps}"
