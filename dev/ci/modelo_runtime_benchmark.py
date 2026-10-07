"""Replay one real native Modelo sequence and retain payload-free cost evidence.

Run ``uv run python -m dev.ci.modelo_runtime_benchmark --output PATH`` with an
empty output directory. The default journey is the enrolled Modelo 100 local
export. ``--profile-first-decode`` adds a bounded first-decode CPU profile;
leave it off for before/after timings. The sandbox and native owner retain all
normal validation, currentness, guard, custody and cleanup behavior.

Boundary timings are inclusive; nested decode/load totals must not be added.
Process CPU includes concurrent threads; thread CPU isolates synchronous work.
The final whole-tree CPU uses the shared ``perf_measurement`` owner, including
native workers and password KDF children. Wall time is diagnostic, never a new
performance gate. JSONL starts are flushed so an interrupted run retains its
last admitted boundary; frequent schema calls are aggregated in memory.
Aggregate records are cumulative snapshots: use the last or maximum count per
process, never sum snapshots. Catalogue and Modelo completions publish them
before a native owner can contain its worker without composition teardown.
"""

from __future__ import annotations

import argparse
import cProfile
import functools
import json
import os
import sys
import threading
import time
from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from types import CodeType
from typing import Literal

import pytest
from pydantic import BaseModel

from dev._paths import REPO_ROOT, UTF_8

from .perf_measurement import process_tree_cpu

_DECODE_MODELS = frozenset(
    {"Envelope[CalculationRevisionCatalogue]", "RegistrySnapshot", "CalculationRenderingSnapshot"}
)
_AGGREGATE_FLUSH_BOUNDARIES = frozenset(
    {"operations.build_registry", "catalogue.load", "catalogue.load_revisioned", "modelo.calculate", "modelo.export"}
)


@dataclass
class _Total:
    calls: int = 0
    wall_seconds: float = 0.0
    cpu_seconds: float = 0.0
    thread_cpu_seconds: float = 0.0


class RuntimeBenchmarkRecorder:
    """Retain only timing, counts and code identities from one benchmark process."""

    def __init__(self, output: Path, *, role: Literal["parent", "worker"], profile_first_decode: bool = False) -> None:
        """Bind one process-local recorder to the benchmark's owned output tree."""
        self.path = output / f"{role}-{os.getpid()}.jsonl"
        self.lock = threading.RLock()
        self.counts: dict[str, int] = {}
        self.totals: dict[str, _Total] = {}
        self.profile_first_decode = profile_first_decode
        self._profiled = False

    def _write(self, record: dict[str, object]) -> None:
        with self.lock, self.path.open("a", encoding=UTF_8) as target:
            target.write(json.dumps(record, allow_nan=False) + "\n")

    @contextmanager
    def measure(self, boundary: str, *, payload_bytes: int | None = None, aggregate: bool = False) -> Generator[None]:
        """Time unchanged work, retaining the exception type without its message."""
        with self.lock:
            call = self.counts.get(boundary, 0) + 1
            self.counts[boundary] = call
        if not aggregate:
            self._write({"event": "start", "boundary": boundary, "call": call, "payload_bytes": payload_bytes})
        wall, cpu, thread = time.perf_counter(), time.process_time(), time.thread_time()
        outcome = "ok"
        try:
            yield
        except BaseException as error:
            outcome = type(error).__name__
            raise
        finally:
            sample = _Total(1, time.perf_counter() - wall, time.process_time() - cpu, time.thread_time() - thread)
            self._finish(boundary, call, outcome, sample, aggregate=aggregate)

    def _finish(self, boundary: str, call: int, outcome: str, sample: _Total, *, aggregate: bool) -> None:
        if aggregate:
            with self.lock:
                total = self.totals.setdefault(boundary, _Total())
                total.calls += 1
                total.wall_seconds += sample.wall_seconds
                total.cpu_seconds += sample.cpu_seconds
                total.thread_cpu_seconds += sample.thread_cpu_seconds
        else:
            self._write({"event": "finish", "boundary": boundary, "call": call, "outcome": outcome, **asdict(sample)})
            if boundary in _AGGREGATE_FLUSH_BOUNDARIES:
                self.flush()

    def wrap[**P, R](self, original: Callable[P, R], boundary: str) -> Callable[P, R]:
        """Observe a real callable, forwarding its exact arguments and return value."""

        @functools.wraps(original)
        def measured(*args: P.args, **kwargs: P.kwargs) -> R:
            with self.measure(boundary, aggregate=boundary == "operations.strict_schema"):
                return original(*args, **kwargs)

        return measured

    def flush(self) -> None:
        """Publish monotonic cumulative totals at coarse boundaries and scope exit."""
        with self.lock:
            totals = {boundary: asdict(total) for boundary, total in self.totals.items()}
            self._write({"event": "aggregate", "semantics": "cumulative", "boundaries": totals})

    def claim_decode_profile(self, model_name: str) -> bool:
        """Reserve one profile without changing which catalogue decode executes."""
        with self.lock:
            selected = (
                self.profile_first_decode
                and not self._profiled
                and model_name == "Envelope[CalculationRevisionCatalogue]"
            )
            if selected:
                self._profiled = True
            return selected

    def retain_profile(self, profile: cProfile.Profile) -> None:
        """Retain bounded CPU-function statistics without paths, locals or inputs."""
        rows = [
            _profile_row(
                entry.code,
                calls=entry.callcount,
                primitive_calls=entry.callcount - entry.reccallcount,
                self_cpu_seconds=entry.inlinetime,
                cumulative_cpu_seconds=entry.totaltime,
            )
            for entry in profile.getstats()
        ]
        # Keep both rankings: nested async scopes can overlap cumulative cost.
        by_self = sorted(rows, key=lambda row: row["self_cpu_seconds"], reverse=True)[:30]
        by_total = sorted(rows, key=lambda row: row["cumulative_cpu_seconds"], reverse=True)[:30]
        self._write({"event": "decode_profile", "timer": "thread_time", "by_self": by_self, "by_cumulative": by_total})

    def record_tree(self, *, wall_seconds: float, own_cpu_seconds: float, child_cpu_seconds: float) -> None:
        """Record the shared process-tree measurement after owned children close."""
        self._write(
            {
                "event": "process_tree",
                "wall_seconds": wall_seconds,
                "own_cpu_seconds": own_cpu_seconds,
                "child_cpu_seconds": child_cpu_seconds,
                "cpu_seconds": own_cpu_seconds + child_cpu_seconds,
            }
        )


def _profile_row(
    code: CodeType | str,
    *,
    calls: int,
    primitive_calls: int,
    self_cpu_seconds: float,
    cumulative_cpu_seconds: float,
) -> dict[str, str | int | float]:
    if isinstance(code, CodeType):
        source = Path(code.co_filename)
        try:
            module = source.relative_to(REPO_ROOT).with_suffix("").as_posix().replace("/", ".")
        except ValueError:
            module = source.name
        line, function = code.co_firstlineno, code.co_name
    else:
        module, line, function = "builtins", 0, code
    return {
        "module": module,
        "line": line,
        "function": function,
        "primitive_calls": primitive_calls,
        "calls": calls,
        "self_cpu_seconds": self_cpu_seconds,
        "cumulative_cpu_seconds": cumulative_cpu_seconds,
    }


def _patch_function_aliases[**P, R](
    patch: pytest.MonkeyPatch, original: Callable[P, R], replacement: Callable[P, R]
) -> None:
    """Observe existing direct-import consumers as well as the defining module."""
    for name, module in tuple(sys.modules.items()):
        if name.startswith("cadrumo."):
            for attribute, value in tuple(vars(module).items()):
                if value is original:
                    patch.setattr(module, attribute, replacement)


def _observe_functions(patch: pytest.MonkeyPatch, recorder: RuntimeBenchmarkRecorder) -> None:
    from cadrumo.application.modelo.calculation_actions import (
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    )
    from cadrumo.application.modelo.export import export_modelo_revision
    from cadrumo.application.operations.registry_schema_validation import strict_model_json_schema
    from cadrumo.entrypoints.operation_composition import build_production_operation_registry

    _patch_function_aliases(
        patch, strict_model_json_schema, recorder.wrap(strict_model_json_schema, "operations.strict_schema")
    )
    _patch_function_aliases(
        patch,
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
        recorder.wrap(calculate_modelo_revision_from_bucket_aggregation_with_diagnostics, "modelo.calculate"),
    )
    _patch_function_aliases(patch, export_modelo_revision, recorder.wrap(export_modelo_revision, "modelo.export"))
    _patch_function_aliases(
        patch,
        build_production_operation_registry,
        recorder.wrap(build_production_operation_registry, "operations.build_registry"),
    )


@contextmanager
def observe_runtime_boundaries(recorder: RuntimeBenchmarkRecorder) -> Generator[None]:
    """Instrument actual owners only inside the composed developer fixture."""
    from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

    original_validate = BaseModel.model_validate_json.__func__

    def validate(
        cls: type[BaseModel],
        json_data: str | bytes | bytearray,
        *,
        strict: bool | None = None,
        extra: Literal["allow", "ignore", "forbid"] | None = None,
        context: object = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> BaseModel:
        if cls.__name__ not in _DECODE_MODELS:
            return original_validate(
                cls, json_data, strict=strict, extra=extra, context=context, by_alias=by_alias, by_name=by_name
            )
        size = len(json_data.encode(UTF_8)) if isinstance(json_data, str) else len(json_data)
        selected = recorder.claim_decode_profile(cls.__name__)
        profile = cProfile.Profile(timer=time.thread_time) if selected else None
        with recorder.measure("decode." + cls.__name__, payload_bytes=size):
            if profile is not None:
                profile.enable()
            try:
                return original_validate(
                    cls, json_data, strict=strict, extra=extra, context=context, by_alias=by_alias, by_name=by_name
                )
            finally:
                if profile is not None:
                    profile.disable()
                    recorder.retain_profile(profile)

    with pytest.MonkeyPatch.context() as patch:
        for method in ("load", "load_revisioned"):
            original = getattr(CalculationRevisionCatalogueRepository, method)
            patch.setattr(
                CalculationRevisionCatalogueRepository, method, recorder.wrap(original, "catalogue." + method)
            )
        patch.setattr(
            PinnedAuthorityOperation, "snapshot", recorder.wrap(PinnedAuthorityOperation.snapshot, "authority.snapshot")
        )
        _observe_functions(patch, recorder)
        patch.setattr(BaseModel, "model_validate_json", classmethod(validate))
        try:
            yield
        finally:
            recorder.flush()


def copy_instrumented_worker(output: Path, *, profile_first_decode: bool = False) -> Path:
    """Copy today's fixture, validating the generated bootstrap before publication."""
    from dev.docs.sequences import runtime_fixture

    source = Path(runtime_fixture.__file__).read_text(encoding=UTF_8)
    source = source.replace("str(Path(__file__).resolve().parents[3])", repr(str(REPO_ROOT)))
    original = "    raise SystemExit(run(composition_factory=_worker_composition))"
    if source.count(original) != 1:
        raise ValueError("runtime fixture main entrypoint changed; update the benchmark copy owner")
    bootstrap = (
        "    from dev.ci.modelo_runtime_benchmark import RuntimeBenchmarkRecorder, observe_runtime_boundaries\n"
        "    @contextmanager\n"
        "    def _benchmark_composition():\n"
        f"        _recorder = RuntimeBenchmarkRecorder(Path({str(output)!r}), role='worker',\n"
        f"            profile_first_decode={profile_first_decode!r})\n"
        "        with _worker_composition(), observe_runtime_boundaries(_recorder):\n"
        "            yield\n"
        "    raise SystemExit(run(composition_factory=_benchmark_composition))"
    )
    destination = output / "runtime_fixture.py"
    copied = source.replace(original, bootstrap)
    compile(copied, str(destination), "exec")
    destination.write_text(copied, encoding=UTF_8)
    return destination


@contextmanager
def record_runtime_tree(recorder: RuntimeBenchmarkRecorder) -> Generator[None]:
    """Retain the canonical final tree measurement after success or failure."""
    with ExitStack() as completed, process_tree_cpu() as tree:

        def retain_completed() -> None:
            recorder.record_tree(
                wall_seconds=tree.wall_seconds,
                own_cpu_seconds=tree.own_cpu_seconds,
                child_cpu_seconds=tree.child_cpu_seconds,
            )

        completed.callback(retain_completed)
        yield


def benchmark_sequence(output: Path, *, page: str, sequence_id: str, profile_first_decode: bool = False) -> None:
    """Execute one discovered real sequence; an occupied destination is refused."""
    from dev.docs.build import ensure_isolated_storage_root

    ensure_isolated_storage_root()
    from cadrumo.core.config import load_settings, override_settings
    from cadrumo.tests.env_scope import derived_storage_settings
    from dev.docs.sequences.checks import discover_sequences
    from dev.docs.sequences.runner import execute_sequence, observe_sequence_frames
    from dev.docs.sequences.runtime_fixture import sequence_worker_script

    discovered, problems = discover_sequences(page=page, sequence_id=sequence_id)
    if problems or len(discovered) != 1:
        raise ValueError("benchmark requires exactly one discovered enrolled sequence")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    authority_root = load_settings().cadrumo_authority_root
    recorder = RuntimeBenchmarkRecorder(output, role="parent")
    worker = copy_instrumented_worker(output, profile_first_decode=profile_first_decode)

    def frame(index: int) -> Generator[None]:
        with recorder.measure(f"sequence.frame.{index}"):
            yield

    with (
        derived_storage_settings(output / "storage-base"),
        override_settings(cadrumo_authority_root=authority_root),
        sequence_worker_script(worker),
        observe_sequence_frames(contextmanager(frame)),
        observe_runtime_boundaries(recorder),
        record_runtime_tree(recorder),
    ):
        try:
            with recorder.measure("sequence.total"):
                execute_sequence(discovered[0].sequence, sandbox_root=output / "sandbox")
        finally:
            recorder.flush()


def main(argv: list[str] | None = None) -> int:
    """Run the diagnostic without exposing a failed frame's payload or arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page", default="how-to/modelo-100")
    parser.add_argument("--sequence-id", default="modelo-100-export-file")
    parser.add_argument("--profile-first-decode", action="store_true")
    options = parser.parse_args(argv)
    try:
        benchmark_sequence(
            options.output,
            page=options.page,
            sequence_id=options.sequence_id,
            profile_first_decode=options.profile_first_decode,
        )
    except Exception as error:
        print(
            f"Benchmark failed: {type(error).__name__}; safe metrics retained in the output directory", file=sys.stderr
        )
        return 1
    print("Benchmark completed; safe metrics retained in the output directory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
