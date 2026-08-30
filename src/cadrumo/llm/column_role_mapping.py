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

from ..core import LLM_EXTRA, FieldRole, ModelRole, build_provenance_stamp, require_optional_extra
from ..core.operator_action_enums import ActionEvidenceProvenance
from ..core.config import Settings, load_settings
from .client import LLMClient
from .errors import LLMConfigError, LLMValidationError
from .models import LLMProvider, LLMRequest
from .preconditions import LLMPreconditionCondition, llm_no_recovery_verdict

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
        return dict[str, str]()
    class_definition = ast.parse(textwrap.dedent(source)).body[0]
    if not isinstance(class_definition, ast.ClassDef):
        return dict[str, str]()
    descriptions: dict[str, str] = {}
    pending_token: str | None = None
    for node in class_definition.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
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
        raise LLMValidationError(
            context={"column_count": 0, "column_headers_present": False},
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.COLUMN_MAPPING_HEADERS_PRESENT,
                facts={"column_count": 0, "column_headers_present": False},
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            ),
        )
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
        raise LLMValidationError(
            context={"column_count": 0, "column_headers_present": False},
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.COLUMN_MAPPING_HEADERS_PRESENT,
                facts={"column_count": 0, "column_headers_present": False},
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            ),
        )
    payload = _first_json_object(text)
    if payload is None:
        raise LLMValidationError(
            context={"column_mapping_response_parseable": False},
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.COLUMN_MAPPING_RESPONSE_PARSEABLE,
                facts={"column_mapping_response_parseable": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            ),
        )
    try:
        reply = ColumnRoleMappingReply.model_validate_json(payload)
    except ValueError as exc:
        raise LLMValidationError(
            context={
                "column_mapping_response_schema_valid": False,
                "column_mapping_validation_error_type": type(exc).__name__,
            },
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.COLUMN_MAPPING_RESPONSE_SCHEMA_VALID,
                facts={
                    "column_mapping_response_schema_valid": False,
                    "column_mapping_validation_error_type": type(exc).__name__,
                },
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            ),
        ) from exc

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

    Binds to :class:`~llm.LLMClient` and nothing lower, so
    which engine answers -- an on-host runtime or a gated hosted one -- is
    configuration rather than a fact this class holds.

    **The model comes from the role, never from the general default.** Left to
    itself the client would answer a mapping call on
    ``cadrumo_llm_model`` -- a frontier hosted model -- for a task that is
    selecting among a handful of short strings. So the model is resolved
    through :func:`~application.provisioning.select_model_for_role` against
    :attr:`~core.ModelRole.COLUMN_ROLE_MAPPING`, which names the WEAKEST catalogued
    candidate clearing the capability, licence and headroom bars on this
    machine. Re-pointing that role in the catalogue re-points this lane with no
    edit here.

    A role-resolved model is an on-host runtime id, so it is paired with the
    LOCAL provider: the pairing is the point, and sending an Ollama id to a
    hosted API would fail at the transport. A caller that pins ``model``
    explicitly owns that pairing and gets no provider override; a caller that
    pins ``provider`` gets exactly what it asked for. That is the seam the
    measurement lane runs its gated cloud engine through, and it is the only
    way off-host.

    Args:
        model: Optional runtime id, honoured over the role resolution. Passed
            to selection as the operator override, so a licence-barred or
            uncatalogued choice is still honoured -- and still advised on.
        provider: Optional provider override. ``None`` pairs a role-resolved
            model with LOCAL, and leaves an explicitly pinned ``model`` on
            whichever provider is configured.
        client: Injected client (dependency injection for callers holding one);
            default-constructed against the resolved settings otherwise.
        settings: Injected settings; defaults to ``load_settings()``.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        provider: LLMProvider | None = None,
        client: LLMClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Build the mapper against a model and settings."""
        # Ahead of every other statement, so the refusal is what an operator
        # without the extra sees rather than a settings or model-resolution
        # error raised on the way to it. This is the point the tabular lane
        # splits at: a known fixed-layout file never reaches here and imports
        # fully on a core install, while an unknown header vocabulary needs the
        # mapping call and refuses with the install hint.
        require_optional_extra(LLM_EXTRA)
        resolved_settings = settings if settings is not None else load_settings()
        self._model = model if model is not None else self._role_model(resolved_settings)
        self._provider = provider if provider is not None else (None if model is not None else LLMProvider.LOCAL)
        # The transport the stamp names, resolved separately from the one the
        # request carries. `self._provider` stays None when the caller deferred
        # to configuration, because passing None to the request means "let the
        # client resolve it" -- but a stamp cannot defer, and one that omits the
        # transport is a stamp a consent withdrawal cannot classify.
        self._stamp_provider = self._provider or LLMProvider(resolved_settings.cadrumo_llm_provider)
        self._client = (
            client
            if client is not None
            else LLMClient(
                settings=resolved_settings,
                caller="cadrumo.llm.column_role_mapping",
                prompt_id=COLUMN_ROLE_MAPPING_PROMPT_ID,
            )
        )

    @staticmethod
    def _role_model(settings: Settings) -> str:
        """Resolve the tabular-mapping role to a runtime id on this machine.

        Deferred import: the selection surface sits in the application tier,
        which reaches back into this package, so an eager binding would close
        that loop at import time.

        Raises:
            LLMConfigError: When no catalogued candidate clears the bars here.
                Naming a model that cannot serve would push the failure into
                inference, where it reaches the operator as a timeout instead
                of as a refusal carrying its own remediation.
        """
        from ..application.provisioning import select_model_for_role

        selection = select_model_for_role(ModelRole.COLUMN_ROLE_MAPPING, settings=settings)
        if not selection.selected or selection.runtime_id is None:
            raise LLMConfigError(
                context=selection.facts,
                precondition_verdict=selection.precondition_verdict,
            )
        return selection.runtime_id

    @property
    def decided_by(self) -> str:
        """Provenance stamp naming the transport and model a mapping was reached with.

        This stamp previously named no transport at all, which had two costs.
        It could not say whether a mapping had left the host -- and this is the
        one reader besides the extractors that accepts a provider, so it is the
        one that can. And its reader name parsed AS a transport, so a survey
        classifying artefacts by that segment read ``column`` where it expected
        a transport.
        """
        return build_provenance_stamp(
            provider=self._stamp_provider,
            reader="column-role-map",
            model=self._model,
        )

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

        Temperature is pinned to zero because role assignment has one right
        answer per column.

        **The evidence marker is stated, and it is stated False.** What crosses
        this seam is the file's schema -- the header labels a bank or a billing
        tool printed to name its own columns -- and never a cell value: the
        prompt compiler accepts headers and nothing else, and the instruction it
        writes forbids the model to reproduce data. That is a judgement about
        the content, so it is written here rather than inherited from the
        model's default, where it would be indistinguishable from a builder that
        forgot. Marking it would put a schema-shaped request behind a
        taxpayer-evidence consent token and close the gated hosted lane the
        tabular measurement runs through.
        """
        return LLMRequest(
            prompt=build_column_role_mapping_prompt(headers),
            max_tokens=_MAX_REPLY_TOKENS,
            temperature=_MAPPING_TEMPERATURE,
            provider_override=self._provider,
            model_override=self._model,
            evidence_derived=False,
        )


def map_column_roles(
    headers: Sequence[str],
    *,
    model: str | None = None,
    provider: LLMProvider | None = None,
    settings: Settings | None = None,
) -> ColumnRoleProposal:
    """Convenience wrapper: build a :class:`SemanticColumnRoleMapper` and map once.

    Args:
        headers: The header cells, in column order.
        model: Optional runtime id, honoured over the role resolution.
        provider: Optional provider override.
        settings: Optional resolved settings override.

    Returns:
        The positional mapping plus every column that was not established.
    """
    return SemanticColumnRoleMapper(model=model, provider=provider, settings=settings).map(headers)
