// The frontend's type check: the TypeScript compiler over tsconfig.json, with
// the @fixtures alias bound to the selected build's own window projections.
//
// The alias is bound through scripts/fixture-alias.mjs, to the directory the
// build-path manifest names, the same one Vite serves and the seed writes, and
// the check refuses to start unless it holds the seeded set rather than
// reporting every fixture import as a missing module.
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { compiler, formatDiagnostics, parseProject } from "./fixture-alias.mjs";

/** Type check a project as `tsc --noEmit` does and return its diagnostics. */
export function typecheck(options = {}) {
  const ts = options.ts ?? compiler();
  const parsed = parseProject({ ...options, ts });
  const program = ts.createProgram({
    rootNames: parsed.fileNames,
    options: { ...parsed.options, noEmit: true },
    projectReferences: parsed.projectReferences,
    configFileParsingDiagnostics: ts.getConfigFileParsingDiagnostics(parsed),
  });
  return { ts, diagnostics: ts.getPreEmitDiagnostics(program) };
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  try {
    const { ts, diagnostics } = typecheck();
    if (diagnostics.length) {
      process.stderr.write(formatDiagnostics(ts, diagnostics));
      process.stderr.write(
        `${ts.sys.newLine}Found ${diagnostics.length} type check diagnostics.${ts.sys.newLine}`,
      );
      process.exitCode = 1;
    }
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  }
}
