"""Build output names its step, honours CMake's levels, and says what each target builds and where."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from ..build_log import LEVEL_VARIABLE, BuildLog, display_path, selected_level
from ..cached_command import run_cached

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ({}, "STATUS"),
        ({LEVEL_VARIABLE: "debug"}, "DEBUG"),
        ({LEVEL_VARIABLE: " Warning "}, "WARNING"),
        ({"VERBOSE": "1"}, "VERBOSE"),
        ({LEVEL_VARIABLE: "NOTICE", "VERBOSE": "1"}, "VERBOSE"),
        ({LEVEL_VARIABLE: "TRACE", "VERBOSE": "1"}, "TRACE"),
        ({"VERBOSE": ""}, "STATUS"),
    ],
)
def test_level_follows_the_variable_and_verbose_only_raises_it(environment: dict[str, str], expected: str) -> None:
    assert selected_level(environment) == expected


def test_a_level_cmake_does_not_define_is_refused() -> None:
    with pytest.raises(ValueError, match="must be one of ERROR, WARNING"):
        selected_level({LEVEL_VARIABLE: "INFO"})


def test_lines_are_filtered_attributed_and_routed_like_cmake(capsys: pytest.CaptureFixture[str]) -> None:
    log = BuildLog("python_sdk", level="VERBOSE")
    log.debug("hidden detail")
    log.verbose("phase producer: pass in 1.0 s")
    log.status("first line\nsecond line")
    log.notice("log excerpt")
    log.warning("tolerated")
    log.error("refused")

    captured = capsys.readouterr()
    assert captured.out.splitlines() == [
        "[cadrumo:python_sdk] phase producer: pass in 1.0 s",
        "[cadrumo:python_sdk] first line",
        "[cadrumo:python_sdk] second line",
    ]
    assert captured.err.splitlines() == [
        "[cadrumo:python_sdk] log excerpt",
        "[cadrumo:python_sdk] warning: tolerated",
        "[cadrumo:python_sdk] error: refused",
    ]


def test_errors_survive_the_quietest_level(capsys: pytest.CaptureFixture[str]) -> None:
    log = BuildLog("zip", level="ERROR")
    log.warning("tolerated")
    log.status("progress")
    log.error("refused")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "[cadrumo:zip] error: refused\n"


def test_paths_inside_the_checkout_read_as_the_cmake_summary_names_them() -> None:
    assert display_path(REPO_ROOT / "build" / "windows-x64" / "stage") == "build/windows-x64/stage"
    outside = Path(REPO_ROOT.anchor) / "not-the-checkout" / "stage"
    assert display_path(outside) == outside.resolve().as_posix()


def test_cached_step_says_why_it_runs_or_reuses(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "source.txt"
    source.write_text("one", encoding="utf-8")
    output = tmp_path / "out.txt"
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "name": "copy",
                "inputs": [str(source)],
                "outputs": [str(output)],
                "marker": str(tmp_path / "receipt.json"),
            }
        ),
        encoding="utf-8",
    )
    command = [sys.executable, "-c", "import shutil,sys; shutil.copyfile(*sys.argv[1:])", str(source), str(output)]

    def statuses() -> list[str]:
        return [line for line in capsys.readouterr().out.splitlines() if line.startswith("[cadrumo:copy] ")]

    assert run_cached(tmp_path, spec, command)
    first = statuses()
    assert first[0].startswith("[cadrumo:copy] running (no completion receipt) -> ")
    assert first[-1].startswith("[cadrumo:copy] finished in ")
    assert not run_cached(tmp_path, spec, command)
    assert statuses()[0].startswith("[cadrumo:copy] up to date, reusing ")
    source.write_text("two", encoding="utf-8")
    assert run_cached(tmp_path, spec, command)
    assert statuses()[0].startswith("[cadrumo:copy] running (1 of 1 inputs changed, first ")
    output.write_text("damaged", encoding="utf-8")
    assert run_cached(tmp_path, spec, command)
    assert statuses()[0].startswith("[cadrumo:copy] running (outputs differ from the completion receipt) -> ")


def test_configure_summary_and_build_announce_every_described_step(tmp_path: Path) -> None:
    cmake = shutil.which("cmake")
    assert cmake is not None
    source = tmp_path / "source"
    source.mkdir()
    modules = REPO_ROOT / "native/cmake"
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(Summary LANGUAGES NONE)\n"
        f'include("{(modules / "BuildLog.cmake").as_posix()}")\n'
        f'include("{(modules / "Cleanup.cmake").as_posix()}")\n'
        'cadrumo_build_fact("Channel" "preview")\n'
        'cadrumo_build_fact("Images" "first" "second")\n'
        # Each step's completion must name its own target although the loop variable moves on.
        "foreach(name first second)\n"
        "  cadrumo_build_step(comment ${name} GROUP payload\n"
        '    SUMMARY "write ${name}; keep its name" OUTPUTS "${CMAKE_BINARY_DIR}/${name}-$<CONFIG>.txt")\n'
        '  add_custom_target(${name} COMMAND "${CMAKE_COMMAND}" -E touch "${CMAKE_BINARY_DIR}/${name}-$<CONFIG>.txt"\n'
        '    COMMENT "${comment}" VERBATIM)\n'
        "endforeach()\n"
        "add_dependencies(second first)\n"
        'cadrumo_describe_target(second_alias GROUP payload SUMMARY "alias")\n'
        "add_custom_target(second_alias ALL DEPENDS second)\n"
        "add_custom_target(undescribed)\n"
        'cmake_language(DEFER DIRECTORY "${CMAKE_SOURCE_DIR}" CALL cadrumo_print_build_summary)\n',
        encoding="utf-8",
    )
    build = tmp_path / "build"
    configured = run_command(
        [cmake, "-S", str(source), "-B", str(build), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release"],
        cwd=source,
    )
    assert configured.returncode == 0, configured.stdout + configured.stderr
    # Columns are padded for reading; compare words.
    summary = [" ".join(line.removeprefix("-- ").split()) for line in configured.stdout.splitlines()]
    assert "Cadrumo build configuration" in summary
    assert "Channel preview" in summary
    assert "Images first, second" in summary
    assert "Build targets: 3 (* = part of the default build)" in summary
    assert [line for line in summary if "keep its name" in line or line.endswith(" alias")] == [
        "first write first; keep its name",
        "second write second; keep its name",
        "* second_alias alias",
    ]
    assert f"-> {(build / 'first-<config>.txt').as_posix()}" in summary
    assert "Undescribed targets: undescribed" in summary

    built = run_command([cmake, "--build", str(build), "--target", "second"], cwd=source)
    assert built.returncode == 0, built.stdout + built.stderr
    announced = re.findall(r"\[cadrumo:(\w+)\] Release: write \1; keep its name -> \S+", built.stdout)
    completed = re.findall(r"\[cadrumo:(\w+)\] Release: complete", built.stdout)
    assert announced == ["first", "second"]
    assert completed == ["first", "second"]
