// The @fixtures alias, bound to one build's window projections.
//
// The window projections are build output of the selected CMake build tree,
// the `window_fixtures` directory of its build-path manifest, which the
// desktop-window-fixtures target seeds. A tsconfig.json cannot compute that
// directory, so its own @fixtures entries are only an editor's candidates and
// the compiler would take the first that exists, whichever preset it belongs
// to. Every tool a build runs binds the alias here instead: the type check in
// memory, and Playwright through a project file written into the build tree.
//
// The seeder records every window family's outputs and their sha256 in an
// index beside them, and removes it when a family is not fresh. The alias is
// bound only to a directory whose files are that recorded set, so a missing,
// partial or edited seed is refused with its remedy rather than reported as
// missing modules.
import { createHash } from "node:crypto";
import {
  lstatSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { createRequire } from "node:module";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { buildPath } from "../../scripts/build-paths.mjs";

const frontend = fileURLToPath(new URL("..", import.meta.url));
const ALIAS = "@fixtures/*";
/** The seeder's record of the window projections, in their directory. */
export const WINDOW_INDEX = ".window-projections.json";
const WINDOW_INDEX_FORMAT = "cadrumo-window-projections-v1";
const SEED =
  "build this preset's desktop-window-fixtures target (`just fixtures-seed` seeds the host preset's)";

/** The TypeScript compiler the frontend's lockfile pins. */
export function compiler() {
  return createRequire(resolve(frontend, "package.json"))("typescript");
}

function refused(fixtures, reason, cause) {
  return new Error(
    `The window projections in ${fixtures} are not the seeded set: ${reason}. To produce them, ${SEED}.`,
    cause ? { cause } : undefined,
  );
}

function recordedIndex(fixtures) {
  let text;
  try {
    text = readFileSync(resolve(fixtures, WINDOW_INDEX), "utf8");
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    throw refused(fixtures, `no ${WINDOW_INDEX} records them`, error);
  }
  let index;
  try {
    index = JSON.parse(text);
  } catch (error) {
    throw refused(fixtures, `${WINDOW_INDEX} is not JSON`, error);
  }
  if (
    !index ||
    index.format !== WINDOW_INDEX_FORMAT ||
    !index.families ||
    typeof index.families !== "object" ||
    !Object.keys(index.families).length
  )
    throw refused(fixtures, `${WINDOW_INDEX} is of another format`);
  return index.families;
}

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

/**
 * Refuse unless `fixtures` is a directory holding exactly the outputs its
 * index records, byte for byte.
 */
export function requireProjections(fixtures) {
  let stat;
  try {
    stat = lstatSync(fixtures);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    throw new Error(
      `The window projections the type check imports are missing: ${fixtures}. To produce them, ${SEED}.`,
      { cause: error },
    );
  }
  if (stat.isSymbolicLink() || !stat.isDirectory())
    throw new Error(
      `The window projections are linked or not a directory: ${fixtures}`,
    );
  const problems = [];
  for (const [family, outputs] of Object.entries(recordedIndex(fixtures))) {
    if (!outputs || typeof outputs !== "object" || !Object.keys(outputs).length)
      problems.push(`${family} records no output`);
    for (const [name, digest] of Object.entries(outputs ?? {})) {
      const path = resolve(fixtures, ...String(name).split("/"));
      const member = relative(fixtures, path);
      if (!member || member.startsWith(`..${sep}`) || isAbsolute(member)) {
        problems.push(`${family} records ${name}, outside the projections`);
        continue;
      }
      let actual;
      try {
        actual = sha256(path);
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
        problems.push(`${name} is missing`);
        continue;
      }
      if (actual !== digest) problems.push(`${name} differs from its seed`);
    }
  }
  if (problems.length)
    throw refused(
      fixtures,
      problems.slice(0, 5).join("; ") +
        (problems.length > 5 ? ` and ${problems.length - 5} more` : ""),
    );
}

/** Diagnostics as the compiler prints them. */
export function formatDiagnostics(ts, diagnostics) {
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
  fixtures = buildPath("window_fixtures"),
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
  if (parsed.errors.length)
    throw new Error(formatDiagnostics(ts, parsed.errors));
  const target = resolve(fixtures, "*").replaceAll("\\", "/");
  parsed.options.paths = { ...parsed.options.paths, [ALIAS]: [target] };
  return parsed;
}

/**
 * Write a project file that extends `project` with every path alias spelled
 * absolutely and @fixtures bound to `fixtures`, and return its path. The file
 * is rewritten only when its text changes, so concurrent readers see a whole
 * file.
 */
export function writeAliasProject(
  destination,
  {
    project = resolve(frontend, "tsconfig.json"),
    fixtures = buildPath("window_fixtures"),
    ts = compiler(),
  } = {},
) {
  const parsed = parseProject({ project, fixtures, ts });
  const base = parsed.options.pathsBasePath ?? dirname(project);
  const paths = Object.fromEntries(
    Object.entries(parsed.options.paths ?? {}).map(([alias, targets]) => [
      alias,
      targets.map((target) => resolve(base, target).replaceAll("\\", "/")),
    ]),
  );
  const text = `${JSON.stringify(
    {
      extends: resolve(project).replaceAll("\\", "/"),
      compilerOptions: { paths },
    },
    null,
    2,
  )}\n`;
  let current;
  try {
    current = readFileSync(destination, "utf8");
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  if (current !== text) {
    mkdirSync(dirname(destination), { recursive: true });
    const staged = `${destination}.${process.pid}.partial`;
    writeFileSync(staged, text);
    renameSync(staged, destination);
  }
  return destination;
}
