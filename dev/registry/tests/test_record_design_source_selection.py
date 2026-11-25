"""Real-binary tests for fail-closed record-design source selection."""

from __future__ import annotations

import ast
import inspect

import pytest

from cadrumo.core.hashing import hash_file
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from .. import maintenance_support
from ..compiler import corpus_catalogue
from ..maintenance_support import resolve_record_design_binary
from .authored_edition_support import source_first_exercise, source_with_sha256
from .catalogue_verification_support import catalogue_verification_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _design_epoch_sources(modelo_prefix: str) -> tuple[SourceReference, ...]:
    """Return the epoch-bearing record-design sources of one modelo that reach the support floor, oldest first."""
    floor = filing_year_envelope().floor
    return tuple(
        sorted(
            (
                source
                for source in catalogue_verification_catalogues().sources.values()
                if str(source.id).startswith(modelo_prefix)
                and source.record_design_epoch is not None
                and (source.applies_to is None or source.applies_to.year >= floor)
            ),
            key=lambda source: (source_first_exercise(source), str(source.id)),
        )
    )


def _source_epochs(modelo_prefix: str) -> tuple[tuple[str, int, str], ...]:
    return tuple(
        (str(source.id), source_first_exercise(source), str(source.record_design_epoch))
        for source in _design_epoch_sources(modelo_prefix)
    )


_M303_SOURCE_EPOCHS = _source_epochs("aeat-dr-303-")
_M390_SOURCE_EPOCHS = _source_epochs("aeat-dr-390-")
_M200_SOURCES = _design_epoch_sources("aeat-dr-200-")
_NEWEST_M303_REF, _NEWEST_M303_YEAR, _NEWEST_M303_EPOCH = _M303_SOURCE_EPOCHS[-1]
_NEWEST_M390_REF, _NEWEST_M390_YEAR, _NEWEST_M390_EPOCH = _M390_SOURCE_EPOCHS[-1]
_PREVIOUS_M390_EPOCH = _M390_SOURCE_EPOCHS[-2][2]
_NEWEST_M200_REF = str(_M200_SOURCES[-1].id)
_NEWEST_M200_YEAR = source_first_exercise(_M200_SOURCES[-1])
_NEWEST_M200_EPOCH = str(_M200_SOURCES[-1].record_design_epoch)
#: The newest closed design, which does not apply to the exercise after its own.
_CLOSED_M200 = next(source for source in reversed(_M200_SOURCES) if source.applies_to is not None)


@pytest.mark.parametrize(("source_ref", "filing_year", "design_epoch"), _M303_SOURCE_EPOCHS)
def test_resolves_each_explicit_hash_pinned_modelo_303_design_epoch(
    source_ref: str,
    filing_year: int,
    design_epoch: str,
) -> None:
    sources = catalogue_verification_catalogues().sources

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
    sources = catalogue_verification_catalogues().sources

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
    with pytest.raises(
        RegistryValidationError,
        match=f"declares design epoch '{_NEWEST_M390_EPOCH}', not requested '{_PREVIOUS_M390_EPOCH}'",
    ):
        resolve_record_design_binary(
            bundled_path(),
            catalogue_verification_catalogues().sources,
            source_ref=_NEWEST_M390_REF,
            filing_year=_NEWEST_M390_YEAR,
            design_epoch=_PREVIOUS_M390_EPOCH,
        )


def test_rejects_modelo_390_hash_drift() -> None:
    sources = catalogue_verification_catalogues().sources
    source = sources[_NEWEST_M390_REF]
    drifting_source = SourceReference.model_validate({**source.model_dump(mode="python"), "sha256": "0" * 64})

    with pytest.raises(RegistryValidationError, match="sha256 mismatch"):
        resolve_record_design_binary(
            bundled_path(),
            {str(drifting_source.id): drifting_source},
            source_ref=_NEWEST_M390_REF,
            filing_year=_NEWEST_M390_YEAR,
            design_epoch=_NEWEST_M390_EPOCH,
        )


def _m303_split_design_sources() -> tuple[tuple[int, str, str, str, str], ...]:
    """Derive each complete early/late pair from the record-design catalogue."""
    epochs_by_year: dict[int, dict[str, list[SourceReference]]] = {}
    for source in catalogue_verification_catalogues().sources.values():
        if not str(source.id).startswith("aeat-dr-303-") or source.record_design_epoch is None:
            continue
        year_text, separator, suffix = source.record_design_epoch.partition("-")
        if not separator or not year_text.isdecimal() or suffix not in {"early", "late"}:
            continue
        epochs_by_year.setdefault(int(year_text), {}).setdefault(suffix, []).append(source)

    pairs: list[tuple[int, str, str, str, str]] = []
    for filing_year, epochs in sorted(epochs_by_year.items()):
        if set(epochs) != {"early", "late"} or any(len(sources) != 1 for sources in epochs.values()):
            raise LookupError(f"Modelo 303 {filing_year}: split design epochs must have one early and one late source")
        (early,) = epochs["early"]
        (late,) = epochs["late"]
        if early.record_design_epoch is None or late.record_design_epoch is None:
            raise LookupError(f"Modelo 303 {filing_year}: split design source lost its declared epoch")
        pairs.append(
            (
                filing_year,
                str(early.id),
                early.record_design_epoch,
                str(late.id),
                late.record_design_epoch,
            )
        )
    if not pairs:
        raise LookupError("Modelo 303 source catalogue declares no complete split design epoch")
    return tuple(pairs)


_M303_SPLIT_DESIGN_SOURCES = _m303_split_design_sources()


@pytest.mark.parametrize(
    ("filing_year", "early_source_ref", "early_epoch", "late_source_ref", "late_epoch"),
    _M303_SPLIT_DESIGN_SOURCES,
)
def test_verifies_both_explicit_modelo_303_split_design_epochs_without_date_only_selection(
    filing_year: int,
    early_source_ref: str,
    early_epoch: str,
    late_source_ref: str,
    late_epoch: str,
) -> None:
    sources = catalogue_verification_catalogues().sources

    early = resolve_record_design_binary(
        bundled_path(),
        sources,
        source_ref=early_source_ref,
        filing_year=filing_year,
        design_epoch=early_epoch,
    )
    late = resolve_record_design_binary(
        bundled_path(),
        sources,
        source_ref=late_source_ref,
        filing_year=filing_year,
        design_epoch=late_epoch,
    )

    assert early.source.id != late.source.id
    assert early.source.record_design_epoch != late.source.record_design_epoch


@pytest.mark.parametrize(
    ("filing_year", "early_source_ref", "early_epoch", "late_source_ref", "late_epoch"),
    _M303_SPLIT_DESIGN_SOURCES,
)
def test_rejects_modelo_303_epoch_mismatch_before_reading_the_binary(
    filing_year: int,
    early_source_ref: str,
    early_epoch: str,
    late_source_ref: str,
    late_epoch: str,
) -> None:
    with pytest.raises(
        RegistryValidationError, match=f"declares design epoch '{late_epoch}', not requested '{early_epoch}'"
    ):
        resolve_record_design_binary(
            bundled_path(),
            catalogue_verification_catalogues().sources,
            source_ref=late_source_ref,
            filing_year=filing_year,
            design_epoch=early_epoch,
        )


def test_rejects_modelo_303_hash_drift() -> None:
    sources = catalogue_verification_catalogues().sources
    source = sources[_NEWEST_M303_REF]
    drifting_source = SourceReference.model_validate({**source.model_dump(mode="python"), "sha256": "0" * 64})

    with pytest.raises(RegistryValidationError, match="sha256 mismatch"):
        resolve_record_design_binary(
            bundled_path(),
            {str(drifting_source.id): drifting_source},
            source_ref=_NEWEST_M303_REF,
            filing_year=_NEWEST_M303_YEAR,
            design_epoch=_NEWEST_M303_EPOCH,
        )


def test_rejects_modelo_303_source_without_an_explicit_epoch() -> None:
    sources = catalogue_verification_catalogues().sources
    source = sources[_NEWEST_M303_REF]
    epochless_source = SourceReference.model_validate({**source.model_dump(mode="python"), "record_design_epoch": None})

    with pytest.raises(RegistryValidationError, match="does not declare a design epoch"):
        resolve_record_design_binary(
            bundled_path(),
            {str(epochless_source.id): epochless_source},
            source_ref=_NEWEST_M303_REF,
            filing_year=_NEWEST_M303_YEAR,
            design_epoch=_NEWEST_M303_EPOCH,
        )


def test_rejects_a_modelo_303_filename_instead_of_an_explicit_source_reference() -> None:
    sources = catalogue_verification_catalogues().sources
    source = sources[_NEWEST_M303_REF]

    with pytest.raises(RegistryValidationError, match="is not declared in the source catalogue"):
        resolve_record_design_binary(
            bundled_path(),
            sources,
            source_ref=source.corpus_path,
            filing_year=_NEWEST_M303_YEAR,
            design_epoch=_NEWEST_M303_EPOCH,
        )


def _catalogue_top_level_imports() -> tuple[set[tuple[int, str | None, str]], set[str]]:
    catalogue_tree = ast.parse(inspect.getsource(corpus_catalogue))
    top_level_imported_symbols = {
        (node.level, node.module, alias.name)
        for node in catalogue_tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    top_level_direct_imports = {
        alias.name for node in catalogue_tree.body if isinstance(node, ast.Import) for alias in node.names
    }
    return top_level_imported_symbols, top_level_direct_imports


def _resolver_imports_and_reached_names() -> tuple[set[tuple[int, str | None, str]], set[str], set[str], set[str]]:
    resolver_tree = ast.parse(inspect.getsource(maintenance_support.resolve_record_design_binary))
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
    return resolver_imports, resolver_globals, call_names, attribute_call_names


def test_record_design_selection_cannot_consult_registry_export_layouts() -> None:
    top_level_imported_symbols, top_level_direct_imports = _catalogue_top_level_imports()
    resolver_imports, resolver_globals, call_names, attribute_call_names = _resolver_imports_and_reached_names()

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
    # A parse that found nothing would satisfy the isolation claims vacuously.
    assert top_level_imported_symbols, "the catalogue module parsed to no imports"
    assert resolver_globals and call_names, "the resolver parsed to no names"
    assert not {name for name in top_level_direct_imports if "export" in name or "layout" in name}
    assert resolver_imports == set()
    # The resolver reaches no export-layout name through globals, calls or
    # attribute calls; it selects a design from its SOURCE alone.
    reached = {name.casefold() for name in (*resolver_globals, *call_names, *attribute_call_names)}
    assert not {name for name in reached if "export" in name or "layout" in name}, sorted(reached)


# The exercise of the hash-pinned official Modelo 200 design, read from its applicability.
_M200_PINNED_DESIGN_EXERCISE = source_first_exercise(
    source_with_sha256("92392cdb46d8e7c7f6e4e6477306570e15edfd64d5ea3e6d631e5cf847dd5509")
)


def test_resolves_the_hash_pinned_modelo_200_binary() -> None:
    year = _M200_PINNED_DESIGN_EXERCISE
    sources = catalogue_verification_catalogues().sources

    resolved = resolve_record_design_binary(
        bundled_path(),
        sources,
        source_ref=f"aeat-dr-200-{year}",
        filing_year=year,
        design_epoch=str(year),
    )

    assert resolved.source.id == f"aeat-dr-200-{year}"
    assert resolved.source.record_design_epoch == str(year)
    assert resolved.path.is_file()


def test_rejects_an_exact_design_that_does_not_apply_to_the_filing_year() -> None:
    after_closed = source_first_exercise(_CLOSED_M200) + 1
    with pytest.raises(RegistryValidationError, match=f"does not apply to filing year {after_closed}"):
        resolve_record_design_binary(
            bundled_path(),
            catalogue_verification_catalogues().sources,
            source_ref=str(_CLOSED_M200.id),
            filing_year=after_closed,
            design_epoch=str(_CLOSED_M200.record_design_epoch),
        )


def test_rejects_a_hash_drifting_selected_binary() -> None:
    sources = catalogue_verification_catalogues().sources
    source = sources[_NEWEST_M200_REF]
    drifting_source = SourceReference.model_validate(
        {**source.model_dump(mode="python"), "sha256": "0" * 64},
    )

    with pytest.raises(RegistryValidationError, match="sha256 mismatch"):
        resolve_record_design_binary(
            bundled_path(),
            {str(drifting_source.id): drifting_source},
            source_ref=_NEWEST_M200_REF,
            filing_year=_NEWEST_M200_YEAR,
            design_epoch=_NEWEST_M200_EPOCH,
        )


def test_rejects_a_selection_without_a_catalogue_epoch() -> None:
    """A source declaring no epoch is refused for THAT reason, not a mismatch.

    The subject is a real shipped source with its epoch stripped, following the
    sibling hash-drift test above, rather than a modelo pinned by id for
    happening to lack one. This test named ``aeat-dr-720``, which has since been
    given epoch ``2013``: the call still raised, so the test still passed, but on
    an epoch MISMATCH — a different branch from the one it exists to cover.
    """
    sources = catalogue_verification_catalogues().sources
    source = sources[_NEWEST_M200_REF]
    epochless = SourceReference.model_validate(
        {**source.model_dump(mode="python"), "record_design_epoch": None},
    )

    with pytest.raises(RegistryValidationError, match="does not declare a design epoch"):
        resolve_record_design_binary(
            bundled_path(),
            {str(epochless.id): epochless},
            source_ref=_NEWEST_M200_REF,
            filing_year=_NEWEST_M200_YEAR,
            design_epoch=_NEWEST_M200_EPOCH,
        )


def test_rejects_a_blank_requested_design_epoch() -> None:
    with pytest.raises(RegistryValidationError, match="requires a non-blank design epoch"):
        resolve_record_design_binary(
            bundled_path(),
            catalogue_verification_catalogues().sources,
            source_ref=_NEWEST_M200_REF,
            filing_year=_NEWEST_M200_YEAR,
            design_epoch="   ",
        )
