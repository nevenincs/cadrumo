"""Detector teeth for the casilla shard generator.

Each test plants a defect the generator exists to catch, and asserts it is
caught. Every planted defect below is one this corpus has actually taken: a
record that grew in its middle and moved every later positional id, a caption
whose line break broke out of its TOML comment, AEAT's own double spaces
collapsed by an over-eager normaliser, a box number that is not five digits,
and a meaning rewritten at an address that did not move.

The sheets are constructed, not read from a workbook. A gate that can only
reach the emission through a real design cannot plant anything in it, and an
unplantable gate proves only that the happy path runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.record_design_schema import (
    RecordDesignField,
    RecordDesignSheet,
)
from dev.registry.authoring.casilla_shard_generation import (
    GenerationRefused,
    WaveSpec,
    audit_sheet,
    derive_number,
    emit_records,
    is_structural,
    normalise_for_drift,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

SEGMENTO = "T99001000"
REVISION = "2025"
LEGAL_REFS = '["orden-test-1-2026:art-1", "ley-test-2-2014:art-9"]'


def field(offset: int, length: int, description: str, *, type_code: str = "N",
          ordinal: str | None = None, content: str | None = None) -> RecordDesignField:
    return RecordDesignField(
        sheet=SEGMENTO,
        row=offset,
        ordinal=ordinal,
        offset=offset,
        length=length,
        type_code=type_code,
        description=description,
        content=content,
    )


def envelope() -> list[RecordDesignField]:
    """The identifier rows every AEAT record opens with."""
    return [
        field(1, 2, "Inicio del identificador de modelo y página.", type_code="An"),
        field(3, 13, "Constante", type_code="An"),
    ]


def sheet_of(rows: list[RecordDesignField], *, total: int | None = None) -> RecordDesignSheet:
    body = envelope() + rows
    tail_at = body[-1].offset + body[-1].length
    body.append(field(tail_at, 12, "Fin de registro.", type_code="An"))
    span = tail_at + 12 - 1
    return RecordDesignSheet(
        name=SEGMENTO, fields=tuple(body), total_positions=total if total is not None else span
    )


def spec_for(tmp_path: Path, *, adjudicate: bool = False) -> WaveSpec:
    prior = tmp_path / "prior"
    prior.mkdir(exist_ok=True)
    return WaveSpec(
        design_path=tmp_path / "unused.xlsx",
        prior_casillas_dir=prior,
        out_dir=tmp_path / "out",
        revision_id=REVISION,
        legal_refs=LEGAL_REFS,
        records=(SEGMENTO,),
        headers={SEGMENTO: "# planted fixture"},
        adjudicated_sections=(
            {SEGMENTO: ("liquidacion", "planted")} if adjudicate else {}
        ),
    )


def write_prior(spec: WaveSpec, rows: list[tuple[str, str, str]]) -> None:
    """Write a prior edition shard: (number, caption, data_type) per row."""
    blocks = [
        f"# @0+0 N. {caption}\n"
        f'[[revisions."2024".casillas]]\n'
        f'id = "{SEGMENTO}:{number}"\n'
        f'number = "{number}"\n'
        f'segmento = "{SEGMENTO}"\n'
        f'section = ["liquidacion", "prior"]\n'
        f"data_type = {data_type}\n"
        for number, caption, data_type in rows
    ]
    (spec.prior_casillas_dir / f"c{SEGMENTO}+planted.toml").write_text(
        "\n".join(blocks), encoding="utf-8"
    )


class TestPlantedGrowthInsideARun:
    """A record that grows in its middle moves every later positional id."""

    def test_moved_positional_rows_are_refused_not_carried(self, tmp_path: Path) -> None:
        spec = spec_for(tmp_path)
        # The prior edition authored two unnumbered slots at their old spans.
        write_prior(spec, [
            (f"{SEGMENTO.lower()}.16-32", "Tramo base imponible 1", '"money"'),
            (f"{SEGMENTO.lower()}.33-37", "Tramo de tipo de gravamen 1", '"ratio"'),
        ])
        # The new design widens the first slot by one byte, so the second moves.
        grown = sheet_of([
            field(16, 18, "Tramo base imponible 1"),
            field(34, 5, "Tramo de tipo de gravamen 1", type_code="Num"),
        ])
        with pytest.raises(GenerationRefused) as refusal:
            emit_records(spec, {SEGMENTO: grown})
        # Both slots moved, so neither may carry the prior edition's attributes.
        assert f"{SEGMENTO.lower()}.16-33" in str(refusal.value)
        assert f"{SEGMENTO.lower()}.34-38" in str(refusal.value)

    def test_a_stale_id_is_never_reused_for_a_moved_slot(self, tmp_path: Path) -> None:
        spec = spec_for(tmp_path, adjudicate=True)
        write_prior(spec, [(f"{SEGMENTO.lower()}.33-37", "Tipo de gravamen", '"ratio"')])
        grown = sheet_of([
            field(16, 18, "Tramo base imponible 1"),
            field(34, 5, "Tipo de gravamen", type_code="Num"),
        ])
        report = emit_records(spec, {SEGMENTO: grown})
        body = report.outcomes[0].body
        # The id IS the position range, so the prior span must not survive.
        assert f'{SEGMENTO.lower()}.33-37' not in body
        assert f'{SEGMENTO.lower()}.34-38' in body


class TestPlantedContinuationLine:
    """A caption's line break must not escape its TOML comment."""

    def test_a_newline_in_a_caption_folds_to_one_space(self, tmp_path: Path) -> None:
        spec = spec_for(tmp_path, adjudicate=True)
        wrapped = sheet_of([
            field(16, 17, "Suma del 50% de las bases imponibles negativas\nde buques y empresas navieras [01264]")
        ])
        report = emit_records(spec, {SEGMENTO: wrapped})
        body = report.outcomes[0].body
        comment = next(line for line in body.splitlines() if line.startswith("# @16"))
        assert "negativas de buques" in comment
        # every non-blank line is a comment or a key, i.e. it is still TOML
        for line in body.splitlines():
            if line.strip():
                assert line.startswith("#") or "=" in line or line.startswith("[")

    def test_a_box_number_on_the_continuation_is_still_found(self, tmp_path: Path) -> None:
        spec = spec_for(tmp_path, adjudicate=True)
        wrapped = sheet_of([field(16, 17, "Regimen especial\nde buques (Pag. 7A) [01264]")])
        report = emit_records(spec, {SEGMENTO: wrapped})
        assert f'number = "01264"' in report.outcomes[0].body


class TestPlantedPipeInACaption:
    """A caption containing a pipe survives the workbook path intact."""

    def test_a_pipe_does_not_split_the_caption_or_hide_the_number(self, tmp_path: Path) -> None:
        spec = spec_for(tmp_path, adjudicate=True)
        piped = sheet_of([
            field(16, 17, "Discriminante (*)[A|E|I|0] del grupo [00562]", type_code="Num")
        ])
        report = emit_records(spec, {SEGMENTO: piped})
        body = report.outcomes[0].body
        assert "(*)[A|E|I|0]" in body
        assert 'number = "00562"' in body


class TestPlantedWhitespaceFidelity:
    """AEAT's own runs of spaces are part of what it printed."""

    def test_a_double_space_inside_a_caption_survives(self, tmp_path: Path) -> None:
        spec = spec_for(tmp_path, adjudicate=True)
        spaced = sheet_of([field(16, 17, "Conversion de activos en  credito exigible [02802]")])
        report = emit_records(spec, {SEGMENTO: spaced})
        assert "en  credito" in report.outcomes[0].body


class TestPlantedTilingBreak:
    """A gap or overlap between slots is a refusal, not a warning."""

    def test_a_gap_is_refused(self) -> None:
        gapped = RecordDesignSheet(
            name=SEGMENTO,
            fields=(field(1, 15, "Inicio del identificador"), field(20, 17, "Importe [00562]")),
            total_positions=36,
        )
        assert any("tiling breaks at @20" in problem for problem in audit_sheet(gapped))

    def test_a_total_the_rows_do_not_reach_is_refused(self) -> None:
        short = RecordDesignSheet(
            name=SEGMENTO,
            fields=(field(1, 15, "Inicio del identificador"), field(16, 17, "Importe [00562]")),
            total_positions=999,
        )
        assert any("declares 999" in problem for problem in audit_sheet(short))

    def test_an_exact_tiling_passes(self) -> None:
        assert audit_sheet(sheet_of([field(16, 17, "Importe [00562]")])) == []


class TestPlantedAmbiguity:
    """Two box tokens in one description means the number rule has broken."""

    def test_two_numbers_in_one_description_are_refused(self) -> None:
        ambiguous = sheet_of([field(16, 17, "Importe [00562] y tambien [00563]")])
        assert any("more than one box token" in problem for problem in audit_sheet(ambiguous))

    def test_an_unknown_type_code_is_refused(self) -> None:
        odd = sheet_of([field(16, 17, "Importe [00562]", type_code="Z")])
        assert any("unknown type_code" in problem for problem in audit_sheet(odd))


class TestNumberDerivation:
    """Box numbers are not uniformly five digits and not always trailing."""

    @pytest.mark.parametrize(
        ("description", "expected"),
        [
            ("Cuota integra del grupo [00562]", "00562"),
            ("Caracter de la pagina 1 [020]", "020"),
            ("Deduccion trasladable [0640]", "0640"),
            ("Importe con cero de mas [000304]", "000304"),
            ("Cuota integra del grupo [00562]. {DID_liq_CI}", "00562"),
            ("Patrimonio [elemento cubierto]. [0640]", "0640"),
            ("Importe a devolver. {DID_dev_importe} [D]", "D"),
        ],
    )
    def test_the_number_is_found_wherever_aeat_printed_it(
        self, description: str, expected: str
    ) -> None:
        number, _ = derive_number(description, 16, 17, SEGMENTO)
        assert number == expected

    def test_an_unnumbered_slot_takes_its_position_range(self) -> None:
        number, _ = derive_number("Tramo base imponible", 786, 17, SEGMENTO)
        assert number == f"{SEGMENTO.lower()}.786-802"

    def test_a_single_byte_slot_takes_a_bare_position(self) -> None:
        number, _ = derive_number("Cuenta corriente tributaria", 16, 1, SEGMENTO)
        assert number == f"{SEGMENTO.lower()}.16"

    def test_the_number_token_is_stripped_from_the_caption(self) -> None:
        _, caption = derive_number("Cuota integra [00562]", 16, 17, SEGMENTO)
        assert "[00562]" not in caption


class TestCaptionDrift:
    """A meaning rewritten at an address that did not move must surface."""

    def test_a_rewritten_meaning_at_a_held_position_is_reported(self, tmp_path: Path) -> None:
        spec = spec_for(tmp_path)
        write_prior(spec, [("00562", "Tramo base imponible 1", '"money"')])
        rewritten = sheet_of([
            field(16, 17, "Tramo 1 - Base imponible (en grupo de cooperativas) [00562]")
        ])
        report = emit_records(spec, {SEGMENTO: rewritten})
        assert len(report.drift) == 1
        assert "00562" in report.drift[0]

    def test_a_devengo_year_change_is_not_drift(self) -> None:
        assert normalise_for_drift("periodo impositivo 2024") == normalise_for_drift(
            "periodo impositivo 2025"
        )

    def test_a_page_pointer_change_is_not_drift(self) -> None:
        assert normalise_for_drift("Bonificacion (pag. 12)") == normalise_for_drift(
            "Bonificacion (pag. 12 bis)"
        )

    def test_a_rewritten_predicate_is_drift(self) -> None:
        assert normalise_for_drift("rendimientos superiores a 60000") != normalise_for_drift(
            "rendimientos no superiores a 60000"
        )


class TestStructuralRows:
    """Envelope, filler and terminator rows are not casillas."""

    @pytest.mark.parametrize(
        "description",
        [
            "Inicio del identificador de modelo y página.",
            "Fin de registro.",
            "RESERVADO PARA LA ADMINISTRACIÓN",
            "Reservado para la Administración. Rellenar con blancos",
            "Constante",
        ],
    )
    def test_structural_rows_are_recognised(self, description: str) -> None:
        assert is_structural(description)

    @pytest.mark.parametrize(
        "description",
        [
            "Cuota íntegra del grupo [00562]",
            "Tramo 1 - Base imponible",
            "Líquido a ingresar o a devolver. Estado [00621]",
        ],
    )
    def test_a_real_casilla_is_not_structural(self, description: str) -> None:
        assert not is_structural(description)


class TestEmissionIntegrity:
    """What is written is read back and checked, not assumed."""

    def test_every_emitted_row_carries_the_waves_revision_and_refs(
        self, tmp_path: Path
    ) -> None:
        spec = spec_for(tmp_path, adjudicate=True)
        report = emit_records(
            spec, {SEGMENTO: sheet_of([field(16, 17, "Importe [00562]")])}, write=True
        )
        written = (spec.out_dir / report.outcomes[0].filename).read_text(encoding="utf-8")
        assert f'[[revisions."{REVISION}".casillas]]' in written
        assert LEGAL_REFS in written
        assert "continuidad_id" not in written

    def test_a_record_with_no_prior_and_no_rule_refuses(self, tmp_path: Path) -> None:
        spec = spec_for(tmp_path)
        with pytest.raises(GenerationRefused, match="need adjudication"):
            emit_records(spec, {SEGMENTO: sheet_of([field(16, 17, "Importe [00562]")])})

    def test_a_missing_sheet_refuses(self, tmp_path: Path) -> None:
        with pytest.raises(GenerationRefused, match="no such sheet"):
            emit_records(spec_for(tmp_path), {})


class TestDriftComparisonIsSymmetric:
    """Both bugs below shipped, and both were invisible on the design that shipped them.

    The generator's first wave ran on a design whose Contenido column is almost
    always empty and whose type codes are one or two letters. On a design where
    every row carries Contenido and the types are Spanish words, the same code
    reported drift on every single row.
    """

    def test_a_row_whose_contenido_the_prior_never_recorded_is_not_drift(
        self, tmp_path: Path
    ) -> None:
        spec = spec_for(tmp_path)
        # Earlier editions of this corpus wrote the caption only, never the
        # Contenido cell. Comparing a rendered line against such a prior made
        # every content-bearing row read as a meaning change.
        write_prior(spec, [("00562", "Tramo base imponible 1", '"money"')])
        sheet = sheet_of([
            field(16, 17, "Tramo base imponible 1 [00562]", content="Nota 1")
        ])
        report = emit_records(spec, {SEGMENTO: sheet})
        assert report.drift == []
        assert report.content_drift == []

    def test_a_contenido_change_under_a_stable_caption_is_reported(
        self, tmp_path: Path
    ) -> None:
        spec = spec_for(tmp_path)
        prior = spec.prior_casillas_dir / f"c{SEGMENTO}+planted.toml"
        prior.write_text(
            "# @16+1 Numérico. EXTINCION DEL PLAN | 1: rescate  2: otras circunstancias\n"
            f'[[revisions."2024".casillas]]\n'
            f'id = "{SEGMENTO}:00137"\n'
            f'number = "00137"\n'
            f'segmento = "{SEGMENTO}"\n'
            'section = ["liquidacion", "prior"]\n'
            'data_type = "text"\n',
            encoding="utf-8",
        )
        sheet = sheet_of([
            field(
                16,
                1,
                "EXTINCION DEL PLAN [00137]",
                type_code="Numérico",
                content="1: rescate  2: otras circunstancias  3: fallecimiento del tomador",
            )
        ])
        report = emit_records(spec, {SEGMENTO: sheet})
        assert report.drift == [], "the caption held, so this is not caption drift"
        assert len(report.content_drift) == 1
        assert "fallecimiento" in report.content_drift[0]

    def test_a_spanish_type_code_does_not_leak_into_the_fold(self) -> None:
        # An enumeration listing only the short codes matched "num" inside
        # "Numérico" and left "érico" behind, where it compared as content.
        assert normalise_for_drift("# @1+1 Numérico. TIPO DE REGISTRO") == (
            normalise_for_drift("# @1+1 Alfanumérico. TIPO DE REGISTRO")
        )
        assert "rico" not in normalise_for_drift("# @1+1 Numérico. ABC")

    def test_both_authored_comment_prefixes_strip(self) -> None:
        # This corpus writes the type into some comments and not others, even
        # within one modelo's own edition.
        with_type = normalise_for_drift("# @16+1 An. Cuenta corriente tributaria")
        without_type = normalise_for_drift("# @16+17. Cuenta corriente tributaria")
        assert with_type == without_type
        assert not any(character.isdigit() for character in with_type)


class TestIdsAreCarriedNotMinted:
    """Some modelos name casillas with slugs no design states."""

    def test_a_carried_row_keeps_the_prior_id_and_omits_an_absent_segmento(
        self, tmp_path: Path
    ) -> None:
        spec = spec_for(tmp_path)
        prior = spec.prior_casillas_dir / f"c{SEGMENTO}+planted.toml"
        prior.write_text(
            "# @16+1 An. Residencia\n"
            f'[[revisions."2024".casillas]]\n'
            'id = "pf.identificacion-residencia-indicador"\n'
            'number = "00562"\n'
            'section = ["declaracion", "persona_fisica"]\n'
            'data_type = "text"\n',
            encoding="utf-8",
        )
        report = emit_records(
            spec, {SEGMENTO: sheet_of([field(16, 1, "Residencia [00562]", type_code="An")])}
        )
        body = report.outcomes[0].body
        assert 'id = "pf.identificacion-residencia-indicador"' in body
        assert f'id = "{SEGMENTO}:00562"' not in body, "a slug id must never be rebuilt"
        assert "segmento = " not in body, "a modelo without segmento must not gain one"

    def test_the_carried_scheme_refuses_to_mint_an_id_for_an_unmatched_row(
        self, tmp_path: Path
    ) -> None:
        from dataclasses import replace

        spec = replace(spec_for(tmp_path, adjudicate=True), id_scheme="carried")
        with pytest.raises(GenerationRefused, match="need adjudication"):
            emit_records(
                spec, {SEGMENTO: sheet_of([field(16, 17, "Importe [00562]")])}
            )


class TestAnUnrecognisedBoxTokenIsRefused:
    """A real box number must never fall through to a fabricated position range."""

    @pytest.mark.parametrize(
        "token",
        ["A1", "B26", "C71", "716.a", "4774bis", "300,301,302", "65"],
    )
    def test_a_modelo_036_number_form_is_refused_not_silently_positional(
        self, token: str
    ) -> None:
        sheet = sheet_of([field(16, 17, f"Identificacion NIF [{token}]", type_code="An")])
        problems = audit_sheet(sheet)
        assert any(f"[{token}]" in problem for problem in problems), (
            "an unrecognised token must refuse, not become a position range"
        )

    def test_bracketed_prose_is_not_mistaken_for_a_box_token(self) -> None:
        sheet = sheet_of([
            field(16, 17, "Patrimonio neto [elemento cubierto]. [00640]", type_code="N")
        ])
        assert audit_sheet(sheet) == []

    def test_a_recognised_number_still_passes(self) -> None:
        assert audit_sheet(sheet_of([field(16, 17, "Importe [00562]")])) == []
