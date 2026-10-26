"""Recognize declared registry revision subjects in literal Python collections."""

from __future__ import annotations

import ast

from pydantic import ValidationError

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

from .temporal_enrollment_models import (
    _MODELO_ID_ADAPTER,
    _REVISION_ID_ADAPTER,
    LiteralEnrollmentDeclaration,
    RegistryRevisionSubject,
)


def _literal_enrollment_declarations(
    source: str, *, path: str, authority: ValidatedRegistryAuthority
) -> tuple[LiteralEnrollmentDeclaration, ...]:
    """Return the module-level collections that enumerate registry revisions.

    A row's shape alone does not establish that a collection names revisions:
    a modelo keyed to a design filename, and a feeder modelo keyed to the
    summary modelo it feeds, both read as a modelo beside a digit-leading
    token. Recognition therefore requires at least one row to name a revision
    the compiled registry actually declares, which those collections never do.
    """
    tree = ast.parse(source, filename=path)
    declarations: list[LiteralEnrollmentDeclaration] = []
    for statement in tree.body:
        assignment = _module_assignment(statement)
        if assignment is None:
            continue
        symbol, value = assignment
        subjects = tuple(subject for row in _literal_rows(value) if (subject := _row_subject(row)) is not None)
        if subjects and any(_subject_is_declared(subject, authority=authority) for subject in subjects):
            declarations.append(LiteralEnrollmentDeclaration(path, symbol, subjects))
    return tuple(declarations)


def _subject_is_declared(subject: RegistryRevisionSubject, *, authority: ValidatedRegistryAuthority) -> bool:
    """Whether the compiled registry declares this exact revision identity.

    Declared, not law-selectable: the corpus ships revisions below the supported
    floor and a test enumerating one is reading real authored history.
    """
    try:
        return subject.revision in authority.modelo(subject.modelo).revisions
    except (KeyError, LookupError):
        return False


def _module_assignment(statement: ast.stmt) -> tuple[str, ast.expr] | None:
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target = statement.targets[0]
        if isinstance(target, ast.Name):
            return target.id, statement.value
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.value is not None:
        return statement.target.id, statement.value
    return None


def _literal_rows(value: ast.expr) -> tuple[ast.expr, ...]:
    if isinstance(value, ast.Tuple | ast.List | ast.Set):
        return tuple(value.elts)
    if isinstance(value, ast.Dict):
        return tuple(key for key in value.keys if key is not None)
    return ()


def _row_subject(row: ast.expr) -> RegistryRevisionSubject | None:
    fields: list[ast.expr]
    if isinstance(row, ast.Tuple | ast.List):
        fields = row.elts
    elif isinstance(row, ast.Call):
        fields = row.args
    else:
        return None
    if len(fields) < 2:
        return None
    modelo = _string_literal(fields[0])
    revision = _string_literal(fields[1])
    if modelo is None or revision is None or not revision[:1].isdigit():
        return None
    try:
        return RegistryRevisionSubject(
            _MODELO_ID_ADAPTER.validate_python(modelo),
            _REVISION_ID_ADAPTER.validate_python(revision),
        )
    except ValidationError:
        return None


def _string_literal(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None
