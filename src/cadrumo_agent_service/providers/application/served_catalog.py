"""The provider catalog the service relays to its frontends: the agent's v1 document and the service's own changes.

The agent serves its catalog as a typed document whose schema it publishes; the service keeps a
byte-exact copy of that schema, pinned to the agent commit it came from, under
``_data/agent_api``. The service changes the document in four ways and declares only those here:
it stamps every lane with whether its models are downloaded to this computer, leaves out whether a
model is installed where nothing is downloaded or the local server was not read, rewrites the local
engine's lane health from the runtime manager's facts within the agent's own vocabulary, and wraps
the catalog the agent declares before it runs in a ``declared`` envelope. :func:`served_schema` is
the one statement of what a frontend receives: the pinned definitions with those changes applied.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from enum import StrEnum
from functools import cache
from importlib.resources import files
from typing import Any, Final, cast

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import best_match
from jsonschema.protocols import Validator

AGENT_SCHEMA_DIRECTORY: Final = ("_data", "agent_api")
"""Where the pinned agent schema and its pin record sit inside the service package."""

SERVED_CATALOG: Final = "ServedProviderCatalog"
"""The definition a running agent's relayed catalog is."""
SERVED_DECLARED_CATALOG: Final = "ServedDeclaredProviderCatalog"
"""The definition the catalog the agent declares before it runs is, in its envelope."""
SERVED_CATALOG_ANSWER: Final = "ServedCatalogAnswer"
"""The definition a catalog answer is: the running agent's catalog or the declared one."""

DECLARED_CATALOG_KIND: Final = "declared"
"""The envelope kind of a catalog the agent declares before it runs; a running agent's catalog carries no ``kind``."""

_AGENT_CATALOG: Final = "ProviderCatalogResponse"
_AGENT_LANE: Final = "ProviderCatalogRecordResponse"
_AGENT_MODEL: Final = "ProviderCatalogEntryResponse"
_AGENT_DECLARED_CATALOG: Final = "DeclaredProviderCatalog"
_AGENT_DECLARED_LANE: Final = "DeclaredLane"
_SERVED_LANE: Final = "ServedProviderLane"
_SERVED_MODEL: Final = "ServedCatalogModel"
_SERVED_DECLARED_DOCUMENT: Final = "ServedDeclaredCatalogDocument"
_SERVED_DECLARED_LANE: Final = "ServedDeclaredLane"
_MODEL_DOWNLOAD: Final = "ModelDownload"


class ModelDownload(StrEnum):
    """Whether a lane's models are downloaded to this computer, stamped by the service on every lane."""

    REQUIRED = "required"
    """A local engine's lane: the person downloads models to this computer for it."""
    NONE = "none"
    """A hosted lane: no model is downloaded, so no installation is offered for it."""


class PinnedSchemaError(RuntimeError):
    """The pinned agent schema is not the file its pin record names."""


def _pinned_bytes(name: str) -> bytes:
    return files("cadrumo_agent_service").joinpath(*AGENT_SCHEMA_DIRECTORY, name).read_bytes()


@cache
def pinned_agent_components() -> dict[str, Any]:
    """The agent's published component schemas, from the pinned file whose digest its pin record states."""
    pin = json.loads(_pinned_bytes("pin.json"))
    document = _pinned_bytes(pin["path"])
    if hashlib.sha256(document).hexdigest() != pin["sha256"]:
        raise PinnedSchemaError("the pinned agent schema does not match its pin record")
    schemas: dict[str, Any] = json.loads(document)["components"]["schemas"]
    return schemas


def _local_refs(node: object) -> object:
    """``node`` with its OpenAPI component references written as references between sibling definitions."""
    if isinstance(node, dict):
        mapping = cast(dict[str, object], node)
        return {
            key: (
                value.replace("#/components/schemas/", "#/$defs/")
                if key == "$ref" and isinstance(value, str)
                else _local_refs(value)
            )
            for key, value in mapping.items()
        }
    if isinstance(node, list):
        return [_local_refs(value) for value in cast(list[object], node)]
    return node


@cache
def agent_definitions() -> dict[str, Any]:
    """The agent's published component schemas as sibling definitions, keyed by name, references between them."""
    return cast(dict[str, Any], _local_refs(pinned_agent_components()))


def _ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/$defs/{name}"}


def _retarget(node: object, renames: dict[str, str]) -> object:
    """``node`` with each reference to a renamed definition pointing at its served form."""
    if isinstance(node, dict):
        mapping = cast(dict[str, object], node)
        reference = mapping.get("$ref")
        if isinstance(reference, str):
            name = reference.rsplit("/", 1)[-1]
            if name in renames:
                return {**mapping, "$ref": f"#/$defs/{renames[name]}"}
        return {key: _retarget(value, renames) for key, value in mapping.items()}
    if isinstance(node, list):
        return [_retarget(value, renames) for value in cast(list[object], node)]
    return node


def _stamped(lane: dict[str, Any], description: str) -> dict[str, Any]:
    """A lane definition with the service's required ``model_download`` stamp."""
    served = copy.deepcopy(lane)
    served["description"] = description
    served["properties"]["model_download"] = _ref(_MODEL_DOWNLOAD)
    served["required"] = [*served.get("required", ()), "model_download"]
    return served


@cache
def served_schema() -> dict[str, Any]:
    """Every definition a frontend's catalog answer is made of, keyed by name, references between them.

    The agent's definitions are kept as it publishes them; the lanes, models and catalogs the service
    changes are written as served definitions beside them, and the agent's names keep meaning what the
    agent serves.
    """
    agent = agent_definitions()
    defs: dict[str, Any] = dict(agent)
    model = copy.deepcopy(agent[_AGENT_MODEL])
    model["description"] = (
        "One model of a lane as the service relays it: `installed` is left out on a hosted lane, which "
        "downloads nothing, and on a local lane whose server nobody read."
    )
    model["required"] = [field for field in model.get("required", ()) if field != "installed"]
    defs[_SERVED_MODEL] = model
    defs[_SERVED_LANE] = _retarget(
        _stamped(
            agent[_AGENT_LANE],
            "One provider lane as the service relays it: the agent's lane, stamped with whether its models "
            "are downloaded to this computer.",
        ),
        {_AGENT_MODEL: _SERVED_MODEL},
    )
    lane_catalog = cast(dict[str, Any], _retarget(agent["ProviderLaneCatalogResponse"], {_AGENT_MODEL: _SERVED_MODEL}))
    lane_catalog["description"] = "A lane's model catalog as the service relays it."
    defs["ServedLaneCatalog"] = lane_catalog
    defs[_SERVED_LANE]["properties"]["catalog"] = _ref("ServedLaneCatalog")
    catalog = cast(dict[str, Any], _retarget(agent[_AGENT_CATALOG], {_AGENT_LANE: _SERVED_LANE}))
    catalog["description"] = "The running agent's provider catalog as the service relays it."
    defs[SERVED_CATALOG] = catalog
    defs[_SERVED_DECLARED_LANE] = _stamped(
        agent[_AGENT_DECLARED_LANE],
        "One lane the agent declares, as the service relays it: stamped with whether its models are "
        "downloaded to this computer.",
    )
    declared = cast(
        dict[str, Any], _retarget(agent[_AGENT_DECLARED_CATALOG], {_AGENT_DECLARED_LANE: _SERVED_DECLARED_LANE})
    )
    declared["description"] = "The catalog the agent declares before it runs, as the service relays it."
    defs[_SERVED_DECLARED_DOCUMENT] = declared
    defs[_MODEL_DOWNLOAD] = {
        "type": "string",
        "enum": [value.value for value in ModelDownload],
        "description": ModelDownload.__doc__,
    }
    defs[SERVED_DECLARED_CATALOG] = {
        "type": "object",
        "description": "The catalog the agent declares, in the envelope that tells it from a running agent's.",
        "properties": {
            "kind": {"const": DECLARED_CATALOG_KIND},
            "catalog": _ref(_SERVED_DECLARED_DOCUMENT),
        },
        "required": ["kind", "catalog"],
        "additionalProperties": False,
    }
    defs[SERVED_CATALOG_ANSWER] = {
        "description": "A provider catalog answer: the running agent's catalog, or the one it declares.",
        "anyOf": [_ref(SERVED_CATALOG), _ref(SERVED_DECLARED_CATALOG)],
    }
    return defs


def _is_date_time(value: object) -> bool:
    """An RFC 3339 date-time: a date and a time joined by ``T``, with its offset stated."""
    if not isinstance(value, str):
        return True
    if len(value) < 11 or value[10] not in "Tt":
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


@cache
def _validator() -> Validator:
    """The served answer's validator, checking the one format its definitions use."""
    formats = FormatChecker(formats=())
    formats.checks("date-time")(_is_date_time)
    schema = {"$defs": served_schema(), "$ref": f"#/$defs/{SERVED_CATALOG_ANSWER}"}
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=formats)


def catalog_nonconformance(answer: object) -> str | None:
    """Where ``answer`` departs from the served catalog answer, or ``None`` when it conforms.

    Only the place and the rule broken are said, never the value found there, so the words can be
    logged: a lane's reasons and names are the agent's text, not the service's.
    """
    error = best_match(_validator().iter_errors(answer))
    return None if error is None else f"{error.json_path} {error.validator}"


__all__ = [
    "AGENT_SCHEMA_DIRECTORY",
    "DECLARED_CATALOG_KIND",
    "SERVED_CATALOG",
    "SERVED_CATALOG_ANSWER",
    "SERVED_DECLARED_CATALOG",
    "ModelDownload",
    "PinnedSchemaError",
    "catalog_nonconformance",
    "pinned_agent_components",
    "served_schema",
]
