"""The one construction of a config-payload result schema.

Four command-spec modules defined an identical private helper for this, and a
fifth built the same object inline, so one concept had five spellings across one
package. They agreed, which is what made the duplication easy to keep: nothing
failed, and each new spec module copied whichever neighbour it was written
beside.

The risk was never that they disagreed today. It is that the payload module's
name, the schema state, or the deferred-target shape changes in one of them, and
the others keep working while meaning something slightly different.
"""

from __future__ import annotations

from ..command_spec import DeferredTarget, ResultSchemaSpec, SchemaState

__all__ = ["config_payload_schema"]

_CONFIG_PAYLOADS_MODULE = "cadrumo.entrypoints.cli.config_payloads"


def config_payload_schema(name: str, identity: str) -> ResultSchemaSpec:
    """Return the deferred result schema for a config payload type.

    ``name`` is the payload class in the config payloads module and ``identity``
    is the command identity the schema is declared under.
    """
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget(_CONFIG_PAYLOADS_MODULE, name),
        identity=identity,
    )
