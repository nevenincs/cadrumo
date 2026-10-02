"""Typed round trips and strict refusal for the development eager baseline."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
)
from cadrumo.domain.calculations.registry.facts.schema import (
    GovernedFact,
    GovernedFactCatalogue,
    GovernedFactFamily,
    MappingFactEntry,
    MappingFactPayload,
)

from ..eager_authority_baseline import (
    EagerAuthorityBaselineError,
    read_eager_authority_baseline,
    write_eager_authority_baseline,
)
from ._authority_generation_support import publishable_artifact

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FACT_ID = "eager-round-trip-atoms"


@pytest.fixture
def artifact() -> AuthorityArtifact:
    original = publishable_artifact("eager-round-trip")
    variant = original.catalogues.facts.facts["spanish-tax-identifier-format"].variants[0]
    payload = MappingFactPayload(
        entries=(
            MappingFactEntry(key="string", value="0.40"),
            MappingFactEntry(key="decimal", value=Decimal("0.40")),
            MappingFactEntry(key="date", value=date(2024, 2, 29)),
            MappingFactEntry(key="true", value=True),
            MappingFactEntry(key="zero", value=0),
            MappingFactEntry(key="false", value=False),
            MappingFactEntry(key="empty", value=""),
        )
    )
    fact = GovernedFact(
        fact_id=_FACT_ID,
        family=GovernedFactFamily.MAPPING,
        variants=(variant.model_copy(update={"variant_id": f"{_FACT_ID}:fixture", "payload": payload}),),
    )
    facts = GovernedFactCatalogue(facts={**original.catalogues.facts.facts, fact.fact_id: fact})
    text = "Synthetic eager-baseline evidence."
    evidence = AuthorityEvidenceProjection(
        legal=tuple(
            PublishedLegalEvidence(
                legal_reference_id=reference_id, anchored_text=text, text_sha256=sha256_hex(text.encode("utf-8"))
            )
            for reference_id in original.catalogues.legal
        )
    )
    return replace(original, catalogues=original.catalogues.model_copy(update={"facts": facts}), evidence=evidence)


def test_write_read_preserves_complete_typed_artifact(tmp_path: Path, artifact: AuthorityArtifact) -> None:
    path = tmp_path / "eager.json"

    write_eager_authority_baseline(path, artifact)
    restored = read_eager_authority_baseline(path)

    assert restored == artifact
    variants = restored.catalogues.facts.facts[_FACT_ID].variants
    assert isinstance(variants, tuple)
    payload = variants[0].payload
    assert isinstance(payload, MappingFactPayload)
    assert isinstance(payload.entries, tuple)
    assert tuple(type(entry.value) for entry in payload.entries) == (str, Decimal, date, bool, int, bool, str)
    assert str(payload.entries[1].value) == "0.40"
    assert restored.modelos[0].revisions == artifact.modelos[0].revisions
    assert restored.profile_schema == artifact.profile_schema


@pytest.mark.parametrize("defect", ["digest", "variants_object", "untagged_atom", "decimal_tag"])
def test_read_refuses_corrupt_or_invalid_wire_values(tmp_path: Path, artifact: AuthorityArtifact, defect: str) -> None:
    path = tmp_path / "eager.json"
    write_eager_authority_baseline(path, artifact)
    frame = json.loads(path.read_bytes())
    fact = frame["payload"]["catalogues"]["facts"]["facts"][_FACT_ID]
    if defect == "digest":
        frame["payload"]["identity_digest"] = "0" * 64
    elif defect == "variants_object":
        fact["variants"] = {}
    elif defect == "untagged_atom":
        fact["variants"][0]["payload"]["entries"][4]["value"] = 0
    else:
        fact["variants"][0]["payload"]["entries"][1]["value"] = {"$decimal": "invalid"}
    if defect != "digest":
        frame["payload_sha256"] = sha256_hex(canonical_json_bytes(frame["payload"]))
    path.write_bytes(canonical_json_bytes(frame))

    with pytest.raises(EagerAuthorityBaselineError, match="failed strict decoding"):
        read_eager_authority_baseline(path)
