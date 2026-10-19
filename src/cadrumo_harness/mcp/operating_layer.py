"""The harness operating layer as MCP serves it: the ``harness_load`` floor tool and its resources.

One authored source, the reviewed tree under ``cadrumo_harness/_data/agent``,
feeds both channels. ``harness_load`` is the floor every client that calls
tools receives: the whole operating-rule corpus, the skill catalogue with each
skill's ``applies_when`` predicate, and on request one skill's document, so a
client without resources still reaches every skill. The ``cadrumo://skill/{name}``
and ``cadrumo://rule/{name}`` resources serve the same documents to a client
that pulls resources.

Everything here is prompt material shipped in the wheel. It carries no profile
data, grants nothing and decides nothing: the runtime admits or refuses every
operation on its own evidence, whatever a rule or skill says. No persona ships,
so no persona is served.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources.abc import Traversable
from typing import Any, Final

from ..resources import iter_operator_rules, iter_skill_documents, iter_skill_metadata, operator_rules_text

_UTF_8 = "utf-8"
_MARKDOWN_SUFFIX = ".md"

_SKILL_URI_PREFIX: Final = "cadrumo://skill/"
_RULE_URI_PREFIX: Final = "cadrumo://rule/"
MARKDOWN_MIME_TYPE: Final = "text/markdown"

_UNKNOWN_SKILL: Final = "unknown_skill"
"""The refusal code of a ``harness_load`` call that names a skill no shipped document has."""


@dataclass(frozen=True, slots=True)
class OperatingResource:
    """One served operating-layer document, as a resource listing names it."""

    uri: str
    name: str
    description: str
    applies_when: dict[str, Any] | None
    """The skill's structured selection predicate; ``None`` for a rule."""
    document: Traversable


@dataclass(frozen=True, slots=True)
class OperatingTemplate:
    """One resource template: the URI pattern and what each resource it names holds."""

    uri_template: str
    name: str
    description: str


RESOURCE_TEMPLATES: Final = (
    OperatingTemplate(
        uri_template=f"{_SKILL_URI_PREFIX}{{name}}",
        name="skill",
        description=(
            "One workflow skill of the Cadrumo operator harness, by the name harness_load lists it under. "
            "A skill is guidance for operating the tools; it grants nothing"
        ),
    ),
    OperatingTemplate(
        uri_template=f"{_RULE_URI_PREFIX}{{name}}",
        name="rule",
        description=(
            "One operating rule of the Cadrumo operator harness, by the name of its document without .md. "
            "harness_load returns every rule at once"
        ),
    ),
)
"""Every template the server advertises, in the order it lists them."""


def _skills() -> dict[str, OperatingResource]:
    """Every shipped skill by name; the metadata loader has already matched each name to its directory."""
    return {
        metadata.name: OperatingResource(
            uri=f"{_SKILL_URI_PREFIX}{metadata.name}",
            name=metadata.name,
            description=metadata.description,
            applies_when=None if metadata.applies_when is None else metadata.applies_when.model_dump(mode="json"),
            document=document,
        )
        for metadata, document in zip(iter_skill_metadata(), iter_skill_documents(), strict=True)
    }


def _rules() -> dict[str, OperatingResource]:
    """Every shipped operating rule by the name of its document without the suffix."""
    rules: dict[str, OperatingResource] = {}
    for document in iter_operator_rules():
        name = document.name.removesuffix(_MARKDOWN_SUFFIX)
        rules[name] = OperatingResource(
            uri=f"{_RULE_URI_PREFIX}{name}",
            name=name,
            description=f"Operating rule {name} of the Cadrumo operator harness",
            applies_when=None,
            document=document,
        )
    return rules


def operating_resources() -> tuple[OperatingResource, ...]:
    """Every served document: the skills, then the rules, each ordered by name."""
    return (*_skills().values(), *_rules().values())


def read_operating_resource(uri: str) -> str | None:
    """Return the text of the document ``uri`` names, or ``None`` when it names none."""
    for prefix, documents in ((_SKILL_URI_PREFIX, _skills), (_RULE_URI_PREFIX, _rules)):
        if uri.startswith(prefix):
            served = documents().get(uri.removeprefix(prefix))
            return None if served is None else served.document.read_text(encoding=_UTF_8)
    return None


def harness_load(args: dict[str, Any]) -> dict[str, Any]:
    """Answer the floor: every operating rule, the skill catalogue and, when named, one skill's document."""
    skills = _skills()
    reply: dict[str, Any] = {
        "outcome": "loaded",
        "rules": operator_rules_text(),
        "skills": [
            {
                "name": skill.name,
                "description": skill.description,
                "resource": skill.uri,
                "applies_when": skill.applies_when,
            }
            for skill in skills.values()
        ],
    }
    requested = args.get("skill")
    if requested is None:
        return reply
    skill = skills.get(requested)
    if skill is None:
        return {"outcome": "refused", "code": _UNKNOWN_SKILL}
    reply["skill"] = {"name": skill.name, "resource": skill.uri, "text": skill.document.read_text(encoding=_UTF_8)}
    return reply


__all__ = [
    "MARKDOWN_MIME_TYPE",
    "RESOURCE_TEMPLATES",
    "OperatingResource",
    "OperatingTemplate",
    "harness_load",
    "operating_resources",
    "read_operating_resource",
]
