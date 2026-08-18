"""The CLI-path to schema-key projection has one home.

The documentation generator and the JSON-schema conformance gate both have to
answer "which result-schema key does this command emit?". They each carried
their own copy of the projection plus their own copy of the namespace policy,
so the generator could document one key while the gate enforced another --
a disagreement invisible until a reader followed the docs to a key that does
not exist.

The copies had already drifted in one respect: the generator hardcoded the
executable token while the gate read it from :data:`PRODUCT_IDENTITY`.
"""

from __future__ import annotations

import pytest

from cadrumo.core import PRODUCT_IDENTITY
from cadrumo.entrypoints.schema_surface import (
    APP_NAMESPACE_FLATTEN,
    APP_NAMESPACE_PASSTHROUGH,
    SCHEMA_KEY_BY_CLI_PATH,
    normalise_cli_path_to_schema_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_EXE = PRODUCT_IDENTITY.cli_executable


class TestProjection:
    def test_the_executable_token_is_dropped(self) -> None:
        assert normalise_cli_path_to_schema_key((_EXE, "config", "status")) == "config.status"

    def test_hyphens_become_underscores(self) -> None:
        assert normalise_cli_path_to_schema_key((_EXE, "app", "modelo", "support-matrix")) == ("modelo.support_matrix")

    @pytest.mark.parametrize("namespace", sorted(APP_NAMESPACE_FLATTEN))
    def test_flattened_namespaces_drop_the_app_prefix(self, namespace: str) -> None:
        assert normalise_cli_path_to_schema_key((_EXE, "app", namespace, "list")) == f"{namespace}.list"

    @pytest.mark.parametrize("namespace", sorted(APP_NAMESPACE_PASSTHROUGH))
    def test_passthrough_namespaces_keep_the_app_prefix(self, namespace: str) -> None:
        assert normalise_cli_path_to_schema_key((_EXE, "app", namespace, "pull")) == f"app.{namespace}.pull"

    def test_the_exception_table_applies_last(self) -> None:
        """A mapped path resolves to its pinned machine contract, not its CLI shape."""
        assert "config.profile.history" in SCHEMA_KEY_BY_CLI_PATH
        assert normalise_cli_path_to_schema_key((_EXE, "config", "profile", "history")) == ("config.bucket.history")

    def test_a_path_without_the_executable_token_is_left_intact(self) -> None:
        assert normalise_cli_path_to_schema_key(("config", "status")) == "config.status"


def test_both_consumers_resolve_through_the_same_callable() -> None:
    """Neither surface may re-derive the projection locally.

    Identity, not equality: a second implementation that happens to agree
    today is exactly the state this consolidation removed.
    """
    from dev.docs.cli_reference import _normalise_command_path as docs_normaliser

    from ..cli.tests.test_json_schema_conformance import (
        _normalise_command_path as gate_normaliser,
    )

    assert docs_normaliser is normalise_cli_path_to_schema_key
    assert gate_normaliser is normalise_cli_path_to_schema_key


def test_the_namespace_policy_has_no_second_copy() -> None:
    """The policy sets are consumed from here, not redeclared per surface."""
    import dev.docs.cli_reference as docs

    from ..cli.tests import test_json_schema_conformance as gate

    for module in (docs, gate):
        assert not hasattr(module, "_APP_NAMESPACE_FLATTEN"), module.__name__
        assert not hasattr(module, "_APP_NAMESPACE_PASSTHROUGH"), module.__name__
