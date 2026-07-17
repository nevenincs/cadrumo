"""Real-behavior coverage for the distribution identity verifier."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from dev.packaging.verify_distribution_identity import (
    _labeled_product_description,
    _product_description_observation,
    verify_distribution_identity,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_real_authored_and_generated_harness_inventory_reports_current_prefix_failure() -> None:
    """The verifier must report today's real generic namespace, not pretend compliance."""
    report = verify_distribution_identity(_REPO_ROOT)
    document = report.to_document()

    assert report.ok is False
    assert document["required_harness_prefix"] == "cadrumo-"
    authored = document["authored_inventory"]
    assert authored["persona"] == {
        "count": 7,
        "compliant": 0,
        "failures": [
            "classifier",
            "coordinator",
            "ledger-groomer",
            "modelo-preparer",
            "onboarding",
            "reconciler",
            "verifier",
        ],
    }
    assert authored["rule"] == {
        "count": 7,
        "compliant": 0,
        "failures": [
            "operator-envelope-reading",
            "operator-grounding",
            "operator-honest-declaration",
            "operator-lifecycle-ordering",
            "operator-operating-rules",
            "operator-orientation-routing",
            "operator-safety-handoff",
        ],
    }
    assert authored["skill"]["count"] == 34
    assert authored["skill"]["compliant"] == 0
    assert len(authored["skill"]["failures"]) == 34
    assert authored["skill"]["failures"][0] == "alta-contribuyente"
    assert authored["skill"]["failures"][-1] == "retenedor-empleador"
    assert "preparar-modelo-200" in authored["skill"]["failures"]
    assert "regularizar-atrasos" in authored["skill"]["failures"]

    surfaces = document["surface_inventory"]
    assert surfaces["workspace"]["generated_agent"]["count"] == 7
    assert surfaces["workspace"]["generated_agent"]["compliant"] == 0
    assert surfaces["workspace"]["rule"]["count"] == 7
    assert surfaces["workspace"]["rule"]["compliant"] == 0
    assert surfaces["workspace"]["skill"]["count"] == 34
    assert surfaces["workspace"]["skill"]["compliant"] == 0
    assert surfaces["plugin"]["generated_agent"]["count"] == 7
    assert surfaces["plugin"]["generated_agent"]["compliant"] == 0
    assert surfaces["plugin"]["skill"]["count"] == 34
    assert surfaces["plugin"]["skill"]["compliant"] == 0
    assert surfaces["marketplace"]["generated_agent"]["count"] == 7
    assert surfaces["marketplace"]["generated_agent"]["compliant"] == 0
    assert surfaces["marketplace"]["skill"]["count"] == 34
    assert surfaces["marketplace"]["skill"]["compliant"] == 0
    assert surfaces["mcp_prompts"]["prompt"] == {
        "count": 35,
        "compliant": 1,
        "failures": surfaces["authored"]["skill"]["failures"],
    }
    assert surfaces["mcp_prompt_resources"]["embedded_rule"] == {
        "count": 1,
        "compliant": 0,
        "failures": ["operating-rules"],
    }
    assert surfaces["mcp_prompt_resources"]["embedded_skill"] == {
        "count": 34,
        "compliant": 0,
        "failures": surfaces["authored"]["skill"]["failures"],
    }
    assert surfaces["mcp_resources"]["resource_persona"]["count"] == 7
    assert surfaces["mcp_resources"]["resource_persona"]["compliant"] == 0
    assert surfaces["mcp_resources"]["resource_rule"]["count"] == 7
    assert surfaces["mcp_resources"]["resource_rule"]["compliant"] == 0
    assert surfaces["mcp_resources"]["resource_skill"]["count"] == 34
    assert surfaces["mcp_resources"]["resource_skill"]["compliant"] == 0
    templates = surfaces["mcp_resource_templates"]
    assert len(templates) == 6
    assert templates["template_persona"] == {"count": 1, "compliant": 1, "failures": []}
    assert templates["template_rule"] == {"count": 1, "compliant": 1, "failures": []}
    assert templates["template_skill"] == {"count": 1, "compliant": 1, "failures": []}
    assert all(template == {"count": 1, "compliant": 1, "failures": []} for template in templates.values())
    assert document["inventory_parity"]["ok"] is True
    assert all(check["compliant"] is True for check in document["inventory_parity"]["checks"])


def test_accepted_mcp_product_tuple_passes_every_real_projection() -> None:
    """Canonical, generated, project-script, resource, and MCPB identities agree."""
    product = verify_distribution_identity(_REPO_ROOT).to_document()["product_identity"]

    assert product["ok"] is True
    assert product["accepted"] == {
        "human_executable": "aeat",
        "mcp_server": "cadrumo",
        "mcp_executable": "cadrumo-mcp",
        "mcp_tool_prefix": "cadrumo_",
        "mcp_resource_scheme": "cadrumo://",
        "plugin_identifier": "cadrumo",
    }
    assert product["approved_generic_mcp_tools"] == ["describe", "execute", "search", "toolsets"]
    assert all(check["compliant"] is True for check in product["checks"])
    tool_check = next(check for check in product["checks"] if check["name"] == "mcp_tool_prefix")
    surfaces = {observation["surface"] for observation in tool_check["observations"]}
    assert {f"runtime_tool:{name}" for name in product["approved_generic_mcp_tools"]} <= surfaces
    assert {"mcpb_tool:search", "mcpb_tool:execute"} <= surfaces


def test_real_client_display_descriptions_report_missing_bilingual_claim_parity() -> None:
    """Every real product-copy field stays failed while its shipped copy is English-only."""
    descriptions = verify_distribution_identity(_REPO_ROOT).to_document()["product_descriptions"]

    assert descriptions["ok"] is False
    assert descriptions["required_languages"] == ["English", "Spanish"]
    assert descriptions["required_claims"] == [
        "capability",
        "safety",
        "privacy",
        "on_host_storage",
        "human_confirmation",
        "never_files_live",
    ]
    assert descriptions["approved_pair_count"] == 0
    assert descriptions["product_review_required"] is True
    assert descriptions["model_facing_descriptions"] == {
        "compliant": True,
        "count": 1625,
        "expected_sha256": "5eaa233019daecfffc215ec482fa36dfdc4763a03b412c00f615cfd45496d9a0",
        "language_labels_absent": True,
        "localization_target": False,
        "nonempty": True,
        "sha256": "5eaa233019daecfffc215ec482fa36dfdc4763a03b412c00f615cfd45496d9a0",
        "surface_counts": {"argument": 1240, "prompt": 35, "resource": 54, "tool": 296},
        "surfaces": [
            "MCP argument descriptions",
            "MCP prompt descriptions",
            "MCP resource descriptions",
            "MCP tool descriptions",
        ],
    }
    observations = descriptions["observations"]
    assert [(row["surface"], row["field"]) for row in observations] == [
        ("claude_plugin_client_display", "description"),
        ("claude_marketplace_client_display", "description"),
        ("claude_marketplace_plugin_client_display", "description"),
        ("mcpb_client_display", "description"),
        ("mcpb_client_display", "long_description"),
    ]
    assert all(row["value"] for row in observations)
    assert all(row["english_label"] is False for row in observations)
    assert all(row["spanish_label"] is False for row in observations)
    assert all(row["english_text"] == "" for row in observations)
    assert all(row["spanish_text"] == "" for row in observations)
    assert all(row["unlabeled_text"] == row["value"] for row in observations)
    assert all(row["translation_approved"] is False for row in observations)
    assert all(row["compliant"] is False for row in observations)
    assert all(
        [claim["name"] for claim in row["claims"]] == descriptions["required_claims"]
        and all(claim["parity"] is False for claim in row["claims"])
        for row in observations
    )
    assert [{claim["name"] for claim in row["claims"] if claim["english"]} for row in observations] == [
        {"capability", "safety", "never_files_live"},
        {"capability"},
        {"capability", "safety", "never_files_live"},
        {"capability", "safety", "never_files_live"},
        set(descriptions["required_claims"]),
    ]
    assert all(all(claim["spanish"] is False for claim in row["claims"]) for row in observations)


def test_supported_english_and_spanish_language_labels_are_parsed() -> None:
    """Both English-language and natural localized section labels are accepted."""
    english, spanish, english_label, spanish_label = _labeled_product_description(
        "Inglés: Approved English copy.\nEspañol: Texto español aprobado."
    )

    assert english == "Approved English copy."
    assert spanish == "Texto español aprobado."
    assert english_label is True
    assert spanish_label is True


def test_unapproved_semantic_contradiction_cannot_pass_keyword_claim_checks() -> None:
    """Product review, not matched vocabulary, is the authority for translation parity."""
    observation = _product_description_observation(
        surface="mcpb_client_display",
        location="review-probe",
        field="long_description",
        value=(
            "English: Cadrumo is not a Spanish tax MCP assistant. There is no gated execution or "
            "read-only safety. It is false that only figures reach the provider. Financial data "
            "does not use on-host encrypted storage. There is no human confirmation. It is false "
            "that Cadrumo never files.\n"
            "Español: Cadrumo no es un asistente fiscal MCP. No existe ejecución controlada ni solo "
            "lectura. Es falso que solo las cifras llegan al proveedor. Los datos financieros no "
            "usan almacenamiento cifrado local. No existe confirmación humana. Es falso que nunca "
            "presenta."
        ),
    )

    assert observation.english_label is True
    assert observation.spanish_label is True
    assert observation.translation_approved is False
    assert observation.compliant is False
    assert all(claim.parity is False for claim in observation.claims)


def test_cli_returns_nonzero_and_emits_the_real_failure_report() -> None:
    """An unprefixed shipped harness must make the production CLI fail closed."""
    completed = subprocess.run(
        [sys.executable, "-m", "dev.packaging.verify_distribution_identity"],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    )

    assert completed.returncode == 1
    assert completed.stderr == ""
    document = json.loads(completed.stdout)
    assert document["ok"] is False
    assert document["authored_inventory"]["persona"]["count"] == 7
    assert document["authored_inventory"]["skill"]["count"] == 34
    assert document["authored_inventory"]["rule"]["count"] == 7
    assert document["product_identity"]["ok"] is True
    assert document["product_descriptions"]["ok"] is False


def test_verifier_rejects_a_mixed_repository_revision(tmp_path: Path) -> None:
    """One report must never combine an imported package with another source root."""
    with pytest.raises(ValueError, match="same repository revision"):
        verify_distribution_identity(tmp_path)
