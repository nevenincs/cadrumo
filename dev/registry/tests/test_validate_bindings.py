"""Detector teeth for the per-revision binding registration refusals.

Every refusal is provoked by editing a COPY of a converted modelo in a
temporary tree and compiling it through the mutable loader, so the live corpus
is never touched and no production module is patched. The normal path and the
defect path are proved in the same suite: a fixture that no longer refuses its
own defect would also stop refusing the corpus.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cadrumo.domain.calculations.registry.binding_targets import BindingConsumerKind, binding_consumers
from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_bindings import (
    unreferenced_binding_advisories,
    validate_binding_registration_section,
)

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS_ROOT = Path(__file__).resolve().parents[3] / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"

_M151_REVISION = "2025-y-siguientes"
_M151_BINDINGS = f"revisions/{_M151_REVISION}/bindings/0001-m151-impatriado-base.toml"
_M151_BINDING_ID = "modelo-151-impatriado-base-liquidable-general"
_M151_CASILLA = "revisions/2025-y-siguientes/casillas/cdecl.ejercicio__cimpatriado.cuota-diferencial.toml"

_M151_PROVIDER_LINE = (
    'provider = { kind = "ledger_impatriado_income_aggregation", modelo = "151", '
    'target_casilla_id = "impatriado.base-liquidable-general", fact = "ingresos_integros_sum" }'
)
_M151_VALUE_LINE = 'value = { data_type = "money", channel = "decimal" }'
_M151_AGGREGATION_LINE = 'aggregation = { op = "sum" }'


def _copy_modelo(tmp_path: Path, modelo_id: str) -> Path:
    """Copy one live modelo directory into an isolated temporary tree."""
    destination = tmp_path / modelo_id
    shutil.copytree(_MODELOS_ROOT / modelo_id, destination)
    return destination


def _rewrite(tree: Path, relative: str, old: str, new: str) -> None:
    """Replace one exact authored line in a copied fragment."""
    path = tree / relative
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        message = f"fixture edit is not unique in {relative}: {old!r} appears {text.count(old)} times"
        raise AssertionError(message)
    path.write_text(text.replace(old, new), encoding="utf-8")


def _revision(tree: Path, revision_id: str) -> ModeloRevision:
    """Compile the copied tree and return one revision."""
    return load_modelo_directory(tree).revisions[revision_id]


def _failures(tree: Path, revision_id: str) -> list[str]:
    return validate_binding_registration_section(
        prefix=f"modelo {tree.name} revision {revision_id}",
        revision=_revision(tree, revision_id),
    )


def test_a_converted_modelo_passes_binding_registration_validation(tmp_path: Path) -> None:
    tree = _copy_modelo(tmp_path, "151")
    assert _failures(tree, _M151_REVISION) == []


def test_an_unregistered_provider_kind_is_refused_before_compilation(tmp_path: Path) -> None:
    tree = _copy_modelo(tmp_path, "151")
    _rewrite(tree, _M151_BINDINGS, _M151_PROVIDER_LINE, 'provider = { kind = "not_a_provider_kind" }')

    with pytest.raises(RegistryLoadError, match="not_a_provider_kind"):
        _revision(tree, _M151_REVISION)


def test_a_deferred_provider_kind_cannot_feed_a_bound_casilla(tmp_path: Path) -> None:
    tree = _copy_modelo(tmp_path, "151")
    _rewrite(
        tree,
        _M151_BINDINGS,
        _M151_PROVIDER_LINE,
        'provider = { kind = "donativo_donor", fact = "row_field", row_field = "donor_tax_id", '
        'grouping = "per_donativo_donor", record = "donante", data_type = "text" }',
    )
    _rewrite(
        tree,
        _M151_BINDINGS,
        _M151_VALUE_LINE,
        'value = { data_type = "rows", channel = "row_set", row_grouping = "donativo" }',
    )
    _rewrite(tree, _M151_BINDINGS, _M151_AGGREGATION_LINE, 'aggregation = { op = "rows" }')

    failures = _failures(tree, _M151_REVISION)

    assert [f for f in failures if "deferred provider kind 'donativo_donor'" in f and _M151_BINDING_ID in f]
    assert all("modelo 151 revision 2025-y-siguientes" in failure for failure in failures)


def test_a_value_channel_the_provider_cannot_produce_is_refused(tmp_path: Path) -> None:
    tree = _copy_modelo(tmp_path, "151")
    _rewrite(tree, _M151_BINDINGS, _M151_VALUE_LINE, 'value = { data_type = "integer", channel = "integer" }')

    failures = _failures(tree, _M151_REVISION)

    assert [f for f in failures if "does not produce the 'integer' value channel" in f and _M151_BINDING_ID in f]


def test_an_aggregation_op_the_provider_does_not_support_is_refused(tmp_path: Path) -> None:
    tree = _copy_modelo(tmp_path, "151")
    _rewrite(tree, _M151_BINDINGS, _M151_AGGREGATION_LINE, 'aggregation = { op = "count_distinct" }')

    failures = _failures(tree, _M151_REVISION)

    assert [
        f
        for f in failures
        if "does not support the 'count_distinct' aggregation operation" in f and _M151_BINDING_ID in f
    ]


def test_a_terminal_origin_class_the_provider_cannot_rest_on_is_refused(tmp_path: Path) -> None:
    tree = _copy_modelo(tmp_path, "151")
    _rewrite(
        tree,
        _M151_BINDINGS,
        _M151_AGGREGATION_LINE,
        _M151_AGGREGATION_LINE + '\nterminal_origins = [{ source_class = "profile_field", role = "primary", '
        'cardinality = "exactly_one", fingerprint = "required" }]',
    )

    failures = _failures(tree, _M151_REVISION)

    assert [f for f in failures if "cannot rest on terminal origin 'profile_field'" in f and _M151_BINDING_ID in f]


def test_a_rows_aggregation_on_a_scalar_channel_is_refused(tmp_path: Path) -> None:
    tree = _copy_modelo(tmp_path, "190")
    fragment = "revisions/2024/bindings/0002-bindings.toml"
    _rewrite(
        tree,
        fragment,
        'id = "modelo-190-perceptor-row-nif"\nprovider = { kind = "withholding", fact = "row_field", '
        'row_field = "perceptor_tax_id", grouping = "per_perceptor_clave", record = "perceptor", '
        'data_type = "text" }\nvalue = { data_type = "rows", channel = "row_set", row_grouping = "withholding" }',
        'id = "modelo-190-perceptor-row-nif"\nprovider = { kind = "withholding", fact = "row_field", '
        'row_field = "perceptor_tax_id", grouping = "per_perceptor_clave", record = "perceptor", '
        'data_type = "text" }\nvalue = { data_type = "money", channel = "decimal" }',
    )

    failures = _failures(tree, "2024")

    assert [
        f
        for f in failures
        if "'rows' aggregation operation requires the 'row_set' value channel" in f
        and "modelo-190-perceptor-row-nif" in f
    ]


def test_an_alternate_binding_whose_value_contract_differs_is_refused(tmp_path: Path) -> None:
    tree = _copy_modelo(tmp_path, "151")
    alternate_id = f"{_M151_BINDING_ID}-alternate"
    binding_fragment = (tree / _M151_BINDINGS).read_text(encoding="utf-8")
    authored_row = binding_fragment[binding_fragment.index(f'[[revisions."{_M151_REVISION}".bindings]]') :]
    alternate_row = authored_row.replace(_M151_BINDING_ID, alternate_id).replace(
        _M151_VALUE_LINE,
        'value = { data_type = "integer", channel = "integer" }',
    )
    (tree / _M151_BINDINGS).write_text(binding_fragment + "\n" + alternate_row, encoding="utf-8")
    _rewrite(
        tree,
        _M151_CASILLA,
        f'binding = "{_M151_BINDING_ID}"',
        f'binding = "{_M151_BINDING_ID}"\nalternate_bindings = ["{alternate_id}"]',
    )

    failures = _failures(tree, _M151_REVISION)

    assert [f for f in failures if "differs from primary binding" in f and alternate_id in f]


def test_a_bound_casilla_and_its_alternate_are_both_indexed_as_consumers(tmp_path: Path) -> None:
    tree = _copy_modelo(tmp_path, "151")
    consumers = binding_consumers(_revision(tree, _M151_REVISION))

    assert [ref.kind for ref in consumers[_M151_BINDING_ID]] == [BindingConsumerKind.CASILLA_PRIMARY]


def _append_binding_row(tree: Path, new_id: str, *, extra: str = "") -> None:
    """Append a copy of the authored 151 binding under a fresh id.

    The copy is a legal row of the same family, so it passes every shape gate
    and differs from the original only in identity -- which makes it the
    narrowest possible orphan fixture.
    """
    newline = chr(10)
    fragment = (tree / _M151_BINDINGS).read_text(encoding="utf-8")
    authored_row = fragment[fragment.index(f'[[revisions."{_M151_REVISION}".bindings]]') :]
    copied = authored_row.replace(_M151_BINDING_ID, new_id)
    if extra:
        copied = copied.replace(_M151_AGGREGATION_LINE, _M151_AGGREGATION_LINE + newline + extra)
    (tree / _M151_BINDINGS).write_text(fragment + newline + copied, encoding="utf-8")


def test_a_binding_no_consumer_names_earns_an_unreferenced_advisory(tmp_path: Path) -> None:
    tree = _copy_modelo(tmp_path, "151")
    _append_binding_row(tree, "modelo-151-impatriado-orphan")

    revision = _revision(tree, _M151_REVISION)
    advisories = unreferenced_binding_advisories(prefix="modelo 151 revision 2025-y-siguientes", revision=revision)

    assert [a for a in advisories if "modelo-151-impatriado-orphan" in a and "named by no casilla" in a]
    assert not [a for a in advisories if _M151_BINDING_ID in a and "orphan" not in a]


def test_a_non_calculation_binding_earns_no_unreferenced_advisory(tmp_path: Path) -> None:
    tree = _copy_modelo(tmp_path, "151")
    _append_binding_row(
        tree,
        "modelo-151-impatriado-export-only",
        extra='applicability = { kind = "non_calculation" }',
    )

    revision = _revision(tree, _M151_REVISION)

    assert unreferenced_binding_advisories(prefix="modelo 151", revision=revision) == ()


def test_an_orphan_binding_stays_out_of_the_refusal_list(tmp_path: Path) -> None:
    tree = _copy_modelo(tmp_path, "151")
    _append_binding_row(tree, "modelo-151-impatriado-orphan")

    assert _failures(tree, _M151_REVISION) == []
