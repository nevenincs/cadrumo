"""Every engine-mirrored model pair keeps its canonical field inventory, without any owner data.

The engine checks a pair's inventory only when a value of that type is projected,
so a drifted mirror otherwise surfaces as a refused read in a native test or for
an operator holding such a value. This walks the annotations the engine walks.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass, is_dataclass
from pathlib import Path
from types import UnionType
from typing import Union, get_args, get_origin

import pytest
from pydantic import BaseModel

from cadrumo.application import workbench_generation_contracts as generation_contracts
from cadrumo.application.modelo.declaration_summary import DeclarationSummary
from cadrumo.application.modelo.work_form_service import ModeloWorkFormLoadV1
from cadrumo.application.modelo.workbench_projection import PublicModeloWorkFormLoadV1, PublicSpanishTaxIdFormat
from cadrumo.application.operations._dataclass_fields import dataclass_type_hints
from cadrumo.application.operations.public_mirror import PublicScalarValueV1, bare_annotation
from cadrumo.application.workbench_generation_public_contracts import (
    PublicDeclarationSummary,
    PublicSearchGenerationStateV1,
    PublicWorkbenchGenerationV1,
)
from cadrumo.core.identity.documents import SpanishTaxIdFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_APPLICATION_ROOT = Path(generation_contracts.__file__).resolve().parent

_ENROLLED: tuple[tuple[object, object], ...] = (
    (generation_contracts.WorkbenchGenerationV1, PublicWorkbenchGenerationV1),
    (ModeloWorkFormLoadV1, PublicModeloWorkFormLoadV1),
    (SpanishTaxIdFormat, PublicSpanishTaxIdFormat),
)
_REVIEWED_OMISSIONS: Mapping[type, frozenset[str]] = {PublicSearchGenerationStateV1: frozenset({"projection"})}


def _is_model(annotation: object) -> bool:
    return isinstance(annotation, type) and (issubclass(annotation, BaseModel) or is_dataclass(annotation))


def _fields(model: type) -> Mapping[str, object]:
    if issubclass(model, BaseModel):
        model.model_rebuild()
        return {name: field.annotation for name, field in model.model_fields.items()}
    return dataclass_type_hints(model)


def _arms(annotation: object) -> tuple[object, ...]:
    bare = bare_annotation(annotation)
    if get_origin(bare) in (Union, UnionType):
        return tuple(arm for choice in get_args(bare) if choice is not type(None) for arm in _arms(choice))
    return (bare,)


def _canonical_arm(public: type, canonical_arms: tuple[object, ...]) -> object | None:
    models = tuple(arm for arm in canonical_arms if _is_model(arm))
    for arm in models:
        if isinstance(arm, type) and arm.__name__ == public.__name__.removeprefix("Public"):
            return arm
    # A non-union canonical field projects into its one public model whatever its name.
    return models[0] if len(models) == 1 else None


@dataclass
class _Walk:
    omissions: Mapping[type, frozenset[str]]
    pairs: set[tuple[type, type]]
    findings: list[str]

    def _visit_pair(self, canonical: type, public: type, path: str) -> None:
        if (canonical, public) in self.pairs:
            return
        self.pairs.add((canonical, public))
        canonical_fields, public_fields = _fields(canonical), _fields(public)
        omitted = set(canonical_fields) - set(public_fields)
        invented = set(public_fields) - set(canonical_fields)
        expected = self.omissions.get(public, frozenset())
        if omitted != expected or invented:
            self.findings.append(
                f"{path}: {canonical.__name__} -> {public.__name__} "
                f"missing={sorted(omitted - expected)} stale_omission={sorted(expected - omitted)} "
                f"invented={sorted(invented)}"
            )
        for name, annotation in public_fields.items():
            if name in canonical_fields:
                self.visit(canonical_fields[name], annotation, f"{path}.{name}")

    def _visit_tuple(self, canonical_arms: tuple[object, ...], public: object, path: str) -> None:
        shapes = tuple(get_args(arm) for arm in canonical_arms if get_origin(arm) is tuple)
        # A public tuple over a canonical mapping holds entry models with no canonical counterpart.
        if not shapes:
            return
        canonical_items, public_items = shapes[0], get_args(public)
        if len(public_items) == 2 and public_items[1] is Ellipsis:
            self.visit(canonical_items[0] if canonical_items else object, public_items[0], f"{path}[]")
        elif len(public_items) != len(canonical_items):
            self.findings.append(f"{path}: fixed tuple changed arity")
        else:
            for index, item in enumerate(public_items):
                self.visit(canonical_items[index], item, f"{path}[{index}]")

    def visit(self, canonical: object, public: object, path: str) -> None:
        canonical_arms = _arms(canonical)
        for arm in _arms(public):
            if arm is PublicScalarValueV1 or arm in canonical_arms:
                continue
            if get_origin(arm) is tuple:
                self._visit_tuple(canonical_arms, arm, path)
            elif _is_model(arm) and isinstance(arm, type):
                match = _canonical_arm(arm, canonical_arms)
                if isinstance(match, type):
                    self._visit_pair(match, arm, path)
                else:
                    self.findings.append(f"{path}: no canonical arm for {arm.__name__}")


def _walk(canonical: object, public: object, omissions: Mapping[type, frozenset[str]]) -> _Walk:
    walk = _Walk(omissions=omissions, pairs=set(), findings=[])
    walk.visit(canonical, public, public.__name__ if isinstance(public, type) else "root")
    return walk


@pytest.mark.parametrize(("canonical", "public"), _ENROLLED)
def test_every_reachable_mirror_keeps_its_canonical_inventory(canonical: object, public: object) -> None:
    assert _walk(canonical, public, _REVIEWED_OMISSIONS).findings == []


def test_the_walk_reaches_the_nested_pairs_it_guards() -> None:
    generation = _walk(*_ENROLLED[0], _REVIEWED_OMISSIONS)
    assert (DeclarationSummary, PublicDeclarationSummary) in generation.pairs
    assert len(generation.pairs) > 40


def test_every_production_projection_root_is_enrolled() -> None:
    enrolled = {(getattr(c, "__name__", ""), getattr(p, "__name__", "")) for c, p in _ENROLLED}
    called: set[tuple[str, str]] = set()
    for path in _APPLICATION_ROOT.parent.rglob("*.py"):
        if "tests" in path.parts or path.name == "public_mirror.py":
            continue
        source = path.read_text(encoding="utf-8")
        if "project_public_mirror(" not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "project_public_mirror"
            ):
                canonical, public = node.args[1], node.args[2]
                assert isinstance(canonical, ast.Name) and isinstance(public, ast.Name)
                called.add((canonical.id, public.id))
    assert called == enrolled


class _Child(BaseModel):
    kept: int
    added: int


class _PublicChild(BaseModel):
    kept: int


class _Parent(BaseModel):
    child: _Child | None
    children: tuple[_Child, ...]


class _PublicParent(BaseModel):
    child: _PublicChild | None
    children: tuple[_PublicChild, ...]


class _PublicInventing(BaseModel):
    kept: int
    added: int
    invented: int


class _PublicUnmatched(BaseModel):
    kept: int


class _Other(BaseModel):
    kept: int


class _UnionHolder(BaseModel):
    value: _Child | _Other


class _PublicUnionHolder(BaseModel):
    value: _PublicUnmatched


def test_the_walk_finds_a_nested_field_a_mirror_lost() -> None:
    assert _walk(_Parent, _PublicParent, {}).findings == [
        "_PublicParent.child: _Child -> _PublicChild missing=['added'] stale_omission=[] invented=[]"
    ]


def test_the_walk_admits_only_a_reviewed_omission_and_refuses_a_stale_one() -> None:
    assert _walk(_Child, _PublicChild, {_PublicChild: frozenset({"added"})}).findings == []
    assert _walk(_Other, _PublicChild, {_PublicChild: frozenset({"gone"})}).findings == [
        "_PublicChild: _Other -> _PublicChild missing=[] stale_omission=['gone'] invented=[]"
    ]


def test_the_walk_finds_an_invented_field_and_an_unmatched_union_arm() -> None:
    assert "invented=['invented']" in _walk(_Child, _PublicInventing, {}).findings[0]
    assert _walk(_UnionHolder, _PublicUnionHolder, {}).findings == [
        "_PublicUnionHolder.value: no canonical arm for _PublicUnmatched"
    ]
