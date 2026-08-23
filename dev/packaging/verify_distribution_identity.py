"""Verify Cadrumo distribution-harness and MCP product identity projections.

This verifier is deliberately read-only. It inventories the shipped authored
harness, materialises the real workspace, plugin, and marketplace generators in
temporary directories, reads the production MCP prompt/resource projections, and
checks client-facing MCP product copy for bilingual claim parity. It reports drift
without renaming, translating, or mutating any shipped byte.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from cadrumo_harness import (
    PRODUCT_AUTHOR_NAME,
    iter_operator_rules,
    iter_personas,
    iter_skill_documents,
    materialise_marketplace,
    materialise_plugin,
    materialise_workspace,
    parse_skill_metadata,
)

import cadrumo
from cadrumo.core import PRODUCT_IDENTITY, scan_directory
from dev._paths import REPO_ROOT, UTF_8

_UTF_8: Final[str] = UTF_8
_REQUIRED_HARNESS_PREFIX: Final[str] = "cadrumo-"
#: The agent harness (operator rules, personas, skills, and the MCP server) is a
#: sibling distribution with its own source root; the CLI package tree under
#: ``src/cadrumo`` no longer carries any of it.
_HARNESS_SOURCE_ROOT: Final[Path] = Path("src") / "cadrumo-harness" / "src"
_HARNESS_PYTHON_PACKAGE: Final[str] = "cadrumo_harness"
_MARKDOWN_SUFFIX: Final[str] = ".md"
_EXPECTED_PRODUCT_IDENTITY: Final[dict[str, str]] = {
    "human_executable": "aeat",
    "mcp_server": "cadrumo",
    "mcp_executable": "cadrumo-mcp",
    "mcp_tool_prefix": "cadrumo_",
    "mcp_resource_scheme": "cadrumo://",
    "plugin_identifier": "cadrumo",
    "mcpb_author": PRODUCT_AUTHOR_NAME,
}
_APPROVED_GENERIC_MCP_TOOLS: Final[tuple[str, ...]] = (
    "describe",
    "execute",
    "search",
    "toolsets",
)
_REQUIRED_PRODUCT_DESCRIPTION_CLAIMS: Final[tuple[str, ...]] = (
    "capability",
    "safety",
    "privacy",
    "on_host_storage",
    "human_confirmation",
    "never_files_live",
)
_MODEL_FACING_DESCRIPTION_SURFACES: Final[tuple[str, ...]] = (
    "MCP argument descriptions",
    "MCP prompt descriptions",
    "MCP resource descriptions",
    "MCP tool descriptions",
)
_ENGLISH_LANGUAGE_LABELS: Final[frozenset[str]] = frozenset({"en", "english", "ingles", "inglés"})
_SPANISH_LANGUAGE_LABELS: Final[frozenset[str]] = frozenset({"es", "espanol", "español", "spanish"})
_LANGUAGE_LABEL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?im)^[ \t]*(?:\*\*)?"
    r"(?P<label>English|EN|Ingl[eé]s|Spanish|ES|Espa[nñ]ol)"
    r"(?:\*\*)?[ \t]*:[ \t]*",
)
# Approved English text extracted from the plugin description labeled section.
# Must exactly match what _labeled_product_description returns for the English
# section of _workspace._PLUGIN_DESCRIPTION (i.e. the text after "English: " and
# before the "\nEspañol: " separator, stripped). Approved in exec record S06 Revision 2.
_PLUGIN_DESCRIPTION_EN: Final[str] = (
    "Operate Cadrumo, the deterministic Spanish-tax CLI, from Claude: "
    "grounded search over the bundled BOE/AEAT legal corpus, situation-keyed guided "
    "workflows, and human-confirmed execution of every state-changing step. Cadrumo "
    "is read-only toward AEAT and never files - live submission is impossible and "
    "the taxpayer files outside the app. All financial data stays on-host in "
    "encrypted storage; only what the conversation shows reaches the model "
    "provider. The server advertises an orientation core by default (overview + "
    "contract + search/execute); set the surface option to 'full' to advertise "
    "every verb up front."
)
# Approved Spanish text extracted from the plugin description labeled section.
_PLUGIN_DESCRIPTION_ES: Final[str] = (
    "Opera Cadrumo, la CLI determinista de impuestos españoles, desde "
    "Claude: búsqueda fundamentada sobre el corpus legal BOE/AEAT incluido, flujos "
    "guiados según la situación del contribuyente y ejecución con confirmación "
    "humana de cada paso que modifica el estado. Cadrumo es de solo lectura frente "
    "a la AEAT y nunca presenta declaraciones - la presentación en vivo es "
    "imposible y el contribuyente presenta fuera de la aplicación. Todos los datos "
    "financieros permanecen en el equipo en almacenamiento cifrado; solo lo que "
    "muestra la conversación llega al proveedor del modelo. El servidor anuncia por "
    "defecto un núcleo de orientación (visión general + contrato + buscar/ejecutar); "
    "configura la opción de superficie en 'full' para anunciar todos los verbos "
    "desde el inicio."
)
# Per-claim keyword coverage: the plugin copy (Revision 2) covers all six required
# claims in both English and Spanish — capability, safety, privacy, on_host_storage,
# human_confirmation, and never_files_live. Approved in exec record S06 Revision 2.
# Approved English text extracted from the marketplace description labeled section.
# Must exactly match what _labeled_product_description returns for the English
# section of _workspace._MARKETPLACE_DESCRIPTION (stripped). Approved in S06 Revision 2.
_MARKETPLACE_DESCRIPTION_EN: Final[str] = (
    "Neve plugin marketplace - Claude plugins including the Cadrumo "
    "Spanish-tax assistant: read-only toward AEAT, it never files (the taxpayer "
    "files outside the app), every state change needs human confirmation, financial "
    "data stays on-host in encrypted storage, and only the conversation reaches the "
    "model provider."
)
# Approved Spanish text extracted from the marketplace description labeled section.
_MARKETPLACE_DESCRIPTION_ES: Final[str] = (
    "Marketplace de plugins de Neve - plugins de Claude, incluido el "
    "asistente de impuestos españoles Cadrumo: de solo lectura frente a la AEAT, "
    "nunca presenta declaraciones (el contribuyente presenta fuera de la "
    "aplicación), cada cambio de estado requiere confirmación humana, los datos "
    "financieros permanecen en el equipo en almacenamiento cifrado y solo la "
    "conversación llega al proveedor del modelo."
)
# Per-claim keyword coverage for marketplace description (Revision 2): all six
# required claims pass in both English and Spanish.
# Approved English text extracted from the MCPB manifest description labeled section.
# Must exactly match what _labeled_product_description returns for the English
# section of packaging/mcpb/manifest.json "description" (stripped). Approved in S06 Revision 2.
_MCPB_DESCRIPTION_EN: Final[str] = (
    "Operate Cadrumo, a deterministic Spanish-tax CLI, as an MCP tool "
    "surface: grounded search over the bundled BOE/AEAT legal corpus, "
    "situation-keyed guided workflows, and human-confirmed execution of every "
    "state-changing step. Read-only toward AEAT - it never files; the taxpayer "
    "files outside the app. Financial data stays on-host in encrypted storage, and "
    "only the conversation reaches the model provider."
)
# Approved Spanish text extracted from the MCPB manifest description labeled section.
_MCPB_DESCRIPTION_ES: Final[str] = (
    "Opera Cadrumo, una CLI determinista de impuestos españoles, como "
    "superficie de herramientas MCP: búsqueda fundamentada sobre el corpus legal "
    "BOE/AEAT incluido, flujos guiados según la situación del contribuyente y "
    "ejecución con confirmación humana de cada paso que modifica el estado. De solo "
    "lectura frente a la AEAT - nunca presenta declaraciones; el contribuyente "
    "presenta fuera de la aplicación. Los datos financieros permanecen en el equipo "
    "en almacenamiento cifrado y solo la conversación llega al proveedor del "
    "modelo."
)
# Per-claim keyword coverage for mcpb description (Revision 2): all six required
# claims pass in both EN and ES.
# Approved English text extracted from the MCPB manifest long_description labeled section.
# Must exactly match what _labeled_product_description returns for the English section
# of packaging/mcpb/manifest.json "long_description" (stripped). Approved in S06.
_MCPB_LONG_DESCRIPTION_EN: Final[str] = (
    "The Cadrumo console exposes a deterministic Spanish-tax CLI to any MCP client. "
    "It carries the operator rules, the taxpayer-situation skills, and guided-workflow "
    "prompts; a read-only corpus and terminology search for legal grounding; and a "
    "human-in-the-loop confirmation gate on every state-changing verb. Live submission "
    "to AEAT is permanently impossible - no such tool exists; the taxpayer files outside "
    "the app. All financial data stays on-host in encrypted storage; only the "
    "conversation and the figures the assistant sees reach the LLM client's provider. "
    "The bundle contains the exact digest-pinned Cadrumo distribution cohort."
)
# Approved Spanish text extracted from the MCPB manifest long_description labeled section.
_MCPB_LONG_DESCRIPTION_ES: Final[str] = (
    "La consola de Cadrumo expone una CLI determinista de impuestos españoles a "
    "cualquier cliente MCP. Incorpora las reglas del operador, las habilidades por "
    "situación del contribuyente y los avisos de flujo guiado; una búsqueda de solo "
    "lectura sobre el corpus legal y la terminología para la fundamentación jurídica; "
    "y una puerta de confirmación humana en cada verbo que modifica el estado. La "
    "presentación en vivo ante la AEAT es permanentemente imposible - no existe tal "
    "herramienta; el contribuyente presenta fuera de la aplicación. Todos los datos "
    "financieros permanecen en el equipo en almacenamiento cifrado; solo la conversación "
    "y las cifras que ve el asistente llegan al proveedor del cliente LLM. El paquete "
    "contiene exactamente la cohorte de distribución de Cadrumo, fijada por sus "
    "resúmenes criptográficos."
)
# Per-claim keyword coverage for mcpb long_description: all six claims pass in both
# EN and ES. Approved in S06 as the full-coverage product statement.
_APPROVED_PRODUCT_DESCRIPTION_PAIRS: Final[dict[tuple[str, str], frozenset[tuple[str, str]]]] = {
    # plugin.json description — used by the standalone Claude plugin.
    ("claude_plugin_client_display", "description"): frozenset(
        {
            (_PLUGIN_DESCRIPTION_EN, _PLUGIN_DESCRIPTION_ES),
        }
    ),
    # plugin.json description inside the marketplace plugins/cadrumo subtree.
    ("claude_marketplace_plugin_client_display", "description"): frozenset(
        {
            (_PLUGIN_DESCRIPTION_EN, _PLUGIN_DESCRIPTION_ES),
        }
    ),
    # marketplace.json description — the Neve marketplace manifest.
    ("claude_marketplace_client_display", "description"): frozenset(
        {
            (_MARKETPLACE_DESCRIPTION_EN, _MARKETPLACE_DESCRIPTION_ES),
        }
    ),
    # packaging/mcpb/manifest.json description — short capability summary.
    ("mcpb_client_display", "description"): frozenset(
        {
            (_MCPB_DESCRIPTION_EN, _MCPB_DESCRIPTION_ES),
        }
    ),
    # packaging/mcpb/manifest.json long_description — all six claims covered.
    ("mcpb_client_display", "long_description"): frozenset(
        {
            (_MCPB_LONG_DESCRIPTION_EN, _MCPB_LONG_DESCRIPTION_ES),
        }
    ),
}
_EXPECTED_MODEL_FACING_DESCRIPTION_SHA256: Final[str] = (
    "0538e21e869b1ad89064c787521719aa1d79cfb20e07f23f79dc2e72eca361f0"
)
# Self-locator for the drift remedy. The digest above pins a surface that ANY
# CLI verb or option change moves, so the readers who redden it are usually
# landing something unrelated to packaging; the failure has to name its own
# constant or they cannot act on it.
_PIN_CONSTANT_NAME: Final[str] = "_EXPECTED_MODEL_FACING_DESCRIPTION_SHA256"
_PIN_LOCATOR: Final[str] = "dev/packaging/verify_distribution_identity.py"
_PRODUCT_CLAIM_PATTERNS: Final[dict[str, dict[str, tuple[re.Pattern[str], ...]]]] = {
    "capability": {
        "english": (
            re.compile(r"\bCadrumo\b", re.I),
            re.compile(r"\b(?:Spanish-tax|Spanish tax|tax)\b", re.I),
            re.compile(r"\b(?:MCP|tool surface|guided workflows?|legal corpus|assistant)\b", re.I),
        ),
        "spanish": (
            re.compile(r"\bCadrumo\b", re.I),
            re.compile(r"\b(?:fiscal|fiscales|tributari[ao]s?|impuestos?)\b", re.I),
            re.compile(r"\b(?:MCP|herramientas?|flujos? guiados?|corpus legal|asistente)\b", re.I),
        ),
    },
    "safety": {
        "english": (re.compile(r"\b(?:gated execution|read-only|safety gate)\b", re.I),),
        "spanish": (
            re.compile(r"\b(?:ejecuci[oó]n controlada|solo lectura|sólo lectura|control de seguridad)\b", re.I),
        ),
    },
    "privacy": {
        "english": (
            re.compile(r"\bonly\b[^.]{0,160}\breach(?:es)?\b", re.I),
            re.compile(r"\bprovider\b", re.I),
        ),
        "spanish": (
            re.compile(r"\b(?:solo|sólo|únicamente|únicamente)\b[^.]{0,160}\bllegan?\b", re.I),
            re.compile(r"\bproveedor\b", re.I),
        ),
    },
    "on_host_storage": {
        "english": (
            re.compile(r"\bfinancial data\b", re.I),
            re.compile(r"\b(?:on-host|encrypted storage|local(?:ly)?)\b", re.I),
        ),
        "spanish": (
            re.compile(r"\bdatos financieros\b", re.I),
            re.compile(r"\b(?:equipo|local|almacenamiento cifrado)\b", re.I),
        ),
    },
    "human_confirmation": {
        "english": (
            re.compile(r"\b(?:human-in-the-loop|human-confirmed|human confirmation|confirmation gate)\b", re.I),
        ),
        "spanish": (re.compile(r"\b(?:confirmaci[oó]n humana|intervenci[oó]n humana|una persona confirma)\b", re.I),),
    },
    "never_files_live": {
        "english": (
            re.compile(
                r"\b(?:never files?|does not file|live submission[^.]{0,80}(?:impossible|no such tool))\b",
                re.I,
            ),
        ),
        "spanish": (
            re.compile(r"\b(?:nunca presenta|no presenta|presentaci[oó]n[^.]{0,80}(?:imposible|no existe))\b", re.I),
        ),
    },
}
_MCP_PROJECTION_SCRIPT: Final[str] = """
import json
from pathlib import Path

import cadrumo
import cadrumo_harness

from cadrumo_harness.mcp._dispatch import tool_name_for_command
from cadrumo_harness.mcp._corpus_tools import CORPUS_SEARCH_TOOL, build_corpus_search_tool
from cadrumo_harness.mcp._harness_tools import (
    HARNESS_LOAD_TOOL,
    WHOAMI_TOOL,
    build_harness_floor_tool,
    build_whoami_tool,
)
from cadrumo_harness.mcp._prompts import ORIENTATION_PROMPT_NAME, build_prompt_catalogue, prompt_document
from cadrumo_harness.mcp._resources import (
    list_harness_resource_templates,
    list_harness_resources,
)
from cadrumo_harness.mcp._server import build_meta_sdk_tools, build_sdk_tools, build_server
from cadrumo_harness.mcp._terminology_tools import TERMINOLOGY_SEARCH_TOOL, build_terminology_search_tool
from cadrumo_harness.mcp._tools import build_tool_descriptors

prompts = []
for prompt in build_prompt_catalogue():
    document = prompt_document(prompt.name)
    prompts.append({
        "name": prompt.name,
        "embedded_uris": [embedded.uri for embedded in document.embedded],
    })
resources = [
    {"kind": row.kind.value, "name": row.name, "uri": row.uri}
    for row in list_harness_resources()
]
templates = [
    {"kind": row.kind.value, "name": row.name, "uri_template": row.uri_template}
    for row in list_harness_resource_templates()
]
descriptors = build_tool_descriptors()
sdk_tools = [
    *build_sdk_tools(descriptors),
    *build_meta_sdk_tools(),
    build_harness_floor_tool(),
    build_whoami_tool(),
    build_corpus_search_tool(),
    build_terminology_search_tool(),
]
server_tools = sorted({
    *(row.name for row in descriptors),
    *(row.name for row in build_meta_sdk_tools()),
    HARNESS_LOAD_TOOL,
    WHOAMI_TOOL,
    CORPUS_SEARCH_TOOL,
    TERMINOLOGY_SEARCH_TOOL,
})
model_facing_descriptions = []
for tool in sdk_tools:
    model_facing_descriptions.append({
        "surface": "tool",
        "identifier": tool.name,
        "description": tool.description,
    })
    # The Python attribute is snake_case on MCP SDK 2.x; the "inputSchema" label
    # is NOT a spelling of it. It is the wire-shaped path segment these identity
    # keys are built from (`<tool>:inputSchema.properties.<name>`), and this
    # module's inventory digest is pinned, so renaming the string would silently
    # move the digest while looking like the same cleanup.
    pending = [("inputSchema", tool.input_schema)]
    while pending:
        path, node = pending.pop()
        if isinstance(node, dict):
            description = node.get("description")
            if isinstance(description, str):
                model_facing_descriptions.append({
                    "surface": "argument",
                    "identifier": f"{tool.name}:{path}",
                    "description": description,
                })
            pending.extend((f"{path}.{key}", value) for key, value in node.items())
        elif isinstance(node, list):
            pending.extend((f"{path}[{index}]", value) for index, value in enumerate(node))
for prompt in build_prompt_catalogue():
    model_facing_descriptions.append({
        "surface": "prompt",
        "identifier": prompt.name,
        "description": prompt.description,
    })
    model_facing_descriptions.extend({
        "surface": "argument",
        "identifier": f"prompt:{prompt.name}:{argument.name}",
        "description": argument.description,
    } for argument in prompt.arguments)
model_facing_descriptions.extend({
    "surface": "resource",
    "identifier": row.uri,
    "description": row.description,
} for row in list_harness_resources())
model_facing_descriptions.extend({
    "surface": "resource",
    "identifier": row.uri_template,
    "description": row.description,
} for row in list_harness_resource_templates())
print(json.dumps({
    "package_file": str(Path(cadrumo.__file__).resolve()),
    "harness_package_file": str(Path(cadrumo_harness.__file__).resolve()),
    "mcp_server": build_server(descriptors).name,
    "orientation_prompt": ORIENTATION_PROMPT_NAME,
    "sample_tool": tool_name_for_command("modelo.work.calculate"),
    "server_tools": server_tools,
    "prompts": prompts,
    "resources": resources,
    "templates": templates,
    "model_facing_descriptions": sorted(
        model_facing_descriptions,
        key=lambda row: (row["surface"], row["identifier"], row["description"]),
    ),
}, sort_keys=True))
"""


@dataclass(frozen=True)
class NamespaceObservation:
    """One identifier-bearing authored or generated harness projection."""

    surface: str
    kind: str
    identifier: str
    projected_identifiers: tuple[str, ...]
    location: str
    compliant: bool


@dataclass(frozen=True)
class ProductIdentityObservation:
    """One concrete projection of an accepted MCP product-identity value."""

    surface: str
    value: str


@dataclass(frozen=True)
class ProductIdentityCheck:
    """Comparison of every observed projection with one accepted tuple member."""

    name: str
    expected: str
    observations: tuple[ProductIdentityObservation, ...]
    compliant: bool


@dataclass(frozen=True)
class InventoryParityCheck:
    """Exact-set comparison between one authored inventory and its projection."""

    name: str
    expected: tuple[str, ...]
    observed: tuple[str, ...]
    compliant: bool


@dataclass(frozen=True)
class ProductDescriptionClaimCheck:
    """One required product claim observed in both labeled languages."""

    name: str
    english: bool
    spanish: bool
    parity: bool


@dataclass(frozen=True)
class ProductDescriptionObservation:
    """One real user-facing MCP product-description metadata field."""

    surface: str
    location: str
    field: str
    value: str
    english_label: bool
    spanish_label: bool
    english_text: str
    spanish_text: str
    unlabeled_text: str
    translation_approved: bool
    claims: tuple[ProductDescriptionClaimCheck, ...]
    compliant: bool


@dataclass(frozen=True)
class ModelFacingDescriptionCheck:
    """Exact observation of the preserved English-only operational copy contract."""

    localization_target: bool
    surfaces: tuple[str, ...]
    count: int
    surface_counts: dict[str, int]
    argument_nodes_by_owner: dict[str, int]
    """Per-owner argument-node counts, so a digest change is DECOMPOSABLE.

    The four surface totals answer "arguments moved by two"; they cannot answer
    "which tools". That gap cost a four-message investigation whose conclusion
    was that the answer is unrecoverable: the reference it had to be measured
    against preserved a total and not its composition, so no later diff could
    reach back across it. Emitting the map means the NEXT delta names its tools
    by subtraction instead of by archaeology over commit diffs.

    Keyed by the OWNING entity, which is not always a tool: a tool argument is
    ``<tool>:inputSchema.properties.<name>`` and owns as ``<tool>``, while a
    prompt argument is ``prompt:<prompt-name>:<arg>`` and owns as
    ``prompt:<prompt-name>``. Splitting on the first colon alone collapses every
    prompt argument under a single bogus ``prompt`` key -- a map that sums
    correctly and decomposes nothing.
    """

    sha256: str
    expected_sha256: str
    nonempty: bool
    language_labels_absent: bool
    compliant: bool


@dataclass(frozen=True)
class DistributionIdentityReport:
    """Complete source, generated-artifact, and MCP identity verification report."""

    required_harness_prefix: str
    namespace_observations: tuple[NamespaceObservation, ...]
    inventory_parity_checks: tuple[InventoryParityCheck, ...]
    product_identity_checks: tuple[ProductIdentityCheck, ...]
    product_description_observations: tuple[ProductDescriptionObservation, ...]
    model_facing_description_check: ModelFacingDescriptionCheck

    @property
    def ok(self) -> bool:
        """Return whether both harness namespace and MCP product identity pass."""
        return (
            all(row.compliant for row in self.namespace_observations)
            and all(row.compliant for row in self.inventory_parity_checks)
            and all(row.compliant for row in self.product_identity_checks)
            and all(row.compliant for row in self.product_description_observations)
            and self.model_facing_description_check.compliant
        )

    def failure_lines(self) -> tuple[str, ...]:
        """Return one actionable line per failed check, empty when the report passes.

        The JSON document carries every observation, but a reader who has just
        reddened this gate needs to know which projection drifted and what to do
        about it without parsing sixteen hundred rows. Each line therefore names
        the drifted surface and, where the remedy is a deliberate re-pin rather
        than a code fix, the constant that holds the pin.
        """
        lines: list[str] = []
        for row in self.namespace_observations:
            if not row.compliant:
                lines.append(
                    f"harness namespace: {row.surface}/{row.kind} {row.identifier!r} at {row.location} "
                    f"projects {list(row.projected_identifiers)} without the required "
                    f"{self.required_harness_prefix!r} prefix",
                )
        for parity in self.inventory_parity_checks:
            if not parity.compliant:
                missing = sorted(set(parity.expected) - set(parity.observed))
                unexpected = sorted(set(parity.observed) - set(parity.expected))
                lines.append(
                    f"inventory parity: {parity.name} missing={missing} unexpected={unexpected}",
                )
        for check in self.product_identity_checks:
            if not check.compliant:
                observed = sorted({row.value for row in check.observations if row.value != check.expected})
                lines.append(
                    f"product identity: {check.name} expected {check.expected!r} but observed {observed}",
                )
        for observation in self.product_description_observations:
            if not observation.compliant:
                unmet = sorted(claim.name for claim in observation.claims if not claim.parity)
                lines.append(
                    f"product description: {observation.surface} field {observation.field!r} at "
                    f"{observation.location} is not approved bilingual copy "
                    f"(english_label={observation.english_label}, spanish_label={observation.spanish_label}, "
                    f"claims_without_parity={unmet})",
                )
        lines.extend(_model_facing_failure_lines(self.model_facing_description_check))
        return tuple(lines)

    def to_document(self) -> dict[str, object]:
        """Return the stable JSON-compatible evidence document."""
        namespace = [asdict(row) for row in self.namespace_observations]
        product = [asdict(row) for row in self.product_identity_checks]
        return {
            "schema_version": 1,
            "ok": self.ok,
            "required_harness_prefix": self.required_harness_prefix,
            "authored_inventory": _namespace_summary(
                self.namespace_observations,
                surface="authored",
            ),
            "surface_inventory": {
                surface: _namespace_summary(self.namespace_observations, surface=surface)
                for surface in _surface_names(self.namespace_observations)
            },
            "namespace_observations": namespace,
            "inventory_parity": {
                "ok": all(row.compliant for row in self.inventory_parity_checks),
                "checks": [asdict(row) for row in self.inventory_parity_checks],
            },
            "product_identity": {
                "ok": all(row.compliant for row in self.product_identity_checks),
                "accepted": dict(_EXPECTED_PRODUCT_IDENTITY),
                "approved_generic_mcp_tools": list(_APPROVED_GENERIC_MCP_TOOLS),
                "checks": product,
            },
            "product_descriptions": {
                "ok": all(row.compliant for row in self.product_description_observations),
                "required_languages": ["English", "Spanish"],
                "required_claims": list(_REQUIRED_PRODUCT_DESCRIPTION_CLAIMS),
                "approved_pair_count": sum(len(pairs) for pairs in _APPROVED_PRODUCT_DESCRIPTION_PAIRS.values()),
                "product_review_required": not bool(_APPROVED_PRODUCT_DESCRIPTION_PAIRS),
                "model_facing_descriptions": {
                    **asdict(self.model_facing_description_check),
                    "surfaces": list(self.model_facing_description_check.surfaces),
                },
                "observations": [asdict(row) for row in self.product_description_observations],
            },
        }


def _surface_names(rows: tuple[NamespaceObservation, ...]) -> tuple[str, ...]:
    return tuple(sorted({row.surface for row in rows}))


def _namespace_summary(
    rows: tuple[NamespaceObservation, ...],
    *,
    surface: str,
) -> dict[str, dict[str, object]]:
    relevant = tuple(row for row in rows if row.surface == surface)
    summary: dict[str, dict[str, object]] = {}
    for kind in sorted({row.kind for row in relevant}):
        grouped = tuple(row for row in relevant if row.kind == kind)
        summary[kind] = {
            "count": len(grouped),
            "compliant": sum(row.compliant for row in grouped),
            "failures": [row.identifier for row in grouped if not row.compliant],
        }
    return summary


def _stem(name: str) -> str:
    return name[: -len(_MARKDOWN_SUFFIX)] if name.endswith(_MARKDOWN_SUFFIX) else name


def _skill_name(document: object) -> str:
    parts = str(document).replace("\\", "/").split("/")
    return parts[-2] if len(parts) >= 2 else parts[-1]


def _namespace_observation(
    *,
    surface: str,
    kind: str,
    identifier: str,
    location: str,
    projected_identifiers: tuple[str, ...] = (),
    valid_projection: bool = True,
) -> NamespaceObservation:
    projected = projected_identifiers or (identifier,)
    return NamespaceObservation(
        surface=surface,
        kind=kind,
        identifier=identifier,
        projected_identifiers=projected,
        location=location,
        compliant=valid_projection and all(value.startswith(_REQUIRED_HARNESS_PREFIX) for value in projected),
    )


def _authored_observations() -> tuple[NamespaceObservation, ...]:
    rows: list[NamespaceObservation] = []
    for persona in iter_personas():
        identifier = _stem(persona.name)
        rows.append(
            _namespace_observation(
                surface="authored",
                kind="persona",
                identifier=identifier,
                location=f"personas/{persona.name}",
            ),
        )
    for skill in iter_skill_documents():
        identifier = _skill_name(skill)
        metadata = parse_skill_metadata(skill.read_text(encoding=_UTF_8))
        rows.append(
            _namespace_observation(
                surface="authored",
                kind="skill",
                identifier=identifier,
                projected_identifiers=(identifier, metadata.name),
                location=f"skills/{identifier}/SKILL.md",
            ),
        )
    for rule in iter_operator_rules():
        identifier = _stem(rule.name)
        rows.append(
            _namespace_observation(
                surface="authored",
                kind="rule",
                identifier=identifier,
                location=f"rules/{rule.name}",
            ),
        )
    return tuple(rows)


def _frontmatter_name(path: Path) -> str:
    lines = path.read_text(encoding=_UTF_8).splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"generated agent has no frontmatter: {path}")
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        key, separator, value = stripped.partition(":")
        if separator and key == "name" and value.strip():
            return value.strip()
    raise ValueError(f"generated agent has no frontmatter name: {path}")


def _generated_agent_observations(
    root: Path,
    *,
    surface: str,
    relative_dir: Path,
    frontmatter: bool,
) -> tuple[NamespaceObservation, ...]:
    rows: list[NamespaceObservation] = []
    directory = root / relative_dir
    for path in scan_directory(directory, pattern="*.md"):
        identifier = path.stem
        projected = (identifier, _frontmatter_name(path)) if frontmatter else (identifier,)
        rows.append(
            _namespace_observation(
                surface=surface,
                kind="generated_agent",
                identifier=identifier,
                projected_identifiers=projected,
                location=(relative_dir / path.name).as_posix(),
            ),
        )
    return tuple(rows)


def _generated_skill_observations(
    root: Path,
    *,
    surface: str,
    relative_dir: Path,
) -> tuple[NamespaceObservation, ...]:
    rows: list[NamespaceObservation] = []
    directory = root / relative_dir
    for path in sorted(directory.glob("*/SKILL.md")):
        identifier = path.parent.name
        metadata = parse_skill_metadata(path.read_text(encoding=_UTF_8))
        rows.append(
            _namespace_observation(
                surface=surface,
                kind="skill",
                identifier=identifier,
                projected_identifiers=(identifier, metadata.name),
                location=path.relative_to(root).as_posix(),
            ),
        )
    return tuple(rows)


def _generated_rule_observations(root: Path) -> tuple[NamespaceObservation, ...]:
    rows: list[NamespaceObservation] = []
    relative_dir = Path(".claude") / "rules"
    for path in scan_directory(root / relative_dir, pattern="*.md"):
        rows.append(
            _namespace_observation(
                surface="workspace",
                kind="rule",
                identifier=path.stem,
                location=(relative_dir / path.name).as_posix(),
            ),
        )
    return tuple(rows)


def _generated_observations(
    workspace: Path,
    plugin: Path,
    marketplace: Path,
) -> tuple[NamespaceObservation, ...]:
    marketplace_plugin = marketplace / "plugins" / PRODUCT_IDENTITY.plugin_identifier
    return (
        *_generated_agent_observations(
            workspace,
            surface="workspace",
            relative_dir=Path(".claude") / "agents",
            frontmatter=False,
        ),
        *_generated_skill_observations(
            workspace,
            surface="workspace",
            relative_dir=Path(".claude") / "skills",
        ),
        *_generated_rule_observations(workspace),
        *_generated_agent_observations(
            plugin,
            surface="plugin",
            relative_dir=Path("agents"),
            frontmatter=True,
        ),
        *_generated_skill_observations(
            plugin,
            surface="plugin",
            relative_dir=Path("skills"),
        ),
        *_generated_agent_observations(
            marketplace_plugin,
            surface="marketplace",
            relative_dir=Path("agents"),
            frontmatter=True,
        ),
        *_generated_skill_observations(
            marketplace_plugin,
            surface="marketplace",
            relative_dir=Path("skills"),
        ),
    )


def _mcp_observations(projection: dict[str, object]) -> tuple[NamespaceObservation, ...]:
    rows: list[NamespaceObservation] = []
    prompts = projection.get("prompts")
    resources = projection.get("resources")
    templates = projection.get("templates")
    if not isinstance(prompts, list) or not isinstance(resources, list) or not isinstance(templates, list):
        raise ValueError("MCP projection inventory is incomplete")
    for prompt in prompts:
        if not isinstance(prompt, dict) or not isinstance(prompt.get("name"), str):
            raise ValueError(f"invalid MCP prompt projection: {prompt!r}")
        name = prompt["name"]
        embedded_uris = prompt.get("embedded_uris")
        if not isinstance(embedded_uris, list) or not all(isinstance(uri, str) for uri in embedded_uris):
            raise ValueError(f"invalid MCP prompt embedded resources: {prompt!r}")
        rows.append(
            _namespace_observation(
                surface="mcp_prompts",
                kind="prompt",
                identifier=name,
                location=f"prompts/{name}",
            ),
        )
        for uri in embedded_uris:
            scheme, separator, path = uri.partition("://")
            kind, path_separator, leaf = path.partition("/")
            valid = (
                scheme == "cadrumo"
                and bool(separator)
                and bool(path_separator)
                and kind in {"persona", "rule", "skill"}
                and bool(leaf)
                and "/" not in leaf
            )
            rows.append(
                _namespace_observation(
                    surface="mcp_prompt_resources",
                    kind=f"embedded_{kind}" if valid else "embedded_invalid",
                    identifier=leaf if leaf else uri,
                    location=f"prompts/{name}:{uri}",
                    valid_projection=valid,
                ),
            )
    for resource in resources:
        if (
            not isinstance(resource, dict)
            or not isinstance(resource.get("kind"), str)
            or not isinstance(resource.get("name"), str)
            or not isinstance(resource.get("uri"), str)
        ):
            raise ValueError(f"invalid MCP resource projection: {resource!r}")
        kind = resource["kind"]
        name = resource["name"]
        uri = resource["uri"]
        leaf = uri.rsplit("/", maxsplit=1)[-1]
        valid = uri == f"cadrumo://{kind}/{name}"
        rows.append(
            _namespace_observation(
                surface="mcp_resources",
                kind=f"resource_{kind}",
                identifier=name,
                projected_identifiers=(name, leaf),
                location=uri,
                valid_projection=valid,
            ),
        )
    for template in templates:
        if (
            not isinstance(template, dict)
            or not isinstance(template.get("kind"), str)
            or not isinstance(template.get("name"), str)
            or not isinstance(template.get("uri_template"), str)
        ):
            raise ValueError(f"invalid MCP resource-template projection: {template!r}")
        kind = template["kind"]
        name = template["name"]
        uri_template = template["uri_template"]
        valid = uri_template == f"cadrumo://{kind}/{{name}}" and name == f"cadrumo-{kind}"
        rows.append(
            _namespace_observation(
                surface="mcp_resource_templates",
                kind=f"template_{kind}",
                identifier=name,
                location=uri_template,
                valid_projection=valid,
            ),
        )
    return tuple(rows)


def _surface_identifiers(
    rows: tuple[NamespaceObservation, ...],
    *,
    surface: str,
    kind: str,
) -> tuple[str, ...]:
    return tuple(sorted(row.identifier for row in rows if row.surface == surface and row.kind == kind))


def _surface_projection_signatures(
    rows: tuple[NamespaceObservation, ...],
    *,
    surface: str,
    kind: str,
) -> tuple[str, ...]:
    return tuple(
        sorted("|".join(row.projected_identifiers) for row in rows if row.surface == surface and row.kind == kind)
    )


def _prompt_skill_associations(rows: tuple[NamespaceObservation, ...]) -> tuple[str, ...]:
    associations: list[str] = []
    for row in rows:
        if row.surface != "mcp_prompt_resources" or row.kind != "embedded_skill":
            continue
        prompt_location, separator, _uri = row.location.partition(":")
        prompt_name = prompt_location.removeprefix("prompts/")
        if not separator or not prompt_name:
            associations.append(row.location)
        else:
            associations.append(f"{prompt_name}|{row.identifier}")
    return tuple(sorted(associations))


def _parity_check(
    name: str,
    *,
    expected: tuple[str, ...],
    observed: tuple[str, ...],
) -> InventoryParityCheck:
    return InventoryParityCheck(
        name=name,
        expected=expected,
        observed=observed,
        compliant=observed == expected,
    )


def _inventory_parity_checks(
    rows: tuple[NamespaceObservation, ...],
) -> tuple[InventoryParityCheck, ...]:
    personas = _surface_identifiers(rows, surface="authored", kind="persona")
    skills = _surface_identifiers(rows, surface="authored", kind="skill")
    rules = _surface_identifiers(rows, surface="authored", kind="rule")
    authored_skills = tuple(row for row in rows if row.surface == "authored" and row.kind == "skill")
    skill_signatures = _surface_projection_signatures(rows, surface="authored", kind="skill")
    agent_signatures = tuple(sorted(f"{name}|{name}" for name in personas))
    prompt_skill_associations = tuple(
        sorted(f"{row.projected_identifiers[1]}|{row.identifier}" for row in authored_skills)
    )
    expected_prompts = tuple(sorted((*skills, "cadrumo-empezar")))
    return (
        _parity_check(
            "workspace_agents",
            expected=personas,
            observed=_surface_identifiers(rows, surface="workspace", kind="generated_agent"),
        ),
        _parity_check(
            "plugin_agents",
            expected=personas,
            observed=_surface_identifiers(rows, surface="plugin", kind="generated_agent"),
        ),
        _parity_check(
            "marketplace_agents",
            expected=personas,
            observed=_surface_identifiers(rows, surface="marketplace", kind="generated_agent"),
        ),
        _parity_check(
            "plugin_agent_metadata",
            expected=agent_signatures,
            observed=_surface_projection_signatures(
                rows,
                surface="plugin",
                kind="generated_agent",
            ),
        ),
        _parity_check(
            "marketplace_agent_metadata",
            expected=agent_signatures,
            observed=_surface_projection_signatures(
                rows,
                surface="marketplace",
                kind="generated_agent",
            ),
        ),
        _parity_check(
            "workspace_skills",
            expected=skills,
            observed=_surface_identifiers(rows, surface="workspace", kind="skill"),
        ),
        _parity_check(
            "plugin_skills",
            expected=skills,
            observed=_surface_identifiers(rows, surface="plugin", kind="skill"),
        ),
        _parity_check(
            "marketplace_skills",
            expected=skills,
            observed=_surface_identifiers(rows, surface="marketplace", kind="skill"),
        ),
        _parity_check(
            "workspace_skill_metadata",
            expected=skill_signatures,
            observed=_surface_projection_signatures(rows, surface="workspace", kind="skill"),
        ),
        _parity_check(
            "plugin_skill_metadata",
            expected=skill_signatures,
            observed=_surface_projection_signatures(rows, surface="plugin", kind="skill"),
        ),
        _parity_check(
            "marketplace_skill_metadata",
            expected=skill_signatures,
            observed=_surface_projection_signatures(rows, surface="marketplace", kind="skill"),
        ),
        _parity_check(
            "workspace_rules",
            expected=rules,
            observed=_surface_identifiers(rows, surface="workspace", kind="rule"),
        ),
        _parity_check(
            "mcp_prompts",
            expected=expected_prompts,
            observed=_surface_identifiers(rows, surface="mcp_prompts", kind="prompt"),
        ),
        _parity_check(
            "mcp_persona_resources",
            expected=personas,
            observed=_surface_identifiers(rows, surface="mcp_resources", kind="resource_persona"),
        ),
        _parity_check(
            "mcp_rule_resources",
            expected=rules,
            observed=_surface_identifiers(rows, surface="mcp_resources", kind="resource_rule"),
        ),
        _parity_check(
            "mcp_skill_resources",
            expected=skills,
            observed=_surface_identifiers(rows, surface="mcp_resources", kind="resource_skill"),
        ),
        _parity_check(
            "mcp_prompt_skill_resources",
            expected=skills,
            observed=_surface_identifiers(rows, surface="mcp_prompt_resources", kind="embedded_skill"),
        ),
        _parity_check(
            "mcp_prompt_skill_associations",
            expected=prompt_skill_associations,
            observed=_prompt_skill_associations(rows),
        ),
    )


def _mcp_projection(repo_root: Path, runtime_root: Path) -> dict[str, object]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(PRODUCT_IDENTITY.environment_prefix) and not key.startswith("PYTHON")
    }
    # Both source roots: the MCP server now lives in the sibling cadrumo-harness
    # distribution, so the projection must import THIS revision of each tree
    # rather than whatever copy the active environment happens to carry.
    env["PYTHONPATH"] = os.pathsep.join(
        (str(repo_root / "src"), str(repo_root / _HARNESS_SOURCE_ROOT)),
    )
    env[f"{PRODUCT_IDENTITY.environment_prefix}LOCAL_STORAGE_ROOT"] = str(runtime_root)
    completed = subprocess.run(  # noqa: S603 - fixed current-interpreter probe.
        [sys.executable, "-c", _MCP_PROJECTION_SCRIPT],
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="strict",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "MCP projection inventory failed "
            f"({completed.returncode}): stdout={completed.stdout!r}, stderr={completed.stderr!r}",
        )
    document = json.loads(completed.stdout)
    if not isinstance(document, dict):
        raise ValueError("MCP projection inventory did not return a JSON object")
    package_file = document.get("package_file")
    if not isinstance(package_file, str) or not Path(package_file).resolve(strict=True).is_relative_to(
        repo_root / "src" / PRODUCT_IDENTITY.python_package
    ):
        raise ValueError("MCP projection imported Cadrumo from a different repository revision")
    harness_package_file = document.get("harness_package_file")
    if not isinstance(harness_package_file, str) or not Path(harness_package_file).resolve(strict=True).is_relative_to(
        repo_root / _HARNESS_SOURCE_ROOT / _HARNESS_PYTHON_PACKAGE
    ):
        raise ValueError("MCP projection imported the Cadrumo harness from a different repository revision")
    return document


def _read_json(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding=_UTF_8))
    if not isinstance(document, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return document


def _mcp_config_server(config: dict[str, object]) -> tuple[str, dict[str, object]]:
    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or len(servers) != 1:
        raise ValueError(f"generated MCP config must contain exactly one server: {config!r}")
    name, document = next(iter(servers.items()))
    if not isinstance(name, str) or not isinstance(document, dict):
        raise ValueError(f"generated MCP server config is invalid: {config!r}")
    return name, document


def _uri_scheme(uri: str) -> str:
    scheme, separator, _remainder = uri.partition("://")
    return f"{scheme}://" if separator else uri


def _product_check(
    name: str,
    observations: tuple[ProductIdentityObservation, ...],
) -> ProductIdentityCheck:
    expected = _EXPECTED_PRODUCT_IDENTITY[name]
    return ProductIdentityCheck(
        name=name,
        expected=expected,
        observations=observations,
        compliant=bool(observations) and all(row.value == expected for row in observations),
    )


def _product_identity_checks(
    repo_root: Path,
    plugin: Path,
    marketplace: Path,
    mcp_projection: dict[str, object],
) -> tuple[ProductIdentityCheck, ...]:
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding=_UTF_8))
    scripts = pyproject["project"]["scripts"]
    plugin_manifest = _read_json(plugin / ".claude-plugin" / "plugin.json")
    plugin_server_name, plugin_server = _mcp_config_server(_read_json(plugin / ".mcp.json"))
    marketplace_manifest = _read_json(marketplace / ".claude-plugin" / "marketplace.json")
    marketplace_entry = marketplace_manifest["plugins"][0]
    if not isinstance(marketplace_entry, dict):
        raise ValueError("generated marketplace plugin entry is invalid")
    marketplace_plugin = marketplace / "plugins" / PRODUCT_IDENTITY.plugin_identifier
    marketplace_plugin_manifest = _read_json(marketplace_plugin / ".claude-plugin" / "plugin.json")
    marketplace_server_name, marketplace_server = _mcp_config_server(
        _read_json(marketplace_plugin / ".mcp.json"),
    )
    mcpb_manifest = _read_json(repo_root / "packaging" / "mcpb" / "manifest.json")
    mcpb_tools = mcpb_manifest.get("tools")
    if not isinstance(mcpb_tools, list) or not mcpb_tools:
        raise ValueError("MCPB manifest has no tool declarations")
    mcpb_tool_names: list[str] = []
    for tool in mcpb_tools:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
            raise ValueError(f"invalid MCPB tool declaration: {tool!r}")
        mcpb_tool_names.append(tool["name"])
    mcpb_author = mcpb_manifest.get("author")
    if not isinstance(mcpb_author, dict) or not isinstance(mcpb_author.get("name"), str):
        raise ValueError("MCPB manifest author.name is invalid")

    plugin_args = plugin_server.get("args")
    marketplace_args = marketplace_server.get("args")
    if not isinstance(plugin_args, list) or not plugin_args or not isinstance(plugin_args[-1], str):
        raise ValueError("generated plugin MCP argv is invalid")
    if not isinstance(marketplace_args, list) or not marketplace_args or not isinstance(marketplace_args[-1], str):
        raise ValueError("generated marketplace MCP argv is invalid")

    sample_suffix = "modelo_work_calculate"
    sample_tool = mcp_projection.get("sample_tool")
    if not isinstance(sample_tool, str):
        raise ValueError("MCP projection did not return the sample tool name")
    tool_prefix = sample_tool[: -len(sample_suffix)] if sample_tool.endswith(sample_suffix) else sample_tool
    server_tools = mcp_projection.get("server_tools")
    if (
        not isinstance(server_tools, list)
        or not server_tools
        or not all(isinstance(name, str) for name in server_tools)
    ):
        raise ValueError("MCP projection did not return the server tool inventory")
    resources = mcp_projection.get("resources")
    templates = mcp_projection.get("templates")
    if not isinstance(resources, list) or not isinstance(templates, list):
        raise ValueError("MCP projection did not return resources and templates")
    resource_schemes = tuple(
        ProductIdentityObservation(
            surface=f"mcp_resource:{row['kind']}",
            value=_uri_scheme(row["uri"]),
        )
        for row in resources
        if isinstance(row, dict) and isinstance(row.get("kind"), str) and isinstance(row.get("uri"), str)
    ) + tuple(
        ProductIdentityObservation(
            surface=f"mcp_template:{row['kind']}",
            value=_uri_scheme(row["uri_template"]),
        )
        for row in templates
        if (isinstance(row, dict) and isinstance(row.get("kind"), str) and isinstance(row.get("uri_template"), str))
    )
    human_scripts = tuple(str(name) for name in scripts if name != _EXPECTED_PRODUCT_IDENTITY["mcp_executable"]) or (
        "",
    )

    return (
        _product_check(
            "human_executable",
            (
                ProductIdentityObservation(surface="canonical", value=PRODUCT_IDENTITY.cli_executable),
                *(ProductIdentityObservation(surface="pyproject_script", value=name) for name in human_scripts),
            ),
        ),
        _product_check(
            "mcp_server",
            (
                ProductIdentityObservation(surface="canonical", value=PRODUCT_IDENTITY.mcp_server),
                ProductIdentityObservation(
                    surface="runtime_server",
                    value=str(mcp_projection.get("mcp_server", "")),
                ),
                ProductIdentityObservation(surface="plugin_config", value=plugin_server_name),
                ProductIdentityObservation(surface="marketplace_plugin_config", value=marketplace_server_name),
            ),
        ),
        _product_check(
            "mcp_executable",
            (
                ProductIdentityObservation(surface="canonical", value=PRODUCT_IDENTITY.mcp_executable),
                ProductIdentityObservation(
                    surface="pyproject_script",
                    value=_EXPECTED_PRODUCT_IDENTITY["mcp_executable"]
                    if _EXPECTED_PRODUCT_IDENTITY["mcp_executable"] in scripts
                    else "",
                ),
                ProductIdentityObservation(surface="plugin_config", value=plugin_args[-1]),
                ProductIdentityObservation(surface="marketplace_plugin_config", value=marketplace_args[-1]),
            ),
        ),
        _product_check(
            "mcp_tool_prefix",
            (
                ProductIdentityObservation(
                    surface="canonical",
                    value=f"{PRODUCT_IDENTITY.mcp_tool_prefix}_",
                ),
                ProductIdentityObservation(surface="command_projection", value=tool_prefix),
                *(
                    ProductIdentityObservation(
                        surface=f"runtime_tool:{name}",
                        value=(
                            _EXPECTED_PRODUCT_IDENTITY["mcp_tool_prefix"]
                            if name.startswith(_EXPECTED_PRODUCT_IDENTITY["mcp_tool_prefix"])
                            or name in _APPROVED_GENERIC_MCP_TOOLS
                            else name
                        ),
                    )
                    for name in server_tools
                ),
                *(
                    ProductIdentityObservation(
                        surface=f"mcpb_tool:{name}",
                        value=(
                            _EXPECTED_PRODUCT_IDENTITY["mcp_tool_prefix"]
                            if name.startswith(_EXPECTED_PRODUCT_IDENTITY["mcp_tool_prefix"])
                            or name in _APPROVED_GENERIC_MCP_TOOLS
                            else name
                        ),
                    )
                    for name in mcpb_tool_names
                ),
            ),
        ),
        _product_check(
            "mcp_resource_scheme",
            (
                ProductIdentityObservation(
                    surface="canonical",
                    value=f"{PRODUCT_IDENTITY.mcp_resource_scheme}://",
                ),
                *resource_schemes,
            ),
        ),
        _product_check(
            "plugin_identifier",
            (
                ProductIdentityObservation(surface="canonical", value=PRODUCT_IDENTITY.plugin_identifier),
                ProductIdentityObservation(surface="plugin_manifest", value=str(plugin_manifest.get("name", ""))),
                ProductIdentityObservation(
                    surface="marketplace_entry",
                    value=str(marketplace_entry.get("name", "")),
                ),
                ProductIdentityObservation(
                    surface="marketplace_source_leaf",
                    value=Path(str(marketplace_entry.get("source", ""))).name,
                ),
                ProductIdentityObservation(
                    surface="marketplace_plugin_manifest",
                    value=str(marketplace_plugin_manifest.get("name", "")),
                ),
                ProductIdentityObservation(surface="mcpb_manifest", value=str(mcpb_manifest.get("name", ""))),
            ),
        ),
        _product_check(
            "mcpb_author",
            (ProductIdentityObservation(surface="mcpb_manifest", value=str(mcpb_author["name"])),),
        ),
    )


def _labeled_product_description(value: str) -> tuple[str, str, bool, bool]:
    """Extract exactly one explicitly labeled English and Spanish section."""
    matches = tuple(_LANGUAGE_LABEL_PATTERN.finditer(value))
    sections: dict[str, list[str]] = {"english": [], "spanish": []}
    for index, match in enumerate(matches):
        label = match.group("label").casefold()
        if label in _ENGLISH_LANGUAGE_LABELS:
            language = "english"
        elif label in _SPANISH_LANGUAGE_LABELS:
            language = "spanish"
        else:  # pragma: no cover - the closed regular expression prevents this.
            raise ValueError(f"unsupported language label: {match.group('label')}")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        sections[language].append(value[match.end() : end].strip())
    english_label = len(sections["english"]) == 1
    spanish_label = len(sections["spanish"]) == 1
    english = sections["english"][0] if english_label else ""
    spanish = sections["spanish"][0] if spanish_label else ""
    return english, spanish, english_label, spanish_label


def _product_description_observation(
    *,
    surface: str,
    location: str,
    field: str,
    value: object,
) -> ProductDescriptionObservation:
    text = value if isinstance(value, str) else ""
    english, spanish, english_label, spanish_label = _labeled_product_description(text)
    unlabeled = text if _LANGUAGE_LABEL_PATTERN.search(text) is None else ""
    english_claim_text = english or unlabeled
    translation_approved = (english, spanish) in _APPROVED_PRODUCT_DESCRIPTION_PAIRS.get(
        (surface, field),
        frozenset(),
    )
    claim_rows: list[ProductDescriptionClaimCheck] = []
    for name, patterns in _PRODUCT_CLAIM_PATTERNS.items():
        english_claim = all(pattern.search(english_claim_text) is not None for pattern in patterns["english"])
        spanish_claim = all(pattern.search(spanish) is not None for pattern in patterns["spanish"])
        claim_rows.append(
            ProductDescriptionClaimCheck(
                name=name,
                english=english_claim,
                spanish=spanish_claim,
                parity=english_claim and spanish_claim and translation_approved,
            ),
        )
    claims = tuple(claim_rows)
    return ProductDescriptionObservation(
        surface=surface,
        location=location,
        field=field,
        value=text,
        english_label=english_label,
        spanish_label=spanish_label,
        english_text=english,
        spanish_text=spanish,
        unlabeled_text=unlabeled,
        translation_approved=translation_approved,
        claims=claims,
        compliant=(
            english_label
            and spanish_label
            and bool(english)
            and bool(spanish)
            and translation_approved
            and all(claim.parity for claim in claims)
        ),
    )


def _product_description_observations(
    repo_root: Path,
    plugin: Path,
    marketplace: Path,
) -> tuple[ProductDescriptionObservation, ...]:
    """Read only client-facing product copy from real generated artifacts."""
    plugin_manifest = _read_json(plugin / ".claude-plugin" / "plugin.json")
    marketplace_manifest = _read_json(marketplace / ".claude-plugin" / "marketplace.json")
    marketplace_plugins = marketplace_manifest.get("plugins")
    if not isinstance(marketplace_plugins, list) or len(marketplace_plugins) != 1:
        raise ValueError("generated marketplace must contain exactly one plugin entry")
    marketplace_entry = marketplace_plugins[0]
    if not isinstance(marketplace_entry, dict):
        raise ValueError("generated marketplace plugin entry is invalid")
    marketplace_source = marketplace_entry.get("source")
    if not isinstance(marketplace_source, str):
        raise ValueError("generated marketplace plugin source is invalid")
    marketplace_plugin_manifest = _read_json(
        marketplace / marketplace_source / ".claude-plugin" / "plugin.json",
    )
    mcpb_manifest = _read_json(repo_root / "packaging" / "mcpb" / "manifest.json")
    return (
        _product_description_observation(
            surface="claude_plugin_client_display",
            location="generated/plugin/.claude-plugin/plugin.json",
            field="description",
            value=plugin_manifest.get("description"),
        ),
        _product_description_observation(
            surface="claude_marketplace_client_display",
            location="generated/marketplace/.claude-plugin/marketplace.json",
            field="description",
            value=marketplace_manifest.get("description"),
        ),
        _product_description_observation(
            surface="claude_marketplace_plugin_client_display",
            location=(
                "generated/marketplace/.claude-plugin/marketplace.json:plugins[0].source"
                " -> generated/marketplace/plugins/cadrumo/.claude-plugin/plugin.json"
            ),
            field="description",
            value=marketplace_plugin_manifest.get("description"),
        ),
        _product_description_observation(
            surface="mcpb_client_display",
            location="packaging/mcpb/manifest.json",
            field="description",
            value=mcpb_manifest.get("description"),
        ),
        _product_description_observation(
            surface="mcpb_client_display",
            location="packaging/mcpb/manifest.json",
            field="long_description",
            value=mcpb_manifest.get("long_description"),
        ),
    )


def _model_facing_description_check(
    mcp_projection: dict[str, object],
) -> ModelFacingDescriptionCheck:
    """Verify the real operational description inventory against its frozen contract."""
    raw_rows = mcp_projection.get("model_facing_descriptions")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ValueError("MCP projection did not return model-facing descriptions")
    rows: list[dict[str, str]] = []
    for row in raw_rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("surface"), str)
            or not isinstance(row.get("identifier"), str)
            or not isinstance(row.get("description"), str)
        ):
            raise ValueError(f"invalid model-facing description projection: {row!r}")
        rows.append(
            {
                "surface": row["surface"],
                "identifier": row["identifier"],
                "description": row["description"],
            },
        )
    canonical = json.dumps(
        rows,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode(_UTF_8)
    digest = hashlib.sha256(canonical).hexdigest()
    surfaces = ("argument", "prompt", "resource", "tool")
    surface_counts = {surface: sum(row["surface"] == surface for row in rows) for surface in surfaces}
    argument_nodes_by_owner: dict[str, int] = {}
    for row in rows:
        if row["surface"] != "argument":
            continue
        segments = row["identifier"].split(":")
        # A tool argument's second segment is its schema path; a prompt
        # argument's second segment is the prompt name and must stay in the key.
        owner = segments[0] if len(segments) < 3 else ":".join(segments[:2])
        argument_nodes_by_owner[owner] = argument_nodes_by_owner.get(owner, 0) + 1
    nonempty = all(row["identifier"].strip() and row["description"].strip() for row in rows)
    language_labels_absent = all(_LANGUAGE_LABEL_PATTERN.search(row["description"]) is None for row in rows)
    complete = all(surface_counts[surface] > 0 for surface in surfaces)
    return ModelFacingDescriptionCheck(
        localization_target=False,
        surfaces=_MODEL_FACING_DESCRIPTION_SURFACES,
        count=len(rows),
        surface_counts=surface_counts,
        argument_nodes_by_owner=dict(sorted(argument_nodes_by_owner.items())),
        sha256=digest,
        expected_sha256=_EXPECTED_MODEL_FACING_DESCRIPTION_SHA256,
        nonempty=nonempty,
        language_labels_absent=language_labels_absent,
        compliant=(
            complete and nonempty and language_labels_absent and digest == _EXPECTED_MODEL_FACING_DESCRIPTION_SHA256
        ),
    )


def _model_facing_failure_lines(check: ModelFacingDescriptionCheck) -> tuple[str, ...]:
    """Return actionable lines for a failed model-facing description check.

    The three integrity properties are real defects and say so. A bare digest
    mismatch is different in kind: the pinned inventory is a review tripwire over
    a surface that every CLI verb or option change legitimately moves, so the
    remedy is a deliberate re-pin, and the lines below carry both the observed
    digest and the precondition that makes re-pinning honest.
    """
    if check.compliant:
        return ()
    lines: list[str] = []
    if not check.nonempty:
        lines.append("model-facing descriptions: at least one identifier or description is blank")
    if not check.language_labels_absent:
        lines.append(
            "model-facing descriptions: a language label leaked into model-facing copy, "
            "which is English-only by design",
        )
    missing_surfaces = sorted(surface for surface, count in check.surface_counts.items() if count == 0)
    if missing_surfaces:
        lines.append(f"model-facing descriptions: no descriptions projected for surfaces {missing_surfaces}")
    if check.sha256 != check.expected_sha256:
        lines.append(
            "model-facing descriptions: the pinned inventory digest drifted. "
            f"expected={check.expected_sha256} observed={check.sha256} "
            f"count={check.count} by_surface={dict(sorted(check.surface_counts.items()))}. "
            "A growing count usually means a verb or option was added and a shrinking count that one was "
            "removed. If that change is intended, re-pin "
            f"{_PIN_CONSTANT_NAME} in {_PIN_LOCATOR} to the observed digest, in the SAME commit as the "
            "change that moved the surface. Re-pin ONLY from a tree whose description sources are clean "
            "against HEAD (src/cadrumo/locales, src/cadrumo/entrypoints, "
            "src/cadrumo-harness/src/cadrumo_harness, packaging/mcpb) - the harness source root covers the "
            "authored operator data, the workspace generators, and the MCP server that projects them. "
            "A digest computed over uncommitted work bakes that "
            "work into a committed gate and is wrong the moment it lands.",
        )
    return tuple(lines)


def verify_distribution_identity(repo_root: Path | None = None) -> DistributionIdentityReport:
    """Inventory and verify the current distribution identity without mutation."""
    root = (repo_root or REPO_ROOT).resolve(strict=True)
    imported_root = Path(cadrumo.__file__).resolve(strict=True).parents[2]
    if root != imported_root:
        raise ValueError(
            "repo_root must identify the same repository revision as the imported Cadrumo package: "
            f"requested={root}, imported={imported_root}"
        )
    with tempfile.TemporaryDirectory(prefix="cadrumo-distribution-identity-") as temporary:
        generated = Path(temporary)
        workspace = generated / "workspace"
        plugin = generated / "plugin"
        marketplace = generated / "marketplace"
        materialise_workspace(workspace)
        materialise_plugin(plugin)
        materialise_marketplace(marketplace)
        mcp_projection = _mcp_projection(root, generated / "mcp-runtime")
        namespace = (
            *_authored_observations(),
            *_generated_observations(workspace, plugin, marketplace),
            *_mcp_observations(mcp_projection),
        )
        parity = _inventory_parity_checks(tuple(namespace))
        product = _product_identity_checks(root, plugin, marketplace, mcp_projection)
        descriptions = _product_description_observations(root, plugin, marketplace)
        model_facing = _model_facing_description_check(mcp_projection)
    return DistributionIdentityReport(
        required_harness_prefix=_REQUIRED_HARNESS_PREFIX,
        namespace_observations=tuple(namespace),
        inventory_parity_checks=parity,
        product_identity_checks=product,
        product_description_observations=descriptions,
        model_facing_description_check=model_facing,
    )


def main(argv: list[str] | None = None) -> int:
    """Print the identity report and fail when any required projection drifts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Also write the JSON report to this path.",
    )
    args = parser.parse_args(argv)
    report = verify_distribution_identity()
    payload = json.dumps(report.to_document(), indent=2, sort_keys=True) + "\n"
    print(payload, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding=_UTF_8, newline="\n")
    if report.ok:
        return 0
    # stdout stays the machine document; the human account goes to stderr so a
    # reader who reddened this gate is told what drifted and what to do, instead
    # of a bare exit 1 beside sixteen hundred rows of JSON.
    for line in report.failure_lines():
        print(line, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
