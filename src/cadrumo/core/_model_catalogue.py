"""The typed local-model catalogue: what may be selected, and under whose licence.

One home for a fact that was previously invisible. Before this module the model
identifiers lived as bare string defaults on
:class:`~core.config.Settings` with their trade-offs described in field
docstrings, and the licence axis was described nowhere at all -- so the shipped
vision default was a research-licensed model that bars commercial use, inside a
commercial tax product, with nothing in the tree that could have said so.

Three declarations per candidate carry the weight:

``memory_requirement_bytes``
    The publisher's stated weight size, the figure
    :func:`~application.provisioning.assess_model_load_contention` compares
    against measured free headroom. It is the requirement BEFORE the configured
    safety margin, never after -- the margin is deployment policy and lives on
    :class:`~core.config.Settings`.

``max_context_tokens``
    The capability floor, and the reason selection is bounded from BELOW. The
    document read sends the registry allow-list prompt plus an encoded page, so
    a model whose window cannot hold ``cadrumo_llm_ollama_num_ctx`` is not a
    cheaper option -- it is an unusable one, and it must be excluded on
    capability rather than ranked below on quality.

:class:`ModelLicence`
    An SPDX identifier plus an EXPLICIT ``commercial_use_permitted`` flag, each
    verified against the publisher's own text at authoring and carrying the
    quote and URL that were read. An unverified licence is a refusal input, not
    a permissive default: :class:`ModelLicence` refuses to be constructed as
    commercially usable without a verification source, so the failure direction
    of a future hand-edit is a build error rather than a silent legal claim.

This is deployment configuration, not registry data -- it encodes no tax
semantics -- so it lives in ``core/`` beside the
:class:`~core.config.Settings` fields it supplies defaults to, and the
selection logic that consumes it lives in the application layer at
:func:`~application.provisioning.select_model_for_role`.

See Also:
    :class:`~core.AcceleratorKind`
        The measured-hardware axis selection filters candidates against.
    :class:`~application.provisioning.HardwareProfile`
        The measured profile whose free figures decide whether a candidate fits.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, Field, model_validator

from ._models import STRICT_FROZEN_CONFIG

__all__ = [
    "ANTHROPIC_COMMERCIAL_TERMS",
    "APACHE_2_0",
    "DEFAULT_MODEL_BY_RUNTIME_AND_ROLE",
    "MODEL_CATALOGUE",
    "QWEN_RESEARCH",
    "DeploymentLicencePosture",
    "LicenceVerification",
    "ModelCandidate",
    "ModelLicence",
    "ModelRole",
    "ModelRuntime",
    "ModelSelectionAdvisory",
    "candidates_for_role",
    "default_model_runtime_id",
    "model_candidate",
]


class ModelRole(StrEnum):
    """The distinct jobs a local model is selected for.

    Kept as roles rather than as one "the local model" axis because the
    capability bars differ, and they differ in BOTH directions: only vision
    transcription needs image input, and the two text roles must be satisfiable
    on a machine that cannot host a vision model at all. Each role resolves
    independently through
    :func:`~application.provisioning.select_model_for_role`.

    The two text roles are not one role. Column-role mapping is *strictly
    easier* than text extraction -- a selection over a short closed vocabulary
    given a handful of short header strings, against reading a whole document's
    text layer -- so it is kept separate precisely so it can be sized DOWN
    independently rather than inheriting the harder role's model.

    ``VISION_TRANSCRIPTION`` reads a scanned or photographed page;
    ``TEXT_EXTRACTION`` classifies an already-extracted text layer;
    ``COLUMN_ROLE_MAPPING`` names the columns of a delimited table from their
    header strings; and ``SUPPLY_NATURE_PROPOSAL`` proposes whether invoice
    lines supply goods or services for an operator to confirm.
    """

    VISION_TRANSCRIPTION = "vision_transcription"
    TEXT_EXTRACTION = "text_extraction"
    COLUMN_ROLE_MAPPING = "column_role_mapping"
    SUPPLY_NATURE_PROPOSAL = "supply_nature_proposal"


class ModelRuntime(StrEnum):
    """Where a candidate's weights actually run, which changes what may be judged.

    The axis exists because two of the catalogue's bars are meaningless off-host.
    A hosted model has no local memory requirement to compare against measured
    free headroom, and no weights to pull; what it has instead is a service
    contract. Collapsing the two runtimes into one list would force every
    consumer to special-case that, and would let a cloud model be ranked by a
    memory figure it does not have.

    The capability and licence bars still apply to both: the prompt is the same
    size wherever it runs, and "may we use this commercially" is the same
    question whether the answer comes from a weights licence or a terms of
    service.

    Members:

        LOCAL_OLLAMA: Weights pulled and run on the operator's own machine.
        CLOUD_ANTHROPIC: A hosted Anthropic API model; nothing runs on-host.
    """

    LOCAL_OLLAMA = "local_ollama"
    CLOUD_ANTHROPIC = "cloud_anthropic"


class LicenceVerification(StrEnum):
    """How a catalogue entry's licence claim was checked, and against what.

    Recorded because the claim's *provenance* is the part that can rot. An SPDX
    identifier written from recall reads identically to one read off the
    publisher's licence file, and only one of the two survives a lawyer. The
    member names the artefact that was actually read.

    ``PUBLISHER_LICENCE_FILE`` means the publisher's LICENSE text was read;
    ``PUBLISHER_MODEL_CARD`` means its model-card licence field was read;
    ``PUBLISHER_SERVICE_TERMS`` means its service terms were read; and
    ``UNVERIFIED`` means no publisher text was read and therefore bars a
    commercial-use claim (see :class:`ModelLicence`).
    """

    PUBLISHER_LICENCE_FILE = "publisher_licence_file"
    PUBLISHER_MODEL_CARD = "publisher_model_card"
    PUBLISHER_SERVICE_TERMS = "publisher_service_terms"
    UNVERIFIED = "unverified"


class DeploymentLicencePosture(StrEnum):
    """Whether this deployment needs a licence that permits commercial use.

    ``COMMERCIAL`` is the product's posture: Cadrumo is a commercial tax
    product and a gestor filing for clients is unambiguously commercial use.
    ``NON_COMMERCIAL`` exists so an individual filing their own return, or a
    research evaluation, is not refused a candidate whose licence genuinely
    covers them -- the posture is a fact about the deployment, and encoding it
    as one is what keeps the commercial default honest rather than merely
    strict.

    Members:

        COMMERCIAL: Only candidates whose licence permits commercial use.
        NON_COMMERCIAL: Research-licensed candidates are additionally eligible.
    """

    COMMERCIAL = "commercial"
    NON_COMMERCIAL = "non_commercial"


class ModelSelectionAdvisory(StrEnum):
    """Why a resolved selection is worth telling the operator about.

    Selection never fails silently and an override is never honoured silently.
    Each member keys one operator-visible statement, so a caller renders the
    reason rather than re-deriving it from the selection's shape.

    Members:

        LICENCE_COMMERCIAL_USE_BARRED: The selected model's licence bars
            commercial use under the active posture. Only reachable through an
            explicit override; automatic selection excludes such candidates.
        LICENCE_UNVERIFIED: No publisher licence text backs the selected model,
            so no licence claim can be made about it at all.
        OVERRIDE_NOT_IN_CATALOGUE: The operator named a model the catalogue does
            not describe, so neither its licence nor its fit could be judged.
        OVERRIDE_BELOW_CONTEXT_FLOOR: The selected model's context window is
            smaller than the configured request window.
        FIT_EXCEEDS_MEASURED_HEADROOM: The selected model's requirement plus the
            safety margin exceeds measured free memory.
        FIT_UNVERIFIED: Free memory could not be measured, so fit was not
            checked here. The load itself still fails closed at
            :func:`~application.provisioning.assess_model_load_contention`.
    """

    LICENCE_COMMERCIAL_USE_BARRED = "licence_commercial_use_barred"
    LICENCE_UNVERIFIED = "licence_unverified"
    OVERRIDE_NOT_IN_CATALOGUE = "override_not_in_catalogue"
    OVERRIDE_BELOW_CONTEXT_FLOOR = "override_below_context_floor"
    FIT_EXCEEDS_MEASURED_HEADROOM = "fit_exceeds_measured_headroom"
    FIT_UNVERIFIED = "fit_unverified"


class ModelLicence(BaseModel):
    """One model's licence, its commercial-use consequence, and the text that proves it.

    ``commercial_use_permitted`` is declared explicitly rather than derived from
    ``spdx_id`` because the derivation is exactly the step that goes wrong: a
    reader who knows Apache-2.0 permits commercial use will assume a
    publisher-specific ``LicenseRef-*`` does too, and one of this catalogue's
    entries is a licence whose text says "FOR NON-COMMERCIAL PURPOSES ONLY".

    ``verified_quote`` and ``source_url`` are required whenever a verification
    source is claimed, so the claim can be re-checked by opening one URL. The
    validator enforces the asymmetry that matters: an ``UNVERIFIED`` licence may
    not assert commercial use. Unverified is a refusal input, never a permissive
    default.
    """

    model_config = STRICT_FROZEN_CONFIG

    spdx_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    commercial_use_permitted: bool
    verification: LicenceVerification
    source_url: str = ""
    verified_quote: str = ""

    @model_validator(mode="after")
    def _verification_supports_the_claim(self) -> ModelLicence:
        """Refuse a commercial-use claim that no publisher text backs."""
        if self.verification is LicenceVerification.UNVERIFIED:
            if self.commercial_use_permitted:
                msg = (
                    f"licence {self.spdx_id!r} claims commercial use is permitted but carries no "
                    f"publisher verification; an unverified licence must not assert commercial use"
                )
                raise ValueError(msg)
            return self
        if not self.source_url or not self.verified_quote:
            msg = (
                f"licence {self.spdx_id!r} declares verification {self.verification.value!r} but "
                f"omits the source URL or the verified quote that was read"
            )
            raise ValueError(msg)
        return self


class ModelCandidate(BaseModel):
    """One selectable local model: what it costs, what it can hold, and its licence.

    ``roles`` is a set because a vision-capable model serves both the
    transcription and the tabular-mapping roles from one pulled copy, and
    duplicating the row per role would let the two descriptions of the same
    weights drift.

    ``measured_baseline_ref`` names the corpus measurement that justifies this
    candidate's place in the ordering, or is empty where none has been run yet.
    Empty is the honest state for most of this catalogue today and must stay
    distinguishable from a measured zero -- a candidate carrying no baseline is
    selected on its declared capability bars alone.
    """

    model_config = STRICT_FROZEN_CONFIG

    runtime_id: str = Field(min_length=1)
    runtime: ModelRuntime
    roles: frozenset[ModelRole] = Field(min_length=1)
    memory_requirement_bytes: int | None = Field(default=None, gt=0)
    input_price_per_mtok_usd: Decimal | None = Field(default=None, gt=Decimal("0"))
    max_context_tokens: int = Field(gt=0)
    licence: ModelLicence
    measured_baseline_ref: str = ""
    notes: str = ""

    @model_validator(mode="after")
    def _memory_requirement_matches_the_runtime(self) -> ModelCandidate:
        """Require a memory figure exactly where one can be measured against.

        A local candidate without it cannot be admitted by the contention check;
        a cloud candidate WITH one invites a comparison against this machine's
        free memory that means nothing, because the weights never touch it.
        """
        if self.runtime is ModelRuntime.LOCAL_OLLAMA and self.memory_requirement_bytes is None:
            msg = f"local candidate {self.runtime_id!r} declares no memory requirement"
            raise ValueError(msg)
        if self.runtime is not ModelRuntime.LOCAL_OLLAMA and self.memory_requirement_bytes is not None:
            msg = (
                f"hosted candidate {self.runtime_id!r} declares a local memory requirement; "
                f"its weights never run on this machine"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _hosted_candidates_declare_their_price(self) -> ModelCandidate:
        """Require the ranking axis each runtime actually has.

        Selection is bounded from below, which needs SOME ordering to be bounded
        against. On-host that axis is the memory requirement; a hosted model has
        no on-host footprint, so without a declared price its ordering silently
        degrades to alphabetical -- and a frontier-tier default then sorts as
        "weakest" purely by its name. The published input price is the honest
        substitute: it is publisher-verifiable, it tracks tier, and it is the
        cost the operator actually carries.
        """
        if self.runtime is ModelRuntime.LOCAL_OLLAMA and self.input_price_per_mtok_usd is not None:
            msg = f"local candidate {self.runtime_id!r} declares a per-token price; its weights run on-host for free"
            raise ValueError(msg)
        if self.runtime is not ModelRuntime.LOCAL_OLLAMA and self.input_price_per_mtok_usd is None:
            msg = (
                f"hosted candidate {self.runtime_id!r} declares no input price, so it has no "
                f"ordering axis and selection cannot be bounded from below"
            )
            raise ValueError(msg)
        return self

    @property
    def selection_rank(self) -> Decimal:
        """Return the ascending 'weakest first' key for this candidate's runtime.

        Memory bytes on-host, published input price off-host. Comparable only
        within one runtime, which is why :func:`candidates_for_role` is scoped to
        one.
        """
        if self.memory_requirement_bytes is not None:
            return Decimal(self.memory_requirement_bytes)
        return self.input_price_per_mtok_usd or Decimal(0)

    def serves(self, role: ModelRole) -> bool:
        """Return whether this candidate is eligible for ``role``."""
        return role in self.roles

    def permitted_under(self, posture: DeploymentLicencePosture) -> bool:
        """Return whether this candidate's licence permits ``posture``.

        A non-commercial posture accepts every catalogued licence; a commercial
        posture accepts only those whose publisher text was read AND permits
        commercial use.
        """
        if posture is DeploymentLicencePosture.NON_COMMERCIAL:
            return True
        return self.licence.commercial_use_permitted


# Licences are declared once and shared by the candidates they cover, so the
# quote that was read cannot differ between two rows describing one licence.
APACHE_2_0: Final = ModelLicence(
    spdx_id="Apache-2.0",
    name="Apache License 2.0",
    commercial_use_permitted=True,
    verification=LicenceVerification.PUBLISHER_MODEL_CARD,
    source_url="https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct",
    verified_quote="license: apache-2.0",
)
"""Apache-2.0 as declared on the publishers' own model cards.

Read from the ``license:`` frontmatter field of each covered model's card at
authoring; ``source_url`` names one of them and the remainder are recorded on
each candidate's ``notes``. Apache-2.0 is an SPDX-listed permissive licence
whose grant is explicitly commercial-capable.
"""

QWEN_RESEARCH: Final = ModelLicence(
    spdx_id="LicenseRef-Qwen-Research",
    name="Qwen RESEARCH LICENSE AGREEMENT",
    commercial_use_permitted=False,
    verification=LicenceVerification.PUBLISHER_LICENCE_FILE,
    source_url="https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/raw/main/LICENSE",
    verified_quote=(
        "to use, reproduce, distribute, copy, create derivative works of, and make "
        "modifications to the Materials FOR NON-COMMERCIAL PURPOSES ONLY"
    ),
)
"""The Qwen Research licence, whose text bars commercial use outright.

Not an SPDX-listed licence, so it carries an SPDX ``LicenseRef-`` identifier
rather than a fabricated listed one. The publisher's licence file adds "If you
are commercially using the Materials, you shall request a license from us",
which is what makes a barred candidate reachable only through an explicit,
advised operator override rather than through automatic selection.
"""


ANTHROPIC_COMMERCIAL_TERMS: Final = ModelLicence(
    spdx_id="LicenseRef-Anthropic-Commercial-Terms",
    name="Anthropic Commercial Terms of Service",
    commercial_use_permitted=True,
    verification=LicenceVerification.PUBLISHER_SERVICE_TERMS,
    source_url="https://www.anthropic.com/legal/commercial-terms",
    verified_quote=(
        "Subject to these Terms, Anthropic gives Customer permission to use the Services, "
        "including to power products and services Customer makes available to its own "
        "customers and end users"
    ),
)
"""The service contract a hosted Anthropic model is used under.

Not a weights licence -- there are no weights to license -- so it carries an
SPDX ``LicenseRef-`` identifier and is verified against the publisher's terms of
service rather than a LICENSE file. The same terms assign output ownership to
the customer, which is what makes a hosted read usable in a filing-grade
product at all.

Reading it as a licence keeps ONE gate over both runtimes: "may we use this
commercially" has to be answered for a hosted model exactly as for a local one,
and a second, parallel notion of permission is how one of the two answers goes
unchecked.
"""


# Memory requirements are the publishers' stated weight sizes for the pulled
# quantisation (decimal GB as published by the runtime library), NOT an
# estimate: the figure a contention check compares must be traceable to a
# published number. Context windows are the publishers' stated windows for the
# same tag.
MODEL_CATALOGUE: Final[tuple[ModelCandidate, ...]] = (
    ModelCandidate(
        runtime_id="moondream:1.8b",
        runtime=ModelRuntime.LOCAL_OLLAMA,
        roles=frozenset({ModelRole.VISION_TRANSCRIPTION}),
        memory_requirement_bytes=1_700_000_000,
        max_context_tokens=2_048,
        licence=APACHE_2_0,
        notes=(
            "The smallest vision-capable candidate, and the worked example of why the "
            "capability floor is a filter rather than a preference: its 2K window cannot "
            "hold the allow-list prompt plus an encoded page, so it is excluded on "
            "capability at the default request window rather than ranked below on quality. "
            "Licence read at https://huggingface.co/vikhyatk/moondream2"
        ),
    ),
    ModelCandidate(
        runtime_id="qwen3-vl:2b",
        runtime=ModelRuntime.LOCAL_OLLAMA,
        roles=frozenset({ModelRole.VISION_TRANSCRIPTION}),
        memory_requirement_bytes=1_900_000_000,
        max_context_tokens=256_000,
        licence=APACHE_2_0,
        notes=(
            "The vision default. Smaller than the research-licensed incumbent it replaces "
            "and permissively licensed, which is why the licence correction costs nothing "
            "in capability. Licence read at https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct"
        ),
    ),
    ModelCandidate(
        runtime_id="qwen2.5vl:3b",
        runtime=ModelRuntime.LOCAL_OLLAMA,
        roles=frozenset({ModelRole.VISION_TRANSCRIPTION}),
        memory_requirement_bytes=3_200_000_000,
        max_context_tokens=125_000,
        licence=QWEN_RESEARCH,
        notes=(
            "The former shipped vision default, retained so an operator whose deployment is "
            "genuinely non-commercial can still name it -- and so the reason it stopped "
            "being the default is recorded rather than lost. Licence read at "
            "https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct"
        ),
    ),
    ModelCandidate(
        runtime_id="qwen2.5vl:7b",
        runtime=ModelRuntime.LOCAL_OLLAMA,
        roles=frozenset({ModelRole.VISION_TRANSCRIPTION}),
        memory_requirement_bytes=6_000_000_000,
        max_context_tokens=125_000,
        licence=APACHE_2_0,
        notes=(
            "An upward override for an 8 GB-class device. Never selected automatically: "
            "selection is bounded from below, so a larger model is an operator's choice. "
            "Licence read at https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct"
        ),
    ),
    ModelCandidate(
        runtime_id="qwen3:1.7b",
        runtime=ModelRuntime.LOCAL_OLLAMA,
        roles=frozenset({ModelRole.TEXT_EXTRACTION, ModelRole.COLUMN_ROLE_MAPPING, ModelRole.SUPPLY_NATURE_PROPOSAL}),
        memory_requirement_bytes=1_400_000_000,
        max_context_tokens=40_000,
        licence=APACHE_2_0,
        notes=(
            "The default for both text roles. Replaces qwen2.5:3b for the same reason the "
            "vision default flipped: the incumbent carries the Qwen Research licence. It "
            "also serves column-role mapping, which needs no larger model and no higher "
            "memory floor -- a machine already provisioned for the text read is provisioned "
            "for the mapper, so the mapper adds no hardware requirement at all. Licence "
            "read at https://huggingface.co/Qwen/Qwen3-1.7B"
        ),
    ),
    ModelCandidate(
        runtime_id="qwen2.5:3b",
        runtime=ModelRuntime.LOCAL_OLLAMA,
        roles=frozenset({ModelRole.TEXT_EXTRACTION, ModelRole.COLUMN_ROLE_MAPPING, ModelRole.SUPPLY_NATURE_PROPOSAL}),
        memory_requirement_bytes=1_900_000_000,
        max_context_tokens=32_768,
        licence=QWEN_RESEARCH,
        notes=(
            "The former shipped text default. Its licence bar is easy to miss because most "
            "Qwen2.5 sizes ARE Apache-2.0 -- the 3B is one of the two that are not, which "
            "is precisely why the flag is declared per candidate and read from the "
            "publisher's licence file. Licence read at "
            "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct"
        ),
    ),
    ModelCandidate(
        runtime_id="claude-haiku-4-5",
        runtime=ModelRuntime.CLOUD_ANTHROPIC,
        roles=frozenset(
            {
                ModelRole.VISION_TRANSCRIPTION,
                ModelRole.TEXT_EXTRACTION,
                ModelRole.COLUMN_ROLE_MAPPING,
                ModelRole.SUPPLY_NATURE_PROPOSAL,
            },
        ),
        input_price_per_mtok_usd=Decimal("1"),
        max_context_tokens=200_000,
        licence=ANTHROPIC_COMMERCIAL_TERMS,
        notes=(
            "The cloud default for every role: the smallest and fastest current Claude "
            "model, and the tier the provisioning decision names as the off-host proxy "
            "for the on-host 2B-4B class. It is the lowest-bound capable cloud candidate, "
            "which is the whole point -- a hosted route must not silently reach a frontier "
            "tier. Vision-capable: the publisher's model overview states that all current "
            "Claude models support text and image input and vision. Priced at $1 per million "
            "input tokens, the cheapest current tier -- against $3 for the mid tier and $5 for "
            "the frontier tier, which is what makes the ordering real rather than alphabetical. "
            "Specification and pricing read at "
            "https://platform.claude.com/docs/en/about-claude/models/overview"
        ),
    ),
)

DEFAULT_MODEL_BY_RUNTIME_AND_ROLE: Final[Mapping[ModelRuntime, Mapping[ModelRole, str]]] = {
    ModelRuntime.LOCAL_OLLAMA: {
        ModelRole.VISION_TRANSCRIPTION: "qwen3-vl:2b",
        ModelRole.TEXT_EXTRACTION: "qwen3:1.7b",
        ModelRole.COLUMN_ROLE_MAPPING: "qwen3:1.7b",
        ModelRole.SUPPLY_NATURE_PROPOSAL: "qwen3:1.7b",
    },
    ModelRuntime.CLOUD_ANTHROPIC: {
        ModelRole.VISION_TRANSCRIPTION: "claude-haiku-4-5",
        ModelRole.TEXT_EXTRACTION: "claude-haiku-4-5",
        ModelRole.COLUMN_ROLE_MAPPING: "claude-haiku-4-5",
        ModelRole.SUPPLY_NATURE_PROPOSAL: "claude-haiku-4-5",
    },
}
"""Every shipped default, keyed by runtime then role -- the source of the settings defaults.

Keyed by runtime as well as role because the two runtimes are configured
separately and a role's answer differs between them. Declared here rather than
as literals on :class:`~core.config.Settings` so the licence gate has ONE place
to read every shipped default from, across both runtimes, and so a default
cannot name a model the catalogue does not describe.

That completeness is the point. A per-role gate that only knew about local
defaults would have passed while every cloud route fell through to a
frontier-tier model, which is exactly the state this mapping was added to
correct.
"""


def _validate_catalogue_runtime_role(
    runtime: ModelRuntime,
    role: ModelRole,
    defaults: Mapping[ModelRole, str],
) -> None:
    """Refuse a runtime/role pair with no candidate, or an absent or ineligible default."""
    if not any(c.serves(role) and c.runtime is runtime for c in MODEL_CATALOGUE):
        msg = f"the catalogue declares no {runtime.value!r} candidate for role {role.value!r}"
        raise ValueError(msg)
    default_id = defaults.get(role)
    if default_id is None:
        msg = f"no {runtime.value!r} default for role {role.value!r}"
        raise ValueError(msg)
    default = next((c for c in MODEL_CATALOGUE if c.runtime_id == default_id), None)
    if default is None or not default.serves(role) or default.runtime is not runtime:
        msg = f"the default {default_id!r} is not a catalogued {runtime.value!r} candidate for {role.value!r}"
        raise ValueError(msg)


def _validate_catalogue() -> None:
    """Refuse an internally inconsistent catalogue at import.

    Structural invariants only -- unique ids, every runtime/role pair covered,
    every default resolvable and eligible for the role and runtime it defaults.
    The licence and ordering properties are asserted by the catalogue gate
    rather than here, because a gate that lives in the module it checks cannot
    fail the build independently of it.
    """
    ids = [candidate.runtime_id for candidate in MODEL_CATALOGUE]
    if len(ids) != len(set(ids)):
        msg = "the model catalogue declares a duplicate runtime id"
        raise ValueError(msg)
    for runtime in ModelRuntime:
        defaults = DEFAULT_MODEL_BY_RUNTIME_AND_ROLE.get(runtime)
        if defaults is None:
            msg = f"the model catalogue declares no defaults for runtime {runtime.value!r}"
            raise ValueError(msg)
        for role in ModelRole:
            _validate_catalogue_runtime_role(runtime, role, defaults)


_validate_catalogue()


def candidates_for_role(
    role: ModelRole,
    runtime: ModelRuntime = ModelRuntime.LOCAL_OLLAMA,
) -> tuple[ModelCandidate, ...]:
    """Return every candidate serving ``role`` on ``runtime``, weakest first.

    Scoped to one runtime because the ordering is only meaningful within one:
    ascending declared memory requirement ranks local candidates, and a hosted
    candidate has no such figure to be ranked by. Mixing them would sort a cloud
    model against a number it does not have.

    Within a runtime the order IS the selection order: the design point is the
    weakest model that clears the capability bars, never the strongest the
    hardware or the budget could reach. A caller that wants a larger model names
    it as an override.
    """
    return tuple(
        sorted(
            (c for c in MODEL_CATALOGUE if c.serves(role) and c.runtime is runtime),
            key=lambda c: (c.selection_rank, c.runtime_id),
        ),
    )


def model_candidate(runtime_id: str) -> ModelCandidate | None:
    """Return the catalogued candidate with ``runtime_id``, or ``None``.

    ``None`` means "this catalogue makes no claim about that model", which is
    distinct from a claim that it is unlicensed -- an operator naming an
    uncatalogued model is advised, not refused.
    """
    return next((candidate for candidate in MODEL_CATALOGUE if candidate.runtime_id == runtime_id), None)


def default_model_runtime_id(
    role: ModelRole,
    runtime: ModelRuntime = ModelRuntime.LOCAL_OLLAMA,
) -> str:
    """Return the shipped default runtime id for ``role`` on ``runtime``.

    Supplies the :class:`~core.config.Settings` field defaults for both
    runtimes, so the settings surface and the licence gate read one value.
    """
    return DEFAULT_MODEL_BY_RUNTIME_AND_ROLE[runtime][role]
