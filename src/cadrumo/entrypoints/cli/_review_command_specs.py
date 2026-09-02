"""Import-light command authority for the review family."""

from __future__ import annotations

from .command_spec import (
    ArgumentSpec,
    CommandSpec,
    CommandWriteRoute,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
)
from .command_spec import translation_key as _key

_METADATA = ExecutionPolicySpec(frozenset({"state-free"}), frozenset({"none"}), "metadata", CommandWriteRoute.NONE)
_READ = ExecutionPolicySpec(frozenset({"encrypted-facts"}), frozenset({"none"}), "local-io", CommandWriteRoute.NONE)
_STR = ValueContract(DeferredTarget("builtins", "str"))
_FLOAT = ValueContract(DeferredTarget("builtins", "float"))
_BOOL = ValueContract(DeferredTarget("builtins", "bool"))
_LANG = ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage"))
_STATE = ValueContract(
    DeferredTarget("cadrumo.application.review.enums", "ReviewState"),
    parser=DeferredTarget("cadrumo.entrypoints.cli._review", "parse_review_state"),
)


def _option(
    name: str,
    declarations: tuple[str, ...],
    value: ValueContract,
    help_key: str,
    *,
    default: str | int | float | bool | tuple[str, ...] | None = None,
    multiple: bool = False,
) -> OptionSpec:
    parameter_default = ParameterDefault.value("pending" if name == "state" else default)
    return OptionSpec(
        name,
        declarations,
        value,
        parameter_default,
        _key(help_key),
        metavar="pending|all" if name == "state" else None,
        multiple=multiple,
    )


REVIEW_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_review",
        "app",
        "review",
        "group",
        _key("cli.review.app_help"),
        None,
        InvocationSpec(no_args_is_help=True),
        (),
        _METADATA,
        None,
        ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "app_review_queue",
        "app_review",
        "queue",
        "leaf",
        _key("cli.review.queue.help"),
        None,
        InvocationSpec(context_parameter="ctx"),
        (
            _option("kinds", ("--kind",), _STR, "cli.review.queue.kind_help", default=(), multiple=True),
            _option(
                "source_kinds", ("--source-kind",), _STR, "cli.review.queue.source_kind_help", default=(), multiple=True
            ),
            _option("state", ("--state",), _STATE, "cli.review.queue.state_help"),
            _option("modelo", ("--modelo",), _STR, "cli.review.queue.modelo_help"),
            _option("confidence_below", ("--confidence-below",), _FLOAT, "cli.review.queue.confidence_below_help"),
            _option("explain", ("--explain",), _BOOL, "cli.review.queue.explain_help", default=False),
            _option(
                "output_language",
                ("--output-language", "--language"),
                _LANG,
                "cli.config.auth.output_language_help",
            ),
        ),
        _READ,
        LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._review", "review_queue")),
        ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._review_payloads", "ReviewQueueResult"),
            identity="app.review.queue",
        ),
    ),
    CommandSpec(
        "app_review_view",
        "app_review",
        "view",
        "leaf",
        _key("cli.review.show.help"),
        None,
        InvocationSpec(context_parameter="ctx"),
        (
            ArgumentSpec("item_id", _STR, ParameterDefault.required(), _key("cli.review.show.id_help")),
            _option("explain", ("--explain",), _BOOL, "cli.review.show.explain_help", default=False),
            _option(
                "output_language",
                ("--output-language", "--language"),
                _LANG,
                "cli.config.auth.output_language_help",
            ),
        ),
        _READ,
        LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._review", "review_view")),
        ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._review_payloads", "ReviewViewResult"),
            identity="app.review.view",
        ),
    ),
)

__all__ = ["REVIEW_COMMAND_SPECS"]
