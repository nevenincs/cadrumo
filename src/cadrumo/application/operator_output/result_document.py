"""The JSON document a command prints as the result of its envelope.

A command's result reaches a person through one serialisation and one
redaction pass. This function is that pass, for a caller that shows a person
what the command would print and has no envelope to emit. An installation act
and an operation answer with real values and never call it: hiding an
identifier belongs to the surface that prints, not to the reply.
"""

from __future__ import annotations

from pydantic import BaseModel

from ...core.errors.hierarchy import InternalInvariantError
from ...core.output_rendering import jsonable_output_payload, reveal_cli_identifiers_opt_in
from ...core.redaction.rules import redact_structured_for_cli_output
from ...core.type_guards import is_str_keyed_dict


def printed_result_document(result: BaseModel) -> dict[str, object]:
    """Serialise and redact ``result`` exactly as a command's JSON envelope does its result.

    Profile and bucket identifiers are hidden unless the installation opted in
    to revealing them, which is the setting a command consults.
    """
    document = redact_structured_for_cli_output(
        jsonable_output_payload(result), reveal_identifiers=reveal_cli_identifiers_opt_in()
    )
    if not is_str_keyed_dict(document):
        raise InternalInvariantError("a command result serialises to one JSON object")
    return document


__all__ = ["printed_result_document"]
