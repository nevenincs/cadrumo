"""Runtime gate for every localized object compiled from the shipped registry.

The locale scanner already derives the full schema-key universe from the
registry.  This gate deliberately exercises the public schema accessors on
that same loaded corpus instead of resolving each leaf in isolation: a casilla
can inherit a continuity label after its revision-occurrence leaf and optional
help or revision labels are allowed to have no source text at all.

It also holds the key compiler to one declaration site.  Tooling may route or
move already-derived keys, but no second production builder may construct a
``modelo.schema`` identity from registry fields.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest

from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import ModeloDefinition, load_registry_tree
from cadrumo.domain.calculations.registry import _modelo_localization as modelo_localization
from dev._paths import REPO_ROOT
from dev.locales import scan_modelo_schema_keys

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CANONICAL_COMPILER = REPO_ROOT / "src" / "cadrumo" / "domain" / "calculations" / "registry" / "_modelo_localization.py"
_REDECLARATION_ROOTS = (
    REPO_ROOT / "src" / "cadrumo",
    REPO_ROOT / "dev" / "locales",
)


@pytest.fixture(scope="module")
def modelos() -> tuple[ModeloDefinition, ...]:
    """Load the complete shipped schema corpus without a hand-maintained subset."""
    loaded, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return loaded


def _runtime_schema_keys(modelos: Iterable[ModeloDefinition]) -> frozenset[str]:
    """Return every concrete locale key attached to loaded schema objects."""
    keys: set[str] = set()
    for modelo in modelos:
        keys.add(modelo.title_localization_key)
        keys.add(modelo.official_name_localization_key)
        for revision in modelo.revisions.values():
            keys.add(revision.localization_key)
            for construct in revision.constructs:
                keys.add(construct.localization_key)
            for casilla in revision.casillas:
                keys.update(casilla.localization_keys)
                keys.update(f"{key.removesuffix('.label')}.help" for key in casilla.localization_keys)
                keys.update(alias.localization_key for alias in casilla.aliases)
    return frozenset(keys)


def _required_resolution_failures(
    *,
    subject: str,
    resolver: Callable[[str], str],
) -> tuple[str, ...]:
    """Return every supported locale where a required schema scalar cannot render."""
    failures: list[str] = []
    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        try:
            value = resolver(locale)
        except Exception as exc:
            failures.append(f"{subject} locale={locale}: {type(exc).__name__}: {exc}")
            continue
        if not value.strip():
            failures.append(f"{subject} locale={locale}: blank resolution")
    return tuple(failures)


def _optional_resolution_failures(
    *,
    subject: str,
    resolver: Callable[[str], str | None],
) -> tuple[str, ...]:
    """Check an optional scalar without promoting absence into a required field.

    Optional help and revision labels may deliberately resolve to ``None`` in
    any locale.  When an optional value is authored, however, the production
    resolver must return non-blank text rather than an invalid scalar or a
    fallback error.
    """
    failures: list[str] = []
    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        try:
            value = resolver(locale)
        except Exception as exc:
            failures.append(f"{subject} locale={locale}: {type(exc).__name__}: {exc}")
            continue
        if value is not None and not value.strip():
            failures.append(f"{subject} locale={locale}: blank resolution")
    return tuple(failures)


def _runtime_resolution_failures(modelos: Iterable[ModeloDefinition]) -> tuple[str, ...]:
    """Resolve every shipped Modelo-schema localization surface in every locale."""
    failures: list[str] = []
    for modelo in modelos:
        modelo_subject = f"modelo={modelo.id}"
        failures.extend(_required_resolution_failures(subject=f"{modelo_subject} title", resolver=modelo.get_title))
        failures.extend(
            _required_resolution_failures(
                subject=f"{modelo_subject} official_name",
                resolver=modelo.get_official_name,
            ),
        )
        for revision in modelo.revisions.values():
            revision_subject = f"{modelo_subject} revision={revision.id}"
            failures.extend(
                _optional_resolution_failures(
                    subject=f"{revision_subject} label",
                    resolver=revision.get_label,
                ),
            )
            for construct in revision.constructs:
                failures.extend(
                    _required_resolution_failures(
                        subject=f"{revision_subject} construct={construct.id} title",
                        resolver=construct.get_title,
                    ),
                )
            for casilla in revision.casillas:
                casilla_subject = f"{revision_subject} casilla={casilla.id}"
                failures.extend(
                    _required_resolution_failures(
                        subject=f"{casilla_subject} label",
                        resolver=casilla.get_label,
                    ),
                )
                failures.extend(
                    _optional_resolution_failures(
                        subject=f"{casilla_subject} help",
                        resolver=casilla.get_help,
                    ),
                )
                for alias_index, alias in enumerate(casilla.aliases):
                    failures.extend(
                        _required_resolution_failures(
                            subject=f"{casilla_subject} alias={alias_index} label",
                            resolver=alias.get_label,
                        ),
                    )
    return tuple(failures)


def _locale_key_builder_declarations(
    paths: Iterable[Path],
    *,
    builder_names: frozenset[str],
) -> dict[str, tuple[Path, ...]]:
    """Find exact builder-name declarations outside test code.

    This is intentionally narrower than matching a dotted-prefix literal.
    Routing and migration tools legitimately name the prefix; duplicating the
    identity compiler is the risk this audit prohibits.
    """
    declared: dict[str, list[Path]] = {}
    for root in paths:
        for source in root.rglob("*.py"):
            if "tests" in source.parts:
                continue
            _append_locale_key_builder_declarations(
                declared,
                tree=ast.parse(source.read_text(encoding="utf-8"), filename=str(source)),
                source=source,
                builder_names=builder_names,
            )
    return {name: tuple(locations) for name, locations in declared.items()}


def _append_locale_key_builder_declarations(
    declared: dict[str, list[Path]],
    *,
    tree: ast.AST,
    source: Path,
    builder_names: frozenset[str],
) -> None:
    """Append canonical-builder declarations from one already-parsed source tree."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in builder_names:
            declared.setdefault(node.name, []).append(source)


def test_runtime_scanner_covers_every_key_attached_to_shipped_schema_objects(
    modelos: tuple[ModeloDefinition, ...],
) -> None:
    """The scanner and runtime compiler agree on the complete shipped inventory."""
    runtime_keys = _runtime_schema_keys(modelos)
    scanner_keys = frozenset(scan_modelo_schema_keys())

    assert runtime_keys, "the registry loader yielded no Modelo localization identities"
    assert scanner_keys == runtime_keys


def test_every_shipped_modelo_schema_localization_resolves_for_every_output_locale(
    modelos: tuple[ModeloDefinition, ...],
) -> None:
    """Public schema accessors render every required text in every shipped locale."""
    failures = _runtime_resolution_failures(modelos)

    assert failures == (), (
        f"{len(failures)} Modelo-schema localization resolution failure(s) "
        f"(showing the first {min(len(failures), 50)}):\n  " + "\n  ".join(failures[:50])
    )


def test_runtime_gate_detects_a_missing_real_casilla_label_key(
    modelos: tuple[ModeloDefinition, ...],
) -> None:
    """Mutation bite: a missing derived label cannot be hidden by the sweep."""
    modelo = next(modelo for modelo in modelos if any(revision.casillas for revision in modelo.revisions.values()))
    revision = next(revision for revision in modelo.revisions.values() if revision.casillas)
    casilla = revision.casillas[0]
    missing_key = "modelo.schema.__s30_missing__.revision.__s30_missing__.casilla.__s30_missing__.label"
    missing_casilla = casilla.model_copy(update={"localization_keys": (missing_key,)})
    missing_revision = revision.model_copy(update={"casillas": (missing_casilla, *revision.casillas[1:])})
    missing_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision.id: missing_revision}},
    )

    failures = _runtime_resolution_failures((missing_modelo,))

    assert any(missing_key in failure for failure in failures), failures


def test_modelo_locale_identity_builders_have_one_canonical_production_home() -> None:
    """No production module redeclares a Modelo-schema locale-key builder."""
    expected_names = frozenset(
        name
        for name, value in inspect.getmembers(modelo_localization, inspect.isfunction)
        if name.endswith("_locale_key") and name in modelo_localization.__all__
    )
    declarations = _locale_key_builder_declarations(_REDECLARATION_ROOTS, builder_names=expected_names)

    assert set(declarations) == expected_names
    assert all(locations == (_CANONICAL_COMPILER,) for locations in declarations.values())


def test_redeclaration_audit_detects_a_second_identity_builder() -> None:
    """Mutation bite: the AST audit sees a second builder declaration."""
    mutated_source = REPO_ROOT / "dev" / "locales" / "_s30_mutation.py"
    declarations: dict[str, list[Path]] = {}
    builder_names = frozenset({"revision_locale_key"})
    _append_locale_key_builder_declarations(
        declarations,
        tree=ast.parse(_CANONICAL_COMPILER.read_text(encoding="utf-8"), filename=str(_CANONICAL_COMPILER)),
        source=_CANONICAL_COMPILER,
        builder_names=builder_names,
    )
    _append_locale_key_builder_declarations(
        declarations,
        tree=ast.parse(
            "def revision_locale_key(modelo_id, revision_id):\n    return f'{modelo_id}.{revision_id}'\n",
            filename=str(mutated_source),
        ),
        source=mutated_source,
        builder_names=builder_names,
    )

    assert declarations["revision_locale_key"] == [_CANONICAL_COMPILER, mutated_source]
