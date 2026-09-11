"""Import-light command authority for the review family."""

from __future__ import annotations

from .command_spec import (
    FLAG_VALUE,
    TEXT_VALUE,
    ArgumentSpec,
    CommandNodeKind,
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
_FLOAT = ValueContract(DeferredTarget("builtins", "float"))
_LANG = ValueContract(DeferredTarget("...core.external_constants", "OutputLanguage", __package__))
_STATE = ValueContract(
    DeferredTarget("...application.review.enums", "ReviewState", __package__),
    parser=DeferredTarget("._review", "parse_review_state", __package__),
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
        CommandNodeKind.GROUP,
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
        CommandNodeKind.LEAF,
        _key("cli.review.queue.help"),
        None,
        InvocationSpec(context_parameter="ctx"),
        (
            _option("kinds", ("--kind",), TEXT_VALUE, "cli.review.queue.kind_help", default=(), multiple=True),
            _option(
                "source_kinds",
                ("--source-kind",),
                TEXT_VALUE,
                "cli.review.queue.source_kind_help",
                default=(),
                multiple=True,
            ),
            _option("state", ("--state",), _STATE, "cli.review.queue.state_help"),
            _option("modelo", ("--modelo",), TEXT_VALUE, "cli.review.queue.modelo_help"),
            _option("confidence_below", ("--confidence-below",), _FLOAT, "cli.review.queue.confidence_below_help"),
            _option("explain", ("--explain",), FLAG_VALUE, "cli.review.queue.explain_help", default=False),
            _option(
                "output_language",
                ("--output-language", "--language"),
                _LANG,
                "cli.config.auth.output_language_help",
            ),
        ),
        _READ,
        LazyBinding.available(DeferredTarget("._review", "review_queue", __package__)),
        ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("._review_payloads", "ReviewQueueResult", __package__),
            identity="app.review.queue",
        ),
    ),
    CommandSpec(
        "app_review_view",
        "app_review",
        "view",
        CommandNodeKind.LEAF,
        _key("cli.review.show.help"),
        None,
        InvocationSpec(context_parameter="ctx"),
        (
            ArgumentSpec("item_id", TEXT_VALUE, ParameterDefault.required(), _key("cli.review.show.id_help")),
            _option("explain", ("--explain",), FLAG_VALUE, "cli.review.show.explain_help", default=False),
            _option(
                "output_language",
                ("--output-language", "--language"),
                _LANG,
                "cli.config.auth.output_language_help",
            ),
        ),
        _READ,
        LazyBinding.available(DeferredTarget("._review", "review_view", __package__)),
        ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("._review_payloads", "ReviewViewResult", __package__),
            identity="app.review.view",
        ),
    ),
)

__all__ = ["REVIEW_COMMAND_SPECS"]
