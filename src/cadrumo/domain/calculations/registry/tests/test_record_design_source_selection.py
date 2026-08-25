"""Real-binary tests for fail-closed record-design source selection."""

from __future__ import annotations

import ast
import inspect

import pytest

from .....core.hashing import hash_file
from .....core.resources import bundled_path
from .. import _corpus_catalogue
from .._corpus_catalogue import resolve_record_design_binary
from ..errors import RegistryValidationError
from .._schema import SourceReference
from ._catalogue_verification_support import _catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_M303_SOURCE_EPOCHS = (
    ("aeat-dr-303-2023", 2023, "2023"),
    ("aeat-dr-303-2024-early", 2024, "2024-early"),
    ("aeat-dr-303-2024-late", 2024, "2024-late"),
    ("aeat-dr-303-2025", 2025, "2025"),
    ("aeat-dr-303-2026", 2026, "2026"),
)
_M390_SOURCE_EPOCHS = (
    ("aeat-dr-390-2022", 2022, "2022"),
    ("aeat-dr-390-2023", 2023, "2023"),
    ("aeat-dr-390-2024", 2024, "2024"),
    ("aeat-dr-390-2025", 2025, "2025"),
)


@pytest.mark.parametrize(("source_ref", "filing_year", "design_epoch"), _M303_SOURCE_EPOCHS)
def test_resolves_each_explicit_hash_pinned_modelo_303_design_epoch(
    source_ref: str,
    filing_year: int,
    design_epoch: str,
) -> None:
    sources = _catalogues().sources

    resolved = resolve_record_design_binary(
        bundled_path(),
        sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=design_epoch,
    )

    assert resolved.source.id == source_ref
    assert resolved.source.record_design_epoch == design_epoch
    assert hash_file(resolved.path) == (resolved.source.sha256, resolved.source.bytes)


@pytest.mark.parametrize(("source_ref", "filing_year", "design_epoch"), _M390_SOURCE_EPOCHS)
def test_resolves_each_explicit_hash_pinned_modelo_390_design_epoch(
    source_ref: str,
    filing_year: int,
    design_epoch: str,
) -> None:
    """Each M390 binary selects only through its own epoch-bearing source entry."""
    sources = _catalogues().sources

    resolved = resolve_record_design_binary(
        bundled_path(),
        sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=design_epoch,
    )

    assert resolved.source.id == source_ref
    assert resolved.source.record_design_epoch == design_epoch
    assert hash_file(resolved.path) == (resolved.source.sha256, resolved.source.bytes)


def test_rejects_modelo_390_cross_epoch_selection_before_reading_the_binary() -> None:
    with pytest.raises(RegistryValidationError, match="declares design epoch '2025', not requested '2024'"):
        resolve_record_design_binary(
            bundled_path(),
            _catalogues().sources,
            source_ref="aeat-dr-390-2025",
            filing_year=2025,
            design_epoch="2024",
        )


def test_rejects_modelo_390_hash_drift() -> None:
    sources = _catalogues().sources
    source = sources["aeat-dr-390-2025"]
    drifting_source = SourceReference.model_validate({**source.model_dump(mode="python"), "sha256": "0" * 64})

    with pytest.raises(RegistryValidationError, match="sha256 mismatch"):
        resolve_record_design_binary(
            bundled_path(),
            {str(drifting_source.id): drifting_source},
            source_ref="aeat-dr-390-2025",
            filing_year=2025,
            design_epoch="2025",
        )


def test_verifies_both_explicit_modelo_303_2024_epochs_without_date_only_selection() -> None:
    sources = _catalogues().sources

    early = resolve_record_design_binary(
        bundled_path(),
        sources,
        source_ref="aeat-dr-303-2024-early",
        filing_year=2024,
        design_epoch="2024-early",
    )
    late = resolve_record_design_binary(
        bundled_path(),
        sources,
        source_ref="aeat-dr-303-2024-late",
        filing_year=2024,
        design_epoch="2024-late",
    )

    assert early.source.id != late.source.id
    assert early.source.record_design_epoch != late.source.record_design_epoch


def test_rejects_modelo_303_epoch_mismatch_before_reading_the_binary() -> None:
    with pytest.raises(RegistryValidationError, match="declares design epoch '2024-late', not requested '2024-early'"):
        resolve_record_design_binary(
            bundled_path(),
            _catalogues().sources,
            source_ref="aeat-dr-303-2024-late",
            filing_year=2024,
            design_epoch="2024-early",
        )


def test_rejects_modelo_303_hash_drift() -> None:
    sources = _catalogues().sources
    source = sources["aeat-dr-303-2025"]
    drifting_source = SourceReference.model_validate({**source.model_dump(mode="python"), "sha256": "0" * 64})

    with pytest.raises(RegistryValidationError, match="sha256 mismatch"):
        resolve_record_design_binary(
            bundled_path(),
            {str(drifting_source.id): drifting_source},
            source_ref="aeat-dr-303-2025",
            filing_year=2025,
            design_epoch="2025",
        )


def test_rejects_modelo_303_source_without_an_explicit_epoch() -> None:
    sources = _catalogues().sources
    source = sources["aeat-dr-303-2025"]
    epochless_source = SourceReference.model_validate({**source.model_dump(mode="python"), "record_design_epoch": None})

    with pytest.raises(RegistryValidationError, match="does not declare a design epoch"):
        resolve_record_design_binary(
            bundled_path(),
            {str(epochless_source.id): epochless_source},
            source_ref="aeat-dr-303-2025",
            filing_year=2025,
            design_epoch="2025",
        )


def test_rejects_a_modelo_303_filename_instead_of_an_explicit_source_reference() -> None:
    sources = _catalogues().sources
    source = sources["aeat-dr-303-2025"]

    with pytest.raises(RegistryValidationError, match="is not declared in the source catalogue"):
        resolve_record_design_binary(
            bundled_path(),
            sources,
            source_ref=source.corpus_path,
            filing_year=2025,
            design_epoch="2025",
        )


def test_record_design_selection_cannot_consult_registry_export_layouts() -> None:
    catalogue_tree = ast.parse(inspect.getsource(_corpus_catalogue))
    top_level_imported_symbols = {
        (node.level, node.module, alias.name)
        for node in catalogue_tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    top_level_direct_imports = {
        alias.name for node in catalogue_tree.body if isinstance(node, ast.Import) for alias in node.names
    }
    resolver_tree = ast.parse(inspect.getsource(_corpus_catalogue.resolve_record_design_binary))
    resolver = resolver_tree.body[0]
    assert isinstance(resolver, ast.FunctionDef)
    resolver_imports = {
        (node.level, node.module, alias.name)
        for node in ast.walk(resolver_tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    call_names = {
        node.func.id
        for node in ast.walk(resolver_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    attribute_call_names = {
        node.func.attr
        for node in ast.walk(resolver_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    parameter_names = {
        argument.arg
        for argument in (
            *resolver.args.posonlyargs,
            *resolver.args.args,
            *resolver.args.kwonlyargs,
        )
    }
    annotation_node_ids = {
        id(node)
        for annotation in (
            *(argument.annotation for argument in resolver.args.posonlyargs if argument.annotation is not None),
            *(argument.annotation for argument in resolver.args.args if argument.annotation is not None),
            *(argument.annotation for argument in resolver.args.kwonlyargs if argument.annotation is not None),
            resolver.returns,
        )
        if annotation is not None
        for node in ast.walk(annotation)
    }
    local_names = parameter_names | {
        node.id for node in ast.walk(resolver_tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    resolver_globals = {
        node.id
        for node in ast.walk(resolver_tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id not in local_names
        and id(node) not in annotation_node_ids
    }

    # Assert the PROPERTY this test is named for -- the selector must not be able
    # to consult an export layout -- rather than pinning the module's whole import
    # inventory. The inventory form failed on `typing.Final` and an intra-package
    # `_legal` constant, neither of which is an export layout: an unrelated import
    # reds it, so it trains everyone to update the constant and then detects
    # nothing.
    export_layout_modules = {
        module
        for _level, module, _symbol in top_level_imported_symbols
        if module is not None and ("export" in module or module == "_fixed_width_codec")
    }
    assert export_layout_modules == set(), (
        f"the record-design selector imports export-layout machinery: {sorted(export_layout_modules)}"
    )
    # ...and a floor, so an empty or mis-rooted parse cannot satisfy the above.
    assert {
        (1, "_errors", "RegistryValidationError"),
        (1, "_schema", "SourceReference"),
        (4, "core.hashing", "hash_file"),
        (4, "core.resources", "resolve_companion_binary"),
    } <= top_level_imported_symbols
    assert top_level_direct_imports == set()
    assert resolver_imports == set()
    assert resolver_globals == {"RegistryValidationError", "ResolvedRecordDesignBinary", "date", "verify_source_file"}
    assert call_names == {"RegistryValidationError", "ResolvedRecordDesignBinary", "date", "verify_source_file"}
    assert attribute_call_names == {"get", "strip"}


def test_resolves_the_hash_pinned_modelo_200_2025_binary() -> None:
    sources = _catalogues().sources

    resolved = resolve_record_design_binary(
        bundled_path(),
        sources,
        source_ref="aeat-dr-200-2025",
        filing_year=2025,
        design_epoch="2025",
    )

    assert resolved.source.id == "aeat-dr-200-2025"
    assert resolved.source.record_design_epoch == "2025"
    assert resolved.path.is_file()


def test_rejects_an_exact_design_that_does_not_apply_to_the_filing_year() -> None:
    with pytest.raises(RegistryValidationError, match="does not apply to filing year 2025"):
        resolve_record_design_binary(
            bundled_path(),
            _catalogues().sources,
            source_ref="aeat-dr-200-2024",
            filing_year=2025,
            design_epoch="2024",
        )


def test_rejects_a_hash_drifting_selected_binary() -> None:
    sources = _catalogues().sources
    source = sources["aeat-dr-200-2025"]
    drifting_source = SourceReference.model_validate(
        {**source.model_dump(mode="python"), "sha256": "0" * 64},
    )

    with pytest.raises(RegistryValidationError, match="sha256 mismatch"):
        resolve_record_design_binary(
            bundled_path(),
            {str(drifting_source.id): drifting_source},
            source_ref="aeat-dr-200-2025",
            filing_year=2025,
            design_epoch="2025",
        )


def test_rejects_a_selection_without_a_catalogue_epoch() -> None:
    """A source declaring no epoch is refused for THAT reason, not a mismatch.

    The subject is a real shipped source with its epoch stripped, following the
    sibling hash-drift test above, rather than a modelo pinned by id for
    happening to lack one. This test named ``aeat-dr-720``, which has since been
    given epoch ``2013``: the call still raised, so the test still passed, but on
    an epoch MISMATCH — a different branch from the one it exists to cover.
    """
    sources = _catalogues().sources
    source = sources["aeat-dr-200-2025"]
    epochless = SourceReference.model_validate(
        {**source.model_dump(mode="python"), "record_design_epoch": None},
    )

    with pytest.raises(RegistryValidationError, match="does not declare a design epoch"):
        resolve_record_design_binary(
            bundled_path(),
            {str(epochless.id): epochless},
            source_ref="aeat-dr-200-2025",
            filing_year=2025,
            design_epoch="2025",
        )


def test_rejects_a_blank_requested_design_epoch() -> None:
    with pytest.raises(RegistryValidationError, match="requires a non-blank design epoch"):
        resolve_record_design_binary(
            bundled_path(),
            _catalogues().sources,
            source_ref="aeat-dr-200-2025",
            filing_year=2025,
            design_epoch="   ",
        )
