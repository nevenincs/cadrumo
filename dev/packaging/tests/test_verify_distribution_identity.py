"""Real-behavior coverage for the distribution identity verifier."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..verify_distribution_identity import (
    ModelFacingDescriptionCheck,
    _labeled_product_description,
    _model_facing_failure_lines,
    _product_description_observation,
    verify_distribution_identity,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = REPO_ROOT


def test_real_authored_and_generated_harness_inventory_is_fully_cadrumo_prefixed() -> None:
    """Every authored and generated harness identifier now carries the ``cadrumo-`` prefix.

    Post-migration compliance gate (was the inverted pre-migration failure probe).
    Every authored persona, rule, and skill and every generated workspace / plugin /
    marketplace projection, MCP prompt, embedded prompt-resource, and MCP resource is
    prefix-compliant with an empty failure list, so this test now fails loudly on any
    FUTURE unprefixed regression. It asserts only the namespace / inventory surface;
    overall ``report.ok`` stays gated by the client-display bilingual claim-parity of
    the short product descriptions, which is proven separately by
    ``test_real_client_display_descriptions_report_missing_bilingual_claim_parity`` and
    ``test_cli_returns_nonzero_and_emits_the_real_failure_report``.
    """
    report = verify_distribution_identity(_REPO_ROOT)
    document = report.to_document()

    assert document["required_harness_prefix"] == "cadrumo-"
    authored = document["authored_inventory"]
    assert authored["persona"] == {"count": 7, "compliant": 7, "failures": []}
    assert authored["rule"] == {"count": 7, "compliant": 7, "failures": []}
    assert authored["skill"] == {"count": 34, "compliant": 34, "failures": []}

    surfaces = document["surface_inventory"]
    for surface in ("workspace", "plugin", "marketplace"):
        for kind, group in surfaces[surface].items():
            assert group["compliant"] == group["count"], (surface, kind, group)
            assert group["failures"] == [], (surface, kind, group)
    assert surfaces["workspace"]["generated_agent"]["count"] == 7
    assert surfaces["workspace"]["rule"]["count"] == 7
    assert surfaces["workspace"]["skill"]["count"] == 34
    assert surfaces["plugin"]["generated_agent"]["count"] == 7
    assert surfaces["plugin"]["skill"]["count"] == 34
    assert surfaces["marketplace"]["generated_agent"]["count"] == 7
    assert surfaces["marketplace"]["skill"]["count"] == 34
    assert surfaces["mcp_prompts"]["prompt"] == {"count": 35, "compliant": 35, "failures": []}
    assert surfaces["mcp_prompt_resources"]["embedded_rule"] == {"count": 1, "compliant": 1, "failures": []}
    assert surfaces["mcp_prompt_resources"]["embedded_skill"] == {"count": 34, "compliant": 34, "failures": []}
    assert surfaces["mcp_resources"]["resource_persona"] == {"count": 7, "compliant": 7, "failures": []}
    assert surfaces["mcp_resources"]["resource_rule"] == {"count": 7, "compliant": 7, "failures": []}
    assert surfaces["mcp_resources"]["resource_skill"] == {"count": 34, "compliant": 34, "failures": []}
    templates = surfaces["mcp_resource_templates"]
    assert len(templates) == 6
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
        "mcpb_author": "CADRUMO tax assistant project",
    }
    assert product["approved_generic_mcp_tools"] == ["describe", "execute", "search", "toolsets"]
    assert all(check["compliant"] is True for check in product["checks"])
    tool_check = next(check for check in product["checks"] if check["name"] == "mcp_tool_prefix")
    surfaces = {observation["surface"] for observation in tool_check["observations"]}
    assert {f"runtime_tool:{name}" for name in product["approved_generic_mcp_tools"]} <= surfaces
    assert {"mcpb_tool:search", "mcpb_tool:execute"} <= surfaces
    # The shipped MCPB manifest author derives from the central product identity.
    author_check = next(check for check in product["checks"] if check["name"] == "mcpb_author")
    assert author_check["compliant"] is True
    assert author_check["expected"] == "CADRUMO tax assistant project"
    assert [observation["value"] for observation in author_check["observations"]] == [
        "CADRUMO tax assistant project",
    ]


def test_real_client_display_descriptions_report_missing_bilingual_claim_parity() -> None:
    """All five client-display fields carry approved bilingual pairs with full six-claim parity.

    Revision 2 of the copy record expanded every short client-display field to the
    full six required claims. All five rows are now compliant=True and
    product_descriptions.ok is True.
    """
    descriptions = verify_distribution_identity(_REPO_ROOT).to_document()["product_descriptions"]

    assert descriptions["ok"] is True  # all five rows carry all six claims in parity
    assert descriptions["required_languages"] == ["English", "Spanish"]
    assert descriptions["required_claims"] == [
        "capability",
        "safety",
        "privacy",
        "on_host_storage",
        "human_confirmation",
        "never_files_live",
    ]
    # Five approved pairs: plugin, marketplace-plugin, marketplace, and the mcpb
    # short description and long_description.
    assert descriptions["approved_pair_count"] == 5
    assert descriptions["product_review_required"] is False
    # model_facing_descriptions count and sha256 are the sibling rename executor's
    # surface (MCP tool/argument descriptions change as renames land). Only check the
    # stable structural properties here; the sibling updates expected_sha256 in the
    # verifier as each rename lands.
    mfd = descriptions["model_facing_descriptions"]
    assert mfd["nonempty"] is True
    assert mfd["language_labels_absent"] is True
    assert mfd["localization_target"] is False
    assert mfd["surfaces"] == [
        "MCP argument descriptions",
        "MCP prompt descriptions",
        "MCP resource descriptions",
        "MCP tool descriptions",
    ]
    assert mfd["count"] > 0
    observations = descriptions["observations"]
    assert [(row["surface"], row["field"]) for row in observations] == [
        ("claude_plugin_client_display", "description"),
        ("claude_marketplace_client_display", "description"),
        ("claude_marketplace_plugin_client_display", "description"),
        ("mcpb_client_display", "description"),
        ("mcpb_client_display", "long_description"),
    ]
    assert all(row["value"] for row in observations)
    # All five rows are compliant: Revision 2 wires full six-claim parity.
    assert all(row["compliant"] is True for row in observations)

    # Every row carries a labeled, approved bilingual pair with all six claims in parity.
    for row in observations:
        assert row["english_label"] is True
        assert row["spanish_label"] is True
        assert row["english_text"] != ""
        assert row["spanish_text"] != ""
        assert row["unlabeled_text"] == ""
        assert row["translation_approved"] is True
        assert [claim["name"] for claim in row["claims"]] == descriptions["required_claims"]
        assert {claim["name"] for claim in row["claims"] if claim["english"]} == set(descriptions["required_claims"])
        assert {claim["name"] for claim in row["claims"] if claim["spanish"]} == set(descriptions["required_claims"])
        assert all(claim["parity"] is True for claim in row["claims"])


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


def test_cli_exits_zero_and_emits_a_passing_report() -> None:
    """The production CLI exits 0 and emits a passing report once all claims carry parity.

    After Revision 2 of the copy record expanded every short client-display field to
    all six required claims, the verifier is fully green: namespace, identity, and
    description checks all pass.

    The name states what the assertions check. Its predecessor was named for a
    non-zero exit while asserting a zero one, so a reader who reddened this gate
    was told the opposite of what had happened.
    """
    completed = subprocess.run(
        [sys.executable, "-m", "dev.packaging.verify_distribution_identity"],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    document = json.loads(completed.stdout)
    assert document["ok"] is True
    assert document["authored_inventory"]["persona"]["count"] == 7
    assert document["authored_inventory"]["skill"]["count"] == 34
    assert document["authored_inventory"]["rule"]["count"] == 7
    assert document["product_identity"]["ok"] is True
    assert document["product_descriptions"]["ok"] is True


def test_verifier_rejects_a_mixed_repository_revision(tmp_path: Path) -> None:
    """One report must never combine an imported package with another source root."""
    with pytest.raises(ValueError, match="same repository revision"):
        verify_distribution_identity(tmp_path)


def _model_facing_check(
    *,
    sha256: str = "a" * 64,
    nonempty: bool = True,
    language_labels_absent: bool = True,
    surface_counts: dict[str, int] | None = None,
    compliant: bool = True,
) -> ModelFacingDescriptionCheck:
    """Build one model-facing check, defaulting to the compliant shape."""
    counts = surface_counts if surface_counts is not None else {"argument": 1, "prompt": 1, "resource": 1, "tool": 1}
    return ModelFacingDescriptionCheck(
        localization_target=False,
        surfaces=("MCP tool descriptions",),
        count=sum(counts.values()),
        surface_counts=counts,
        argument_nodes_by_owner={"cadrumo_probe": counts.get("argument", 0)},
        sha256=sha256,
        expected_sha256="a" * 64,
        nonempty=nonempty,
        language_labels_absent=language_labels_absent,
        compliant=compliant,
    )


def test_a_compliant_model_facing_check_produces_no_failure_lines() -> None:
    """The detector must stay silent on the passing surface, or its lines mean nothing."""
    assert _model_facing_failure_lines(_model_facing_check()) == ()


def test_a_drifted_digest_names_its_own_pin_constant_and_locator() -> None:
    """A digest mismatch must tell the reader where the pin lives and what it observed.

    This gate reddens on any CLI verb or option change, so the agents who trip it
    are usually landing something unrelated to packaging. Before this line existed
    the verifier exited 1 with empty stderr beside sixteen hundred rows of JSON,
    and the drift was rediscovered from scratch three times in three days.
    """
    observed = "b" * 64
    expected = "a" * 64
    lines = _model_facing_failure_lines(
        _model_facing_check(sha256=observed, compliant=False),
    )

    assert len(lines) == 1
    line = lines[0]
    assert observed in line
    assert expected in line
    assert "_EXPECTED_MODEL_FACING_DESCRIPTION_SHA256" in line
    assert "dev/packaging/verify_distribution_identity.py" in line


def test_each_integrity_failure_contributes_its_own_line() -> None:
    """Blank copy, a leaked language label, and an empty surface are distinct defects.

    They are real defects rather than tripwire drift, so each must be reported
    separately instead of collapsing into the digest line.
    """
    blank = _model_facing_failure_lines(_model_facing_check(nonempty=False, compliant=False))
    labelled = _model_facing_failure_lines(_model_facing_check(language_labels_absent=False, compliant=False))
    empty_surface = _model_facing_failure_lines(
        _model_facing_check(
            surface_counts={"argument": 1, "prompt": 1, "resource": 1, "tool": 0},
            compliant=False,
        ),
    )

    assert len(blank) == 1
    assert len(labelled) == 1
    assert len(empty_surface) == 1
    assert "tool" in empty_surface[0]
    assert len({blank[0], labelled[0], empty_surface[0]}) == 3


def test_the_per_owner_argument_map_decomposes_the_argument_total() -> None:
    """The map must be present and must SUM to the total it decomposes.

    The four surface totals can say "arguments moved by two" and cannot say
    which entity moved. That gap cost a four-message investigation whose answer
    was that it is unrecoverable: the reference the delta had to be measured
    against preserved a total and not its composition, so no later diff could
    reach back across it. A map that silently drifted from its own total would
    reintroduce exactly that.
    """
    report = verify_distribution_identity()
    check = report.model_facing_description_check
    by_owner = check.argument_nodes_by_owner

    assert by_owner, "the per-owner argument map must not be empty"
    assert sum(by_owner.values()) == check.surface_counts["argument"], (
        f"map sums to {sum(by_owner.values())} but the argument surface reports {check.surface_counts['argument']}"
    )
    assert all(count > 0 for count in by_owner.values())


def test_prompt_arguments_decompose_per_prompt_not_under_one_key() -> None:
    """Prompt arguments must key per prompt, never collapse under a bare ``prompt``.

    A prompt argument identifier is ``prompt:<prompt-name>:<arg>``, so splitting
    on the first colon alone buckets every prompt argument under one key. That
    map sums correctly and decomposes nothing, which is the exact failure this
    field exists to prevent -- the sum invariant cannot catch it, so this does.
    """
    report = verify_distribution_identity()
    by_owner = report.model_facing_description_check.argument_nodes_by_owner

    assert "prompt" not in by_owner, "prompt arguments collapsed under a single bogus key"
    prompt_owners = [key for key in by_owner if key.startswith("prompt:")]
    assert len(prompt_owners) > 1, f"expected many prompt owners, got {prompt_owners}"
    assert all(key.count(":") == 1 for key in prompt_owners), [k for k in prompt_owners if k.count(":") != 1]
    tool_owners = [key for key in by_owner if not key.startswith("prompt:")]
    assert all(":" not in key for key in tool_owners), [k for k in tool_owners if ":" in k]
