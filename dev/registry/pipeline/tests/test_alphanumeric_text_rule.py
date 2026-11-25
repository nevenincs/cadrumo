"""A record design's alphanumeric text rule is declared only with the design's own words.

Many AEAT record designs state once, for every alphanumeric and alphabetic
field, that text is written "en mayúsculas, sin caracteres especiales y sin
vocales acentuadas". A render profile declares that rule by quoting the
sentence, and the pipeline finds the quote in the design's own text before the
rule reaches a generated record. These tests hold that contract against the
committed profiles and their hash-verified designs.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.text_fold import normalise_corpus_text
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportAlphanumericText
from cadrumo.domain.calculations.registry.ids import SourceRefId
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ...compiler.authority import compiled_bundled_authority
from ...compiler.validate_evidence import EvidenceValidator
from ..render_profile_loading import load_render_profile
from ..render_profile_model import RenderProfile
from ..render_profile_statement import verify_alphanumeric_text_statement

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROFILES = Path(__file__).resolve().parents[2] / "render_profiles"
_RULE_FRAGMENT = "alphanumeric-text"


@cache
def _sources() -> Mapping[SourceRefId, SourceReference]:
    return compiled_bundled_authority().catalogues.sources


def _profile_directories() -> tuple[Path, ...]:
    return tuple(sorted({path.parent for path in _PROFILES.rglob("*.toml")}))


def _declaring_directories() -> tuple[Path, ...]:
    return tuple(
        directory
        for directory in _profile_directories()
        if any(path.stem.endswith(_RULE_FRAGMENT) for path in directory.glob("*.toml"))
    )


def _verify(profile: RenderProfile) -> None:
    verify_alphanumeric_text_statement(profile, source_root=bundled_path(), sources=_sources())


def test_every_declared_rule_quotes_its_own_design() -> None:
    directories = _declaring_directories()
    assert directories
    for directory in directories:
        profile = load_render_profile(directory)
        rule = profile.alphanumeric_text_rule
        assert rule is not None, directory
        assert rule.alphanumeric_text == ExportAlphanumericText.UPPER_UNACCENTED
        _verify(profile)


def test_a_design_that_states_the_rule_declares_it() -> None:
    """The rule is not optional where the design states it: an undeclared statement is a missed rule."""
    declared = {directory: load_render_profile(directory) for directory in _declaring_directories()}
    (statement,) = {
        profile.alphanumeric_text_rule.official_statement
        for profile in declared.values()
        if profile.alphanumeric_text_rule is not None
    }
    sources = _sources()
    reader = EvidenceValidator(legal_refs={}, source_refs=sources, source_root=bundled_path())
    folded = normalise_corpus_text(statement)
    for directory in _profile_directories():
        if directory in declared:
            continue
        profile = load_render_profile(directory)
        source = sources.get(profile.design_identity.source_ref)
        if source is None:
            continue
        text = reader.source_text(source)
        assert text is None or folded not in text, directory


def test_a_quote_the_design_does_not_contain_refuses() -> None:
    profile = load_render_profile(_declaring_directories()[0])
    rule = profile.alphanumeric_text_rule
    assert rule is not None
    altered = profile.model_copy(
        update={
            "alphanumeric_text_rule": rule.model_copy(
                update={"official_statement": rule.official_statement.replace("sin vocales", "con vocales")}
            )
        }
    )

    with pytest.raises(RegistryValidationError, match="does not contain"):
        _verify(altered)


def test_a_rule_citing_an_uncatalogued_design_refuses() -> None:
    profile = load_render_profile(_declaring_directories()[0])
    identity = profile.design_identity.model_copy(update={"source_ref": "uncatalogued-design"})

    with pytest.raises(RegistryValidationError, match="does not catalogue"):
        _verify(profile.model_copy(update={"design_identity": identity}))


def test_a_profile_declaring_two_rules_refuses(tmp_path: Path) -> None:
    directory = _declaring_directories()[0]
    for path in directory.glob("*.toml"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    (rule_path,) = (path for path in tmp_path.glob("*.toml") if path.stem.endswith(_RULE_FRAGMENT))
    duplicate = rule_path.read_bytes().decode("utf-8").replace(rule_path.stem, f"9999-second-{_RULE_FRAGMENT}")
    (tmp_path / f"9999-second-{_RULE_FRAGMENT}.toml").write_bytes(duplicate.encode("utf-8"))

    with pytest.raises(RegistryValidationError, match="alphanumeric"):
        load_render_profile(tmp_path)
