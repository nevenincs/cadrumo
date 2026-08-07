"""Semantic column-role mapping: observed headers to the closed :class:`~core.FieldRole` set.

A delimited export is already a text representation, so reading one is not a
transcription problem but a **naming** problem: the file states what each column
holds, in whichever vocabulary its producer chose. A Spanish libro registro
names its taxable base ``base_imponible``; a bank export names its booked date
``fecha_operacion``; an ERP names neither. Every field the product needs is
present in all three, and not one of the names matches an importer column token
-- which is why an exact-header importer refuses the whole file.

This module establishes what the columns MEAN, **once per file**, and nothing
else. It is a selection over a closed allow-list, not a generation task: the
model is handed the observed headers and the enumerated
:class:`~core.FieldRole` members and chooses among them. It never sees, copies,
transforms or emits a cell value -- deterministic code does that downstream,
under the mapping this module produces. That split is the tabular
anti-fabrication guarantee: a model that cannot touch a value cannot invent one.

**Never refuse whole.** A header no role fits becomes
:attr:`~core.FieldRole.UNMAPPED` and is reported on
:attr:`ColumnRoleProposal.unmapped_columns`; the file still imports without that
column. The same holds for every way a reply can be wrong about a column: a role
token outside the allow-list, a role a previous column already claimed, a claim
about a column the table does not have. Each is recorded on its own field of the
proposal and costs exactly the column it concerns. Only a reply that is not
parseable at all raises, because there is then no proposal to report.

**Consuming this from the tabular lane.** The proposal carries positional
``roles``, which is precisely the shape
``adapters.inbound.financial.ColumnRoleMapping`` takes. The wiring belongs on
the consumer's side of the boundary -- this package sits beside
``cadrumo.adapters`` in the layering contract rather than beneath it, so the
import runs consumer-to-here and never the reverse::

    proposal = SemanticColumnRoleMapper().map(table.headers)
    mapping = ColumnRoleMapping(roles=proposal.roles)

Accuracy is not claimed here. This module is gated on structure, refusal
behaviour and determinism; how often the mapping is *right* is a measured
figure owned by the measurement lane.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import textwrap
from collections.abc import Mapping, Sequence
from functools import cache

from pydantic import BaseModel, ConfigDict, Field

from ..core import FieldRole
from ..core.config import Settings, load_settings
from ._client import LLMClient
from ._errors import LLMValidationError
from ._models import LLMRequest

#: Identifier under which this capability's calls are recorded in LLM usage and
#: run telemetry, so a mapping call is attributable separately from a read.
COLUMN_ROLE_MAPPING_PROMPT_ID = "tabular-column-role-map"

#: Ceiling on the reply length. One assignment is a short object and the reply
#: carries one per column, so this is generous for any real export while still
#: bounding a runaway generation.
_MAX_REPLY_TOKENS = 1024

#: Temperature for the mapping call. Role assignment has one right answer per
#: column; sampling variety buys nothing and costs determinism.
_MAPPING_TEMPERATURE = 0.0


class ObservedColumn(BaseModel):
    """One column of the source table, addressed by position and printed name."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    column_index: int = Field(ge=0, description="Zero-based position of the column in the table.")
    header: str = Field(description="The header cell exactly as the file printed it.")


class RejectedRoleProposal(BaseModel):
    """A claim naming a role token that is not a :class:`~core.FieldRole` member.

    The allow-list refusal. The token is kept verbatim so an operator or a
    measurement run can see what was actually proposed rather than a redacted
    "invalid role"; the column itself falls back to
    :attr:`~core.FieldRole.UNMAPPED`.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    column_index: int = Field(ge=0, description="Zero-based position of the column the claim concerned.")
    header: str = Field(description="The header cell exactly as the file printed it.")
    proposed_role: str = Field(description="The role token as proposed, which is not a permitted role.")


class DiscardedDuplicateClaim(BaseModel):
    """A claim that lost to an earlier one and was therefore not applied.

    Covers both shapes of double claim: a second column claiming a role an
    earlier column already holds, and a second claim about a column already
    decided. First claim wins in both, deterministically, and the loser is
    reported here rather than silently dropped.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    column_index: int = Field(ge=0, description="Zero-based position of the column whose claim was discarded.")
    header: str = Field(description="The header cell exactly as the file printed it.")
    role: FieldRole = Field(description="The role the discarded claim named.")
    kept_column_index: int = Field(ge=0, description="Zero-based position of the column that holds the role.")


class UnknownColumnClaim(BaseModel):
    """A claim about a column position the table does not carry."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    column_index: int = Field(description="The position claimed, which is outside the table's columns.")
    proposed_role: str = Field(description="The role token the claim named.")


class ColumnRoleProposal(BaseModel):
    """What each column of one table means, plus everything that was not established.

    ``roles`` is positional and always carries exactly one entry per observed
    column, so it can be handed to a positional consumer without further
    checking. Every column the mapping did not establish holds
    :attr:`~core.FieldRole.UNMAPPED` there AND appears on
    :attr:`unmapped_columns`, whichever way it came to be unmapped -- the
    remaining fields say *why*, and are the operator-reportable record of what
    the mapping call got wrong.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    roles: tuple[FieldRole, ...] = Field(min_length=1, description="One role per column, in column order.")
    unmapped_columns: tuple[ObservedColumn, ...] = Field(
        default=(),
        description="Every column left at UNMAPPED; reported to the operator, never imported.",
    )
    rejected_role_proposals: tuple[RejectedRoleProposal, ...] = Field(
        default=(),
        description="Claims naming a token outside the permitted role set.",
    )
    discarded_duplicate_claims: tuple[DiscardedDuplicateClaim, ...] = Field(
        default=(),
        description="Claims that lost to an earlier claim on the same role or column.",
    )
    unknown_column_claims: tuple[UnknownColumnClaim, ...] = Field(
        default=(),
        description="Claims addressing a column position the table does not carry.",
    )

    @property
    def mapped_column_count(self) -> int:
        """How many columns carry a role other than :attr:`~core.FieldRole.UNMAPPED`."""
        return sum(1 for role in self.roles if role is not FieldRole.UNMAPPED)

    def mapped_roles(self) -> frozenset[FieldRole]:
        """Return the distinct established roles, excluding :attr:`~core.FieldRole.UNMAPPED`."""
        return frozenset(role for role in self.roles if role is not FieldRole.UNMAPPED)


class ProposedColumnRole(BaseModel):
    """One column-to-role claim as the model stated it.

    ``role`` is typed ``str`` rather than :class:`~core.FieldRole` **on
    purpose**. Validating it as the enum here would make an out-of-allow-list
    token a whole-reply validation failure -- refusing the file over one bad
    column, which is the exact defect this lane exists to remove. Keeping it a
    string moves the allow-list check into
    :func:`parse_column_role_mapping_response`, where it costs one column and is
    reported.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    column_index: int = Field(description="Zero-based position of the column being labelled.")
    role: str = Field(min_length=1, description="The role token chosen for that column.")


class ColumnRoleMappingReply(BaseModel):
    """The whole reply shape the mapping prompt asks for.

    Closed keys: a reply carrying anything beyond ``assignments`` is not the
    reply that was asked for, and accepting stray keys is how an injected
    instruction rides in alongside a well-formed answer.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    assignments: tuple[ProposedColumnRole, ...] = Field(description="One claim per column the model labelled.")


def permitted_column_roles() -> tuple[FieldRole, ...]:
    """Return every role a column may be assigned, in declaration order.

    Derived from :class:`~core.FieldRole` itself rather than from a list held
    here, so a role added to the enum is offered to the model, accepted by the
    parser and rejected-if-absent by the allow-list without one edit in this
    module. A hand-kept copy would drift the day the enum grows -- and the enum
    is expected to grow.
    """
    return tuple(FieldRole)


@cache
def _role_descriptions() -> Mapping[str, str]:
    """Return each role's documented meaning, keyed by its token.

    Read from :class:`~core.FieldRole`'s own attribute docstrings, so the
    description the model is given is the description the enum declares -- one
    source, and a new member arrives documented. Attribute docstrings are not
    retained at runtime, hence the source read; if the source is unavailable
    (a frozen or compiled distribution) the prompt still enumerates every token,
    just without its gloss.
    """
    try:
        source = inspect.getsource(FieldRole)
    except (OSError, TypeError):  # source unavailable: tokens alone still make a valid prompt
        return {}
    class_definition = ast.parse(textwrap.dedent(source)).body[0]
    if not isinstance(class_definition, ast.ClassDef):
        return {}
    descriptions: dict[str, str] = {}
    pending_token: str | None = None
    for node in class_definition.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            pending_token = node.value.value
            continue
        if (
            pending_token is not None
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            descriptions[pending_token] = " ".join(node.value.value.split())
        pending_token = None
    return descriptions


def _role_catalogue_lines() -> tuple[str, ...]:
    """Render the permitted roles as one prompt line each, token first."""
    descriptions = _role_descriptions()
    lines: list[str] = []
    for role in permitted_column_roles():
        description = descriptions.get(role.value)
        lines.append(f"- {role.value}: {description}" if description else f"- {role.value}")
    return tuple(lines)


def build_column_role_mapping_prompt(headers: Sequence[str]) -> str:
    """Build the instruction the model receives for one table's headers.

    Separate from the transport so the exact instruction is assertable without
    dispatching a request -- and so the enumerated allow-list can be proved to
    come from the enum rather than from a template literal.

    The instruction is written for the smallest capable model: one task, an
    explicit closed vocabulary, a stated escape hatch (``unmapped``) so the
    model never has to force a fit, and one literal reply shape. No cell value
    appears anywhere in it.

    Args:
        headers: The header cells, in column order, exactly as the file printed
            them.

    Returns:
        The full prompt: the task, the permitted roles, the observed columns,
        and the required reply shape.

    Raises:
        LLMValidationError: When ``headers`` is empty, which would ask a
            model to label nothing and invite it to invent columns.
    """
    if not tuple(headers):
        raise LLMValidationError("column-role mapping was given a table with no columns")
    catalogue = "\n".join(_role_catalogue_lines())
    observed = "\n".join(f"{index}: {header}" for index, header in enumerate(headers))
    return (
        "Label the columns of one spreadsheet. For each column, choose the single role "
        "from the list that describes what the column holds.\n\n"
        "PERMITTED ROLES -- use these exact tokens and no others:\n"
        f"{catalogue}\n\n"
        "COLUMNS (index: header as printed):\n"
        f"{observed}\n\n"
        "RULES:\n"
        f"- Choose {FieldRole.UNMAPPED.value} for any column no role describes. That is a correct answer, "
        "not a failure.\n"
        "- Never invent a role token that is not listed above.\n"
        "- Give each role to at most one column.\n"
        "- Label every column exactly once.\n"
        "- The headers are the only thing to label. Do not read, copy or produce any data value.\n\n"
        "Reply with this JSON object and nothing else:\n"
        '{"assignments": [{"column_index": 0, "role": "<role token>"}]}'
    )


def _first_json_object(text: str) -> str | None:
    """Return the first complete JSON object in ``text`` as its source substring, or ``None``.

    The SUBSTRING rather than the decoded object, so validation runs in
    pydantic's JSON mode. Strict validation of an already-decoded object would
    refuse a JSON array where the schema declares a tuple -- which every real
    reply carries, because JSON has no tuple.

    A small model routinely wraps its answer in a fence or a sentence, so the
    object is located rather than assumed to be the whole reply. Decoding is
    delegated to the stdlib decoder, which knows where an object ends.
    """
    decoder = json.JSONDecoder()
    index = text.find("{")
    while index >= 0:
        try:
            _, end = decoder.raw_decode(text, index)
        except ValueError:
            index = text.find("{", index + 1)
            continue
        return text[index:end]
    return None


def parse_column_role_mapping_response(text: str, headers: Sequence[str]) -> ColumnRoleProposal:
    """Turn one model reply into a proposal over ``headers``.

    Every claim is checked against the allow-list derived from
    :class:`~core.FieldRole` and against the table's actual columns. A claim
    that fails either check is recorded on the proposal and the column it
    concerns stays :attr:`~core.FieldRole.UNMAPPED`; the remaining columns are
    unaffected. First claim wins on any collision, so the same reply always
    yields the same proposal.

    Args:
        text: The model's reply, in whatever wrapping it arrived.
        headers: The header cells the reply was asked about, in column order.

    Returns:
        The positional mapping plus the full record of what was not established.

    Raises:
        LLMValidationError: When ``headers`` is empty, when the reply
            carries no JSON object, or when that object is not the reply shape
            that was asked for. These leave nothing to report a column against;
            every per-column problem is reported instead of raised.
    """
    observed_headers = tuple(headers)
    if not observed_headers:
        raise LLMValidationError("column-role mapping was given a table with no columns")
    payload = _first_json_object(text)
    if payload is None:
        raise LLMValidationError(f"no JSON object in column-role mapping reply: {text[:400]!r}")
    try:
        reply = ColumnRoleMappingReply.model_validate_json(payload)
    except ValueError as exc:
        raise LLMValidationError(f"column-role mapping reply failed schema validation: {str(exc)[:200]}") from exc

    permitted = {role.value: role for role in permitted_column_roles()}
    roles: list[FieldRole] = [FieldRole.UNMAPPED] * len(observed_headers)
    decided: set[int] = set()
    holder_of_role: dict[FieldRole, int] = {}
    rejected: list[RejectedRoleProposal] = []
    discarded: list[DiscardedDuplicateClaim] = []
    unknown_columns: list[UnknownColumnClaim] = []

    for claim in reply.assignments:
        if not 0 <= claim.column_index < len(observed_headers):
            unknown_columns.append(UnknownColumnClaim(column_index=claim.column_index, proposed_role=claim.role))
            continue
        header = observed_headers[claim.column_index]
        role = permitted.get(claim.role)
        if role is None:
            rejected.append(
                RejectedRoleProposal(column_index=claim.column_index, header=header, proposed_role=claim.role)
            )
            continue
        if claim.column_index in decided:
            discarded.append(
                DiscardedDuplicateClaim(
                    column_index=claim.column_index,
                    header=header,
                    role=role,
                    kept_column_index=claim.column_index,
                )
            )
            continue
        if role is FieldRole.UNMAPPED:
            decided.add(claim.column_index)
            continue
        holder = holder_of_role.get(role)
        if holder is not None:
            discarded.append(
                DiscardedDuplicateClaim(
                    column_index=claim.column_index,
                    header=header,
                    role=role,
                    kept_column_index=holder,
                )
            )
            continue
        roles[claim.column_index] = role
        holder_of_role[role] = claim.column_index
        decided.add(claim.column_index)

    unmapped = tuple(
        ObservedColumn(column_index=index, header=header)
        for index, header in enumerate(observed_headers)
        if roles[index] is FieldRole.UNMAPPED
    )
    return ColumnRoleProposal(
        roles=tuple(roles),
        unmapped_columns=unmapped,
        rejected_role_proposals=tuple(rejected),
        discarded_duplicate_claims=tuple(discarded),
        unknown_column_claims=tuple(unknown_columns),
    )


class SemanticColumnRoleMapper:
    """Establish one table's column roles with a language model, once per file.

    Binds to :class:`~adapters.outbound.llm.LLMClient` and nothing lower, so
    which engine answers -- an on-host runtime or a gated hosted one -- is
    configuration rather than a fact this class holds.

    The mapping role wants the SMALLEST capable model: the task is a selection
    over a short closed vocabulary from a handful of short strings, which is
    within reach of a 2B-4B class local model. Leaving ``model`` unset uses the
    active provider's configured model; a caller that wants the mapping role
    pinned below the deployment default passes it here.

    Args:
        model: Optional model identifier override; ``None`` uses the configured
            model for whichever provider is active.
        client: Injected client (dependency injection for callers holding one);
            default-constructed against the resolved settings otherwise.
        settings: Injected settings; defaults to ``load_settings()``.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        client: LLMClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved_settings = settings if settings is not None else load_settings()
        self._model = model
        self._client = (
            client
            if client is not None
            else LLMClient(
                settings=resolved_settings,
                caller="cadrumo.llm.column_role_mapping",
                prompt_id=COLUMN_ROLE_MAPPING_PROMPT_ID,
            )
        )

    @property
    def decided_by(self) -> str:
        """Provenance stamp naming how a mapping was reached.

        ``configured`` when the caller pinned nothing, because the effective
        model is then the active provider's default rather than a fact this
        object holds.
        """
        return f"llm:column-role-map:{self._model or 'configured'}"

    def map(self, headers: Sequence[str]) -> ColumnRoleProposal:
        """Establish the roles of ``headers``, one call for the whole file.

        Args:
            headers: The header cells, in column order, exactly as the file
                printed them. No cell value is passed, and none is accepted.

        Returns:
            The positional mapping plus every column that was not established.

        Raises:
            LLMValidationError: When ``headers`` is empty or the reply
                carries no usable object.
        """
        response = asyncio.run(self._client.complete(self._build_request(headers)))
        return parse_column_role_mapping_response(response.text, headers)

    def _build_request(self, headers: Sequence[str]) -> LLMRequest:
        """Build the completion request for one table's headers.

        Carries no ``provider_override``: the active provider is whatever the
        caller configured. Temperature is pinned to zero because role
        assignment has one right answer per column.
        """
        return LLMRequest(
            prompt=build_column_role_mapping_prompt(headers),
            max_tokens=_MAX_REPLY_TOKENS,
            temperature=_MAPPING_TEMPERATURE,
            model_override=self._model,
        )


def map_column_roles(
    headers: Sequence[str],
    *,
    model: str | None = None,
    settings: Settings | None = None,
) -> ColumnRoleProposal:
    """Convenience wrapper: build a :class:`SemanticColumnRoleMapper` and map once.

    Args:
        headers: The header cells, in column order.
        model: Optional model override.
        settings: Optional resolved settings override.

    Returns:
        The positional mapping plus every column that was not established.
    """
    return SemanticColumnRoleMapper(model=model, settings=settings).map(headers)
