// The frontend's type check: the TypeScript compiler over tsconfig.json, with
// the @fixtures alias bound to the host preset's own window projections.
//
// A tsconfig.json cannot compute a path, so its @fixtures entries can only list
// candidate build trees, and the compiler takes the first that exists,
// whichever preset it belongs to. The check instead binds the alias to the one
// directory fixture-paths.mjs resolves for this host, the same directory Vite
// serves and the producers write, and refuses to start without it rather than
// reporting every fixture import as a missing module.
import { lstatSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { windowFixtures } from "./fixture-paths.mjs";

const frontend = fileURLToPath(new URL("..", import.meta.url));
const ALIAS = "@fixtures/*";
const SEED =
  "build the desktop-window-fixtures target, or run `just fixtures-seed`";

/** The TypeScript compiler the frontend's lockfile pins. */
export function compiler() {
  return createRequire(resolve(frontend, "package.json"))("typescript");
}

function requireProjections(fixtures) {
  let stat;
  try {
    stat = lstatSync(fixtures);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    throw new Error(
      `The window projections the type check imports are missing: ${fixtures}. To produce them, ${SEED}.`,
    );
  }
  if (stat.isSymbolicLink() || !stat.isDirectory())
    throw new Error(
      `The window projections are linked or not a directory: ${fixtures}`,
    );
}

function format(ts, diagnostics) {
  return ts.formatDiagnosticsWithColorAndContext(diagnostics, {
    getCurrentDirectory: ts.sys.getCurrentDirectory,
    getCanonicalFileName: ts.sys.useCaseSensitiveFileNames
      ? (file) => file
      : (file) => file.toLowerCase(),
    getNewLine: () => ts.sys.newLine,
  });
}

/**
 * Parse a project with its @fixtures alias bound to `fixtures` alone; every
 * other option, path and file is the project's own.
 */
export function parseProject({
  project = resolve(frontend, "tsconfig.json"),
  fixtures = windowFixtures(),
  ts = compiler(),
} = {}) {
  requireProjections(fixtures);
  const parsed = ts.getParsedCommandLineOfConfigFile(
    project,
    {},
    {
      ...ts.sys,
      onUnRecoverableConfigFileDiagnostic: (diagnostic) => {
        throw new Error(
          ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n"),
        );
      },
    },
  );
  if (parsed.errors.length) throw new Error(format(ts, parsed.errors));
  const target = resolve(fixtures, "*").replaceAll("\\", "/");
  parsed.options.paths = { ...parsed.options.paths, [ALIAS]: [target] };
  return parsed;
}

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
      process.stderr.write(format(ts, diagnostics));
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
