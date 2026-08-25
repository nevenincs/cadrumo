"""Conformance tests for the registered-error to authored-message source join."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from textwrap import dedent

import pytest

from dev.quality.cli_action_census import (
    AuthoredErrorMessageCensusError,
    RegisteredErrorCode,
    authored_error_message_join,
)
from dev.quality.cli_action_census_dispositions import (
    AuthoredMessageExclusion,
    DispositionValidationError,
    load_authored_message_exclusions,
    validate_authored_error_message_join,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write_source(root: Path, relative_path: str, source: str) -> None:
    """Write one minimal production module into a real temporary source tree."""
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(source).lstrip(), encoding="utf-8")


def _code(qualname: str, code: str = "REFUSED_TEST") -> RegisteredErrorCode:
    """Construct one injected registry fact without reimplementing registry lookup."""
    return RegisteredErrorCode(error_qualname=qualname, code=code)


def test_ast_join_assigns_a_direct_registered_constructor_to_its_one_live_code_owner(tmp_path: Path) -> None:
    """A direct constructor message is owned by the registry code, not prose or a path rule."""
    _write_source(
        tmp_path,
        "src/cadrumo/demo.py",
        """
        class DemoError(Exception):
            pass

        def produce() -> None:
            DemoError("authored detail")
        """,
    )

    join = authored_error_message_join(
        root=tmp_path,
        codes=(_code("cadrumo.demo.DemoError", "REFUSED_DEMO"),),
    )
    partition = validate_authored_error_message_join(join, ())

    assert len(partition.owned_sites) == 1
    (site,) = partition.owned_sites
    assert site.owner_qualnames == ("cadrumo.demo.DemoError",)
    assert site.message_expression == "'authored detail'"
    assert partition.clean_codes == ()
    assert partition.excluded_sites == ()


def test_join_rejects_an_unregistered_base_message_until_its_exact_site_is_excluded(tmp_path: Path) -> None:
    """An unowned direct CadrumoError message cannot disappear behind a broad exemption."""
    _write_source(
        tmp_path,
        "src/cadrumo/demo.py",
        """
        from cadrumo.core.errors import CadrumoError

        def produce() -> None:
            CadrumoError("unregistered base detail")
        """,
    )

    join = authored_error_message_join(root=tmp_path, codes=())
    (site,) = join.unresolved_sites
    exclusion = AuthoredMessageExclusion(fingerprint=site.fingerprint, reason="Synthetic root-base probe.")

    with pytest.raises(DispositionValidationError, match="0 exclusions instead of one"):
        validate_authored_error_message_join(join, ())
    partition = validate_authored_error_message_join(join, (exclusion,))
    assert partition.excluded_sites == (site,)
    with pytest.raises(DispositionValidationError, match="stale authored message exclusion"):
        validate_authored_error_message_join(join, (replace(exclusion, fingerprint="stale"),))


def test_join_rejects_a_message_constructor_reachable_from_multiple_registered_codes(tmp_path: Path) -> None:
    """A conditional alias cannot claim an arbitrary one of two live code owners."""
    _write_source(
        tmp_path,
        "src/cadrumo/demo.py",
        """
        class FirstError(Exception):
            pass

        class SecondError(Exception):
            pass

        def produce(enabled: bool) -> None:
            if enabled:
                selected = FirstError
            else:
                selected = SecondError
            selected("ambiguous detail")
        """,
    )

    join = authored_error_message_join(
        root=tmp_path,
        codes=(
            _code("cadrumo.demo.FirstError", "REFUSED_FIRST"),
            _code("cadrumo.demo.SecondError", "REFUSED_SECOND"),
        ),
    )

    assert len(join.multiply_owned_sites) == 1
    with pytest.raises(DispositionValidationError, match="2 registered-code owners"):
        validate_authored_error_message_join(join, ())


def test_ast_join_resolves_a_registered_error_through_nested_source_facade_reexports(tmp_path: Path) -> None:
    """A public-package import retains the private registered error owner through aliases."""
    _write_source(
        tmp_path,
        "src/cadrumo/_errors.py",
        """
        class FacadeError(Exception):
            pass
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/facade/_reexport.py",
        """
        from cadrumo._errors import FacadeError
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/facade/__init__.py",
        """
        from ._reexport import FacadeError
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/consumer.py",
        """
        from cadrumo.facade import FacadeError

        def produce() -> None:
            FacadeError("facade detail")
        """,
    )

    join = authored_error_message_join(
        root=tmp_path,
        codes=(_code("cadrumo._errors.FacadeError", "REFUSED_FACADE"),),
    )

    (site,) = join.singly_owned_sites
    assert site.owner_qualnames == ("cadrumo._errors.FacadeError",)


def test_join_fails_closed_when_a_facade_import_looks_like_a_registered_error_but_cannot_resolve(
    tmp_path: Path,
) -> None:
    """A broken public re-export cannot silently remove a registered constructor from the join."""
    _write_source(
        tmp_path,
        "src/cadrumo/_errors.py",
        """
        class FacadeError(Exception):
            pass
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/facade/__init__.py",
        """
        from ._cycle import FacadeError
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/facade/_cycle.py",
        """
        from . import FacadeError
        """,
    )
    _write_source(
        tmp_path,
        "src/cadrumo/consumer.py",
        """
        from cadrumo.facade import FacadeError

        def produce() -> None:
            FacadeError("unreachable detail")
        """,
    )

    with pytest.raises(AuthoredErrorMessageCensusError, match=r"facade import cadrumo\.facade\.FacadeError"):
        authored_error_message_join(
            root=tmp_path,
            codes=(_code("cadrumo._errors.FacadeError", "REFUSED_FACADE"),),
        )


def test_live_join_is_exhaustively_partitioned_by_the_current_registry_and_exact_ledger_exclusion() -> None:
    """A source or registry mutation changes the live join rather than clearing vacuously."""
    join = authored_error_message_join()
    partition = validate_authored_error_message_join(
        join,
        load_authored_message_exclusions(
            Path("dev/quality/cli_action_census_dispositions.toml"),
        ),
    )

    assert len(join.registered_codes) > 600
    assert len(partition.owned_sites) > 4_000
    assert not join.multiply_owned_sites
    assert len(partition.excluded_sites) == 1
    assert partition.excluded_sites[0].path == "src/cadrumo/core/errors/__init__.py"
    assert partition.excluded_sites[0].enclosing_symbol == "CadrumoError.__init__"
    assert any(
        site.path == "src/cadrumo/core/json_contract.py"
        and site.owner_qualnames == ("cadrumo.core.json_contract.OutputSchemaError",)
        for site in partition.owned_sites
    )
    assert sum(
        site.path == "src/cadrumo/adapters/persistence/profile/transactions.py"
        and site.callee == "LedgerStorageError"
        and site.owner_qualnames == ("cadrumo.domain.transactions._errors.LedgerStorageError",)
        for site in partition.owned_sites
    ) == 12
    assert len(partition.clean_codes) > 100


def test_whole_tree_join_fails_closed_when_one_module_cannot_be_parsed(tmp_path: Path) -> None:
    """A syntax failure cannot make an authored message site vanish from the audit."""
    _write_source(tmp_path, "src/cadrumo/invalid.py", "def missing(:\n")

    with pytest.raises(AuthoredErrorMessageCensusError, match=r"cannot parse src/cadrumo/invalid\.py"):
        authored_error_message_join(root=tmp_path, codes=())
