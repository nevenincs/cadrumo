"""A builder for context-invoked leaves whose handler and result live in named modules.

Command families name their handler and payload modules once, in a table keyed
by a short alias, so every lazily resolved edge is a whole dotted path that a
static reader can see. The tax CLI and the runtime executable each wrote the
same handler, schema and leaf construction around such a table; this builder
is that construction, parameterized by the table, the declaring package and
the family's profile-authentication posture.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from cadrumo_client.contracts.command_ports import CommandNodeKind, ProfileAuthenticationPosture

from .parameters import ArgumentSpec, OptionSpec
from .shared_contracts import DeferredTarget, LazyBinding, ResultSchemaSpec, SchemaState, translation_key
from .spec import CommandSpec, ExecutionPolicySpec, InvocationSpec

__all__ = ["ModuleLeafBuilder"]


@dataclass(frozen=True, slots=True)
class ModuleLeafBuilder:
    """Build ``ctx``-invoked leaf specs from aliases in a handler-module table.

    ``modules`` maps each alias to a whole module path, absolute or relative to
    ``package``. An unknown alias raises ``KeyError`` at spec-build time rather
    than failing lazily on first invocation.
    """

    modules: Mapping[str, str]
    package: str | None
    profile_authentication: ProfileAuthenticationPosture = ProfileAuthenticationPosture.NOT_APPLICABLE

    def target(self, module: str, name: str) -> DeferredTarget:
        """Return the deferred target ``name`` in the module aliased ``module``."""
        return DeferredTarget(self.modules[module], name, self.package)

    def leaf(
        self,
        key: str,
        parent: str,
        token: str,
        help_key: str,
        module: str,
        handler: str,
        schema_module: str,
        schema_name: str,
        policy: ExecutionPolicySpec,
        parameters: tuple[ArgumentSpec | OptionSpec, ...] = (),
        *,
        identity: str | None = None,
    ) -> CommandSpec:
        """Return one leaf spec; its identity defaults to ``key`` with dots for underscores."""
        return CommandSpec(
            key=key,
            parent_key=parent,
            token=token,
            kind=CommandNodeKind.LEAF,
            help_key=translation_key(help_key),
            short_help_key=None,
            invocation=InvocationSpec(context_parameter="ctx"),
            parameters=parameters,
            policy=policy,
            handler=LazyBinding.available(self.target(module, handler)),
            result_schema=ResultSchemaSpec(
                SchemaState.TARGET,
                target=self.target(schema_module, schema_name),
                identity=identity or key.replace("_", "."),
            ),
            profile_authentication=self.profile_authentication,
        )
