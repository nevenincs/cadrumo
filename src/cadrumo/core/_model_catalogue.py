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
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, Field, model_validator

from ._models import STRICT_FROZEN_CONFIG

__all__ = [
    "APACHE_2_0",
    "DEFAULT_MODEL_BY_ROLE",
    "MODEL_CATALOGUE",
    "QWEN_RESEARCH",
    "DeploymentLicencePosture",
    "LicenceVerification",
    "ModelCandidate",
    "ModelLicence",
    "ModelRole",
    "ModelSelectionAdvisory",
    "candidates_for_role",
    "default_model_runtime_id",
    "model_candidate",
]


class ModelRole(StrEnum):
    """The distinct jobs a local model is selected for.

    Kept as roles rather than as one "the local model" axis because the
    capability bars differ: two of the three need image input, and the text
    role must be satisfiable on a machine that cannot host a vision model at
    all. Each role resolves independently through
    :func:`~application.provisioning.select_model_for_role`.

    Members:
        VISION_TRANSCRIPTION: Reading a scanned or photographed document page.
        TEXT_EXTRACTION: Classifying an already-extracted text layer.
        TABULAR_MAPPING: Mapping a rendered table's cells to typed columns.
    """

    VISION_TRANSCRIPTION = "vision_transcription"
    TEXT_EXTRACTION = "text_extraction"
    TABULAR_MAPPING = "tabular_mapping"


class LicenceVerification(StrEnum):
    """How a catalogue entry's licence claim was checked, and against what.

    Recorded because the claim's *provenance* is the part that can rot. An SPDX
    identifier written from recall reads identically to one read off the
    publisher's licence file, and only one of the two survives a lawyer. The
    member names the artefact that was actually read.

    Members:
        PUBLISHER_LICENCE_FILE: The publisher's own LICENSE text was read.
        PUBLISHER_MODEL_CARD: The publisher's model card licence field was read.
        UNVERIFIED: No publisher text was read. Bars a commercial-use claim
            outright -- see :class:`ModelLicence`.
    """

    PUBLISHER_LICENCE_FILE = "publisher_licence_file"
    PUBLISHER_MODEL_CARD = "publisher_model_card"
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
    roles: frozenset[ModelRole] = Field(min_length=1)
    memory_requirement_bytes: int = Field(gt=0)
    max_context_tokens: int = Field(gt=0)
    licence: ModelLicence
    measured_baseline_ref: str = ""
    notes: str = ""

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


# Memory requirements are the publishers' stated weight sizes for the pulled
# quantisation (decimal GB as published by the runtime library), NOT an
# estimate: the figure a contention check compares must be traceable to a
# published number. Context windows are the publishers' stated windows for the
# same tag.
MODEL_CATALOGUE: Final[tuple[ModelCandidate, ...]] = (
    ModelCandidate(
        runtime_id="moondream:1.8b",
        roles=frozenset({ModelRole.VISION_TRANSCRIPTION, ModelRole.TABULAR_MAPPING}),
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
        roles=frozenset({ModelRole.VISION_TRANSCRIPTION, ModelRole.TABULAR_MAPPING}),
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
        roles=frozenset({ModelRole.VISION_TRANSCRIPTION, ModelRole.TABULAR_MAPPING}),
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
        roles=frozenset({ModelRole.VISION_TRANSCRIPTION, ModelRole.TABULAR_MAPPING}),
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
        roles=frozenset({ModelRole.TEXT_EXTRACTION}),
        memory_requirement_bytes=1_400_000_000,
        max_context_tokens=40_000,
        licence=APACHE_2_0,
        notes=(
            "The text default. Replaces qwen2.5:3b for the same reason the vision default "
            "flipped: the incumbent carries the Qwen Research licence. Licence read at "
            "https://huggingface.co/Qwen/Qwen3-1.7B"
        ),
    ),
    ModelCandidate(
        runtime_id="qwen2.5:3b",
        roles=frozenset({ModelRole.TEXT_EXTRACTION}),
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
)

DEFAULT_MODEL_BY_ROLE: Final[Mapping[ModelRole, str]] = {
    ModelRole.VISION_TRANSCRIPTION: "qwen3-vl:2b",
    ModelRole.TEXT_EXTRACTION: "qwen3:1.7b",
    ModelRole.TABULAR_MAPPING: "qwen3-vl:2b",
}
"""The runtime id each role falls back to, and the source of the settings defaults.

Declared here rather than as literals on :class:`~core.config.Settings` so the
licence gate has one place to read every shipped default from, and so a default
cannot name a model the catalogue does not describe.
"""


def _validate_catalogue() -> None:
    """Refuse an internally inconsistent catalogue at import.

    Structural invariants only -- unique ids, every role covered, every default
    resolvable and eligible for the role it defaults. The licence and ordering
    properties are asserted by the catalogue gate rather than here, because a
    gate that lives in the module it checks cannot fail the build independently
    of it.
    """
    ids = [candidate.runtime_id for candidate in MODEL_CATALOGUE]
    if len(ids) != len(set(ids)):
        msg = "the model catalogue declares a duplicate runtime id"
        raise ValueError(msg)
    for role in ModelRole:
        if not any(candidate.serves(role) for candidate in MODEL_CATALOGUE):
            msg = f"the model catalogue declares no candidate for role {role.value!r}"
            raise ValueError(msg)
        default_id = DEFAULT_MODEL_BY_ROLE.get(role)
        if default_id is None:
            msg = f"the model catalogue declares no default for role {role.value!r}"
            raise ValueError(msg)
        default = next((candidate for candidate in MODEL_CATALOGUE if candidate.runtime_id == default_id), None)
        if default is None or not default.serves(role):
            msg = f"the default {default_id!r} for role {role.value!r} is not a catalogued candidate for it"
            raise ValueError(msg)


_validate_catalogue()


def candidates_for_role(role: ModelRole) -> tuple[ModelCandidate, ...]:
    """Return every candidate serving ``role``, weakest first.

    Ascending by declared memory requirement, which is the selection order:
    the design point is the weakest model that clears the capability bars, not
    the strongest the hardware could hold. A caller that wants a larger model
    names it as an override.
    """
    return tuple(
        sorted(
            (candidate for candidate in MODEL_CATALOGUE if candidate.serves(role)),
            key=lambda candidate: (candidate.memory_requirement_bytes, candidate.runtime_id),
        ),
    )


def model_candidate(runtime_id: str) -> ModelCandidate | None:
    """Return the catalogued candidate with ``runtime_id``, or ``None``.

    ``None`` means "this catalogue makes no claim about that model", which is
    distinct from a claim that it is unlicensed -- an operator naming an
    uncatalogued model is advised, not refused.
    """
    return next((candidate for candidate in MODEL_CATALOGUE if candidate.runtime_id == runtime_id), None)


def default_model_runtime_id(role: ModelRole) -> str:
    """Return the shipped default runtime id for ``role``.

    Supplies the :class:`~core.config.Settings` field defaults, so the settings
    surface and the licence gate read one value.
    """
    return DEFAULT_MODEL_BY_ROLE[role]
