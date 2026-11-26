# Making a change: the development loop

This is the procedure for an ordinary change to the Python backend, sized so that proof stays proportional to the change. It routes to the other development references for detail: [testing lanes and the gate](dev-testing-lanes-and-gate.md), [authority and fixture staleness](dev-authority-and-fixture-staleness.md), [generated artefacts](dev-generated-artefacts.md) and [build loop](dev-build-loop.md).

## Before the first edit

- **Environment.** Recipes run `uv run --no-sync`, so nothing syncs the environment for you. `just setup-check` reports the state without writing. `just setup` converges Python, tooling, `env/.env`, the published authority, the frontend packages and the fixture projections; `just setup-checkout` does Python, tooling and `env/.env` only; `just setup-env` creates `env/.env` and ports values from the main worktree without printing any ([setup](../../../../justfile#L89)).
- **Derived inputs.** If registry data, personas or producers changed since you last ran tests (yours or someone else's landing), publish and seed first: `just registry-publish-authority-if-authority-stale`, then `just fixtures-seed`. `just fixtures-status` shows what is stale without changing anything.
- **Find the owner.** Decide which layer owns the behaviour (the numbered references in the skill index) and read the nearest existing test in that package's `tests/` directory. The test you extend tells you the markers, fixtures and lane you will use.

## The small-change loop

1. **Edit**, in the defining module. Use relative imports inside the package; keep `__init__.py` inert.
2. **Focused test.** Add or extend a test in the narrowest owning `tests/` directory, with module-level markers, and run that file: `uv run --no-sync pytest <file> -n 0`, adding `-m integration` or `-m "integration and serial"` when the file is marked so. Check the summary shows your test ran and was not deselected.
3. **Static checks on what you touched.** `just fix-code PATH` repairs one named Python file (Ruff fix, ty fix, Ruff format; it changes the file and is not a gate). Then verify: `uv run --no-sync ruff check <files>`, `uv run --no-sync ruff format --check <files>` and the type checker on those files.
4. **Regenerate what your change made stale.** Use the trigger table in [generated artefacts](dev-generated-artefacts.md). The common ones: a new, moved or removed non-test module needs `just generate-import-load-targets`; an operation schema change needs `just generate-operation-contract-manifest`; a new user-visible key needs the locale workflow.
5. **Owning lane.** Run the narrowest lane that contains your tests (`just test-cli`, `test-tui`, `test-calculations`, `test-registry`, or the tooling lanes). Lanes take minutes, not seconds; one run after the focused test passes is the efficient order.
6. **Before handing over.** `just check-code` (or `just check-python` when the native toolchain is not configured), `just check-registry-gate`, `just test-gate [MANIFEST]`, then read `just report-code-health`. A failure on code you did not touch is reported, not fixed in passing.

Runs longer than about ten minutes (`check-code`, `test-registry`, `test-product`, the gate, any native build) belong in the background.

## Static checks, in the order the suite runs them

`just check-code` runs `dev.quality.suite --all-languages`; `just check-python` runs the same suite without the native frontend and Rust checks. The Python checks are `check-style`, `check-format`, `check-data-format`, `check-types`, `complexity-gate`, `check-module-size`, `check-year-literals`, `check-surface-redeclaration`, `check-import-boundaries`, `check-dependency-declarations`, `check-module-reachability`, `check-symbol-usage`, `check-export-consumption`, `check-secure-store-write-paths`, `check-persistence-write-paths`, `check-docstring-references` and `check-operation-contract-manifest`. Each is also a recipe of the same name, so run the one that failed alone while fixing it ([suite](../../../../dev/quality/suite.py#L80)).

- **Types.** `just check-types` runs `ty` over `src`, and `pyrefly` and `basedpyright` over the strict domain and application subset, for Linux, Windows and macOS. `--count` prints one integer. A change to a protocol or a widely implemented interface is not proved by checking the touched files alone, because implementations and test fakes elsewhere break: run the whole `just check-types`.
- **Imports.** `just check-import-boundaries` is the one import verdict. It needs a still tree and current load-target metadata. `uv run --no-sync lint-imports --config .importlinter --no-cache` is the quick contract check while iterating. A new package must be classified in `.importlinter`, which keeps a closed classification.
- **Years.** `just check-year-literals` rejects year literals in Python and TypeScript; years come from the registry envelope.
- **Never** add a lint or type suppression, a skip or an expected-failure marker to get past a check.

## Changes that reach further than one module

**A registered operation (new, or a changed request or result shape).** Operations are composed by group in `src/cadrumo/entrypoints/operation_composition.py` and its per-area neighbours. After the change:

- regenerate the contract manifest, `just generate-operation-contract-manifest` (a stale manifest is refused at run time when its group is composed, which shows up downstream as an unavailable operation);
- if a command, or what a command submits, changed, rewrite the recorded command-to-operation table with `python -m dev.operation_contract_manifest.command_operation_derivation --connection-requests`;
- run the tests under `dev/operation_contract_manifest/tests/` (manifest drift, command join, frontend parity, MCP surface policies, exposure census) and the operator-surface reconciliation test under `src/cadrumo/application/operator_surface/tests/`;
- if CLI output changed, regenerate and review the documentation sequence goldens (`just docs-generate-sequences`, then `just docs-sequences-check`);
- if the desktop frontend consumes the shape, seed fixtures and run the frontend checks ([composition](../../../../src/cadrumo/entrypoints/operation_composition.py#L474), [manifest generator](../../../../dev/operation_contract_manifest/generate.py#L1)).

**A user-visible string.** Never edit a catalogue file by hand. `just locales-scaffold` creates the catalogue leaves for keys found in code; `just locales-set LOCALE KEY VALUE` sets one value and `just locales-set-batch MANIFEST` sets many from a JSON object mapping locale code to a map of dotted keys to values. Every supported locale needs a real translation. `just locales-status` reports and `just check-locales` is the audit of keys, values, placeholders and enrolment; the tests are under `dev/locales/tests/`. Documentation catalogues are a separate workflow (`just docs-generate-catalogs`, `just docs-locales-set-batch`) ([locale tool](../../../../dev/locales/cli.py#L281)).

**A new module, package or test directory.** Regenerate the import load targets; classify a new package in `.importlinter`; make sure a new `tests/` directory is inside a lane path and its modules carry markers.

**Registry data.** Follow the registry-authoring skill for authoring, and [authority and fixture staleness](dev-authority-and-fixture-staleness.md) for what to republish. Prove per supported year, enumerating years from the registry envelope.

**A protocol, IPC contract or environment name.** These have generated copies in Rust, C and TypeScript; see [generated artefacts](dev-generated-artefacts.md) and the environment contract reference.

## Seeing the change run

- **CLI and TUI** run from the checkout's environment; set up with `just setup` so the authority exists.
- **Desktop frontend without a native build:** `just dev` publishes the authority when stale, seeds the fixture projections and serves the frontend against simulated host data. It compiles no Rust and shows recorded projections, not your live backend, so a backend change appears there only after the projections are reseeded.
- **Packaged application:** a backend change reaches a built bundle only by rebuilding it; see [build loop](dev-build-loop.md). Check which checkout a running runtime or worker was started from before concluding a change has no effect: a process started earlier, or from another worktree's environment, still runs the old code.

## Efficient habits

- Go narrow to wide: file, lane, change-scoped gate, full gate. Do not start a wide run to find out whether a narrow one would pass.
- Batch the slow proofs: finish the code, then run each long check once.
- Do not run two things that write the same output at once (two authority publishes, two fixture seeds, two native builds, a docs build beside a docs check).
- Keep scratch under the worktree's `.tmp/` and remove it afterwards.
- Product code, tests and tools never invoke the version-control executable; tests keep plain assertions.
