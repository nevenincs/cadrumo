"""The printed-box parser must read the five-digit numbering modelo 200 uses."""

from dev.registry.analysis.casilla_lineage_seed import _DESIGN_BOX


def test_reads_a_five_digit_printed_box() -> None:
    assert _DESIGN_BOX.findall("Base imponible [00101] del ejercicio") == ["00101"]


def test_still_reads_shorter_printed_boxes() -> None:
    assert _DESIGN_BOX.findall("[1] [07] [123] [4567]") == ["1", "07", "123", "4567"]


def test_reads_every_box_on_a_line_of_five_digit_numbering() -> None:
    line = "[00101] + [00102] - [03442] = [00955]"
    assert _DESIGN_BOX.findall(line) == ["00101", "00102", "03442", "00955"]


def test_refuses_a_run_longer_than_the_widest_numbering() -> None:
    assert _DESIGN_BOX.findall("[123456]") == []
