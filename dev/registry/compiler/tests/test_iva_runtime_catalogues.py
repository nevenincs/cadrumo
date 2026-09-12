"""Compiler-owned tests for the authored IVA runtime catalogues.

The product domain consumes the published authority and its public resolvers.
The mutable TOML shape, schema refusals, and authoring-corpus checks belong to
the development compiler, which can exercise them against isolated copies of
the registry without teaching runtime code how to read source files.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.runtime_catalogues import (
    CountryVocabularyRecord,
    RuntimeRegistryCatalogues,
    TerritoryCarveOut,
)
from cadrumo.domain.iva.country_vocabulary import normalise_printed_country_name

from ..authority import compile_validated_authority
from ..legal_grounding import legal_reference_quotes_corpus
from ..runtime_catalogues import compile_runtime_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CARVE_OUT_LEGAL_REFERENCE = "ley-37-1992:art-3.tres"
_RUNTIME_FILES = (
    ("iva", "country_names.toml"),
    ("iva", "territories.toml"),
    ("iva", "territory_carve_outs.toml"),
    ("iva", "catalogues.toml"),
    ("iva", "place_of_supply.toml"),
    ("apoderamientos", "scopes.toml"),
    ("legal", "ley-58-2003-recargo-bands.toml"),
)


def _bundled_registry_root() -> Path:
    """Return the immutable registry tree shipped with the package."""
    return bundled_path("registry", "aeat")


def _runtime_root(tmp_path: Path) -> Path:
    """Copy the runtime tables needed by ``compile_runtime_catalogues``."""
    source = _bundled_registry_root()
    root = tmp_path / "runtime" / "registry" / "aeat"
    for relative in _RUNTIME_FILES:
        source_path = source.joinpath(*relative)
        target = root.joinpath(*relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
    return root


def _authoring_root(tmp_path: Path) -> Path:
    """Copy the complete registry tree for full candidate-authority checks."""
    root = tmp_path / "authoring" / "registry" / "aeat"
    root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_bundled_registry_root(), root)
    return root


def _replace(path: Path, old: str, new: str) -> None:
    """Replace one exact authored fragment in an isolated fixture."""
    payload = path.read_text(encoding="utf-8")
    assert payload.count(old) == 1, f"mutation anchor {old!r} is not unique in {path}"
    path.write_text(payload.replace(old, new, 1), encoding="utf-8")


def _country_table(*rows: tuple[str, str, tuple[str, ...]]) -> str:
    """Render the small country table used by compiler schema probes."""
    blocks: list[str] = []
    for code, alpha3, names in rows:
        names_literal = ", ".join(f'"{name}"' for name in names)
        blocks.append(
            "\n".join(
                [
                    "[[country]]",
                    f'code = "{code}"',
                    f'alpha3 = "{alpha3}"',
                    f"names = [{names_literal}]",
                ]
            )
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "country = []\n")


def _write_country_table(root: Path, *rows: tuple[str, str, tuple[str, ...]]) -> None:
    """Overwrite the isolated country table with the supplied rows."""
    (root / "iva" / "country_names.toml").write_text(_country_table(*rows), encoding="utf-8")


def _carve_out_table(*assimilations: tuple[str, str]) -> str:
    """Render carve-outs whose only disposition is an assimilation pointer."""
    blocks = [
        "\n".join(
            [
                "[[carve_out]]",
                f'code = "{code}"',
                f'name = "Synthetic {code}"',
                f'assimilated_to = "{parent}"',
                f'legal_refs = ["{_CARVE_OUT_LEGAL_REFERENCE}"]',
            ]
        )
        for code, parent in assimilations
    ]
    return "\n\n".join(blocks) + "\n"


def _compiled_carve_outs(tmp_path: Path, *assimilations: tuple[str, str]) -> Mapping[str, TerritoryCarveOut]:
    """Compile an isolated carve-out table through the public compiler entrypoint."""
    root = _runtime_root(tmp_path)
    (root / "iva" / "territory_carve_outs.toml").write_text(
        _carve_out_table(*assimilations),
        encoding="utf-8",
    )
    return compile_runtime_catalogues(root).territory_carve_outs


def _country_catalogues(*records: CountryVocabularyRecord) -> RuntimeRegistryCatalogues:
    """Build the public typed runtime projection used by schema probes."""
    return RuntimeRegistryCatalogues(countries={record.code: record for record in records})


def test_a_two_row_ring_is_refused_by_the_compiler(tmp_path: Path) -> None:
    with pytest.raises(RegistryValidationError, match="closes into a cycle"):
        _compiled_carve_outs(tmp_path, ("MC", "IM"), ("IM", "MC"))


def test_a_longer_ring_is_refused_by_the_compiler(tmp_path: Path) -> None:
    with pytest.raises(RegistryValidationError, match="closes into a cycle"):
        _compiled_carve_outs(tmp_path, ("MC", "IM"), ("IM", "JE"), ("JE", "MC"))


def test_the_self_pointer_keeps_its_own_compiler_message(tmp_path: Path) -> None:
    with pytest.raises(RegistryValidationError, match="assimilated to itself"):
        _compiled_carve_outs(tmp_path, ("MC", "MC"))


def test_a_chain_that_terminates_still_compiles(tmp_path: Path) -> None:
    rows = _compiled_carve_outs(tmp_path, ("MC", "FR"), ("IM", "MC"))

    assert rows["MC"].assimilated_to == "FR"
    assert rows["IM"].assimilated_to == "MC"


def test_the_bundled_table_is_free_of_rings() -> None:
    rows = compile_runtime_catalogues(_bundled_registry_root()).territory_carve_outs

    assert rows["MC"].assimilated_to == "FR"


def test_the_compiler_wraps_a_missing_runtime_catalogue_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing-iva-catalogue"

    with pytest.raises(RegistryValidationError, match="cannot compile runtime catalogue"):
        compile_runtime_catalogues(missing)


def test_the_compiler_refuses_an_unknown_legal_reference(tmp_path: Path) -> None:
    root = _authoring_root(tmp_path)
    _replace(
        root / "iva" / "catalogues.toml",
        'legal_reference = "ley-37-1992:art-90"',
        'legal_reference = "ley-37-1992:art-invented"',
    )

    with pytest.raises(RegistryValidationError, match="unknown legal id"):
        compile_validated_authority(root, bundled_path())


def test_the_compiler_refuses_an_unquoted_verified_citation(tmp_path: Path) -> None:
    root = _runtime_root(tmp_path)
    _replace(
        root / "iva" / "catalogues.toml",
        'quoted_text = "Artículo 90. Tipo impositivo general. Uno. El Impuesto se exigirá al tipo del 21 por ciento, salvo lo dispuesto en el artículo siguiente. Dos. El tipo impositivo aplicable a cada operación será el vigente en el momento del devengo. Tres."',
        'quoted_text = ""',
    )

    with pytest.raises(ValidationError, match="verified IVA citation requires quotation"):
        compile_runtime_catalogues(root)


def test_the_compiler_exposes_a_mutated_quotation_to_the_public_grounding_check(tmp_path: Path) -> None:
    root = _authoring_root(tmp_path)
    _replace(
        root / "iva" / "catalogues.toml",
        "El Impuesto se exigirá al tipo del 21 por ciento",
        "El Impuesto se exigirá al tipo del 25 por ciento",
    )

    authority = compile_validated_authority(root, bundled_path())
    citation = authority.catalogues.runtime.iva_regulations["domestic_general"].citations[0]
    reference = authority.catalogues.legal[citation.legal_reference]

    assert not legal_reference_quotes_corpus(reference, citation.quoted_text, source_root=bundled_path())


def test_two_countries_claiming_one_normalised_name_are_refused() -> None:
    with pytest.raises(RegistryValidationError, match="multiple countries"):
        _country_catalogues(
            CountryVocabularyRecord(code="MX", alpha3="MEX", names=("México",)),
            CountryVocabularyRecord(code="AR", alpha3="ARG", names=("Mexico",)),
        )


def test_one_country_repeating_a_spelling_is_accepted() -> None:
    catalogue = _country_catalogues(
        CountryVocabularyRecord(code="MX", alpha3="MEX", names=("México", "Mexico")),
    )
    indexed = {
        normalise_printed_country_name(name): record.code
        for record in catalogue.countries.values()
        for name in record.names
    }

    assert indexed == {"mexico": "MX"}


@pytest.mark.parametrize(
    "record",
    [
        {"alpha3": "NWR", "names": ["Nowhere"]},
        {"code": "", "alpha3": "NWR", "names": ["Nowhere"]},
        {"code": "DEU", "alpha3": "NWR", "names": ["Nowhere"]},
        {"code": "D1", "alpha3": "NWR", "names": ["Nowhere"]},
    ],
)
def test_a_country_record_without_a_valid_alpha_two_code_is_refused(record: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CountryVocabularyRecord.model_validate(record)


def test_a_country_carrying_no_printed_name_is_refused() -> None:
    with pytest.raises(ValidationError):
        CountryVocabularyRecord.model_validate({"code": "DE", "alpha3": "DEU", "names": []})


def test_a_blank_printed_name_is_refused() -> None:
    with pytest.raises(RegistryValidationError, match="blank printed name"):
        _country_catalogues(CountryVocabularyRecord(code="DE", alpha3="DEU", names=("  ",)))


def test_an_empty_vocabulary_is_refused(tmp_path: Path) -> None:
    root = _runtime_root(tmp_path)
    _write_country_table(root)

    with pytest.raises(RegistryValidationError, match="non-empty array"):
        compile_runtime_catalogues(root)


def test_the_bundled_vocabulary_survives_its_schema_refusals() -> None:
    runtime = compile_runtime_catalogues(_bundled_registry_root())
    indexed = {
        normalise_printed_country_name(name): record.code
        for record in runtime.countries.values()
        for name in record.names
    }

    assert len(indexed) > len({code for code in indexed.values()})


def test_no_bundled_country_record_repeats_its_own_normalised_name() -> None:
    runtime = compile_runtime_catalogues(_bundled_registry_root())

    for code, record in runtime.countries.items():
        seen: dict[str, str] = {}
        for name in record.names:
            folded = normalise_printed_country_name(name)
            twin = seen.get(folded)
            assert twin is None, f"{code}: {name!r} is the fold of {twin!r}"
            seen[folded] = name


def test_every_bundled_record_carries_an_alpha3_code() -> None:
    records = compile_runtime_catalogues(_bundled_registry_root()).countries.values()

    assert tuple(records)
    assert all(record.alpha3 for record in records)


def test_the_bundled_alpha3_column_names_each_country_exactly_once() -> None:
    records = compile_runtime_catalogues(_bundled_registry_root()).countries.values()
    codes = tuple(record.code for record in records)
    alpha3 = tuple(record.alpha3 for record in records)

    assert len(set(codes)) == len(codes)
    assert len(set(alpha3)) == len(alpha3)


def test_northern_ireland_is_absent_from_both_bundled_columns() -> None:
    records = compile_runtime_catalogues(_bundled_registry_root()).countries.values()
    printed = {
        normalise_printed_country_name(name): record.code
        for record in records
        for name in record.names
    }
    alpha3 = {record.alpha3: record.code for record in records}

    assert "XI" not in printed.values()
    assert "XI" not in alpha3.values()


def test_a_country_record_without_an_alpha3_code_is_refused() -> None:
    with pytest.raises(ValidationError):
        CountryVocabularyRecord.model_validate({"code": "DE", "names": ["Alemania"]})


@pytest.mark.parametrize("alpha3", ["", "DE", "DEUT", "D3U", "  "])
def test_a_malformed_alpha3_is_refused(alpha3: str) -> None:
    with pytest.raises(ValidationError):
        CountryVocabularyRecord.model_validate({"code": "DE", "alpha3": alpha3, "names": ["Alemania"]})


def test_two_countries_claiming_one_alpha3_are_refused() -> None:
    with pytest.raises(RegistryValidationError, match="alpha-3"):
        _country_catalogues(
            CountryVocabularyRecord(code="DE", alpha3="DEU", names=("Alemania",)),
            CountryVocabularyRecord(code="AT", alpha3="DEU", names=("Österreich",)),
        )


def test_one_country_stating_two_alpha3_codes_is_refused(tmp_path: Path) -> None:
    root = _runtime_root(tmp_path)
    _write_country_table(root, ("DE", "DEU", ("Alemania",)), ("DE", "GER", ("Germany",)))

    with pytest.raises(RegistryValidationError, match="repeats key"):
        compile_runtime_catalogues(root)


def test_a_country_with_one_alpha3_code_is_accepted() -> None:
    catalogue = _country_catalogues(CountryVocabularyRecord(code="DE", alpha3="DEU", names=("Alemania",)))

    assert {record.alpha3: record.code for record in catalogue.countries.values()} == {"DEU": "DE"}


def test_a_record_without_an_alpha_two_code_is_refused() -> None:
    with pytest.raises(ValidationError):
        CountryVocabularyRecord.model_validate({"alpha3": "DEU", "names": ["Alemania"]})


def test_an_empty_alpha3_column_is_refused(tmp_path: Path) -> None:
    root = _runtime_root(tmp_path)
    _write_country_table(root)

    with pytest.raises(RegistryValidationError, match="non-empty array"):
        compile_runtime_catalogues(root)
