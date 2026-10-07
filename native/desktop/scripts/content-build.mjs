// CMake invokes the inexpensive check each time, so additions, removals and
// missing outputs are visible even when source timestamps have not changed.
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  statSync,
  renameSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { dirname, isAbsolute, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { syncBackendSource } from "./backend-snapshot.mjs";

export function writeStable(file, content) {
  const bytes = Buffer.from(content);
  if (existsSync(file) && readFileSync(file).equals(bytes)) return;
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, bytes);
}

function inventory(paths) {
  const entries = [];
  function visit(file) {
    if (!existsSync(file)) {
      entries.push([file, null]);
      return;
    }
    const stat = statSync(file);
    if (stat.isDirectory()) {
      const start = entries.length;
      entries.push([file, "directory"]);
      for (const name of readdirSync(file).sort()) visit(resolve(file, name));
      entries[start][1] = createHash("sha256")
        .update(JSON.stringify(entries.slice(start + 1)))
        .digest("hex");
    } else {
      entries.push([
        file,
        createHash("sha256").update(readFileSync(file)).digest("hex"),
      ]);
    }
  }
  for (const path of [...paths].sort()) visit(resolve(path));
  return entries;
}

export function contentBuild(
  { inputs, outputs, record, identity = {} },
  build,
) {
  const fingerprint = JSON.stringify({
    identity,
    inputs: inventory([
      ...inputs,
      fileURLToPath(import.meta.url),
      fileURLToPath(new URL("backend-snapshot.mjs", import.meta.url)),
    ]),
  });
  const before = inventory(outputs);
  let previous;
  try {
    previous = JSON.parse(readFileSync(record, "utf8"));
  } catch {
    /* First build or invalid record. */
  }
  if (
    previous?.fingerprint === fingerprint &&
    JSON.stringify(previous.outputs) === JSON.stringify(before) &&
    before.every(([, hash]) => hash !== null)
  )
    return false;
  // Preserve original filesystem objects, including sub-microsecond times.
  // Tools may empty/truncate their output trees, so build separately and merge
  // changed bytes into the retained originals before moving them back.
  const roots = [...new Set(outputs.map((output) => resolve(output)))].filter(
    (candidate, _, all) =>
      !all.some((other) => {
        const path = relative(other, candidate);
        return (
          other !== candidate &&
          path &&
          !path.startsWith("..") &&
          !isAbsolute(path)
        );
      }),
  );
  mkdirSync(dirname(record), { recursive: true });
  const workspace = mkdtempSync(resolve(dirname(record), "content-build-"));
  const backups = [];
  try {
    for (const [index, output] of roots.entries()) {
      if (!existsSync(output)) continue;
      const backup = resolve(workspace, String(index));
      renameSync(output, backup);
      backups.push([output, backup]);
    }
    build();
    const after = inventory(outputs);
    if (!after.length || after.some(([, hash]) => hash === null))
      throw new Error("Build did not produce all declared outputs");
    for (const [output, backup] of backups) {
      syncBackendSource(output, backup, workspace);
      rmSync(output, { recursive: true, force: true });
      renameSync(backup, output);
    }
    writeStable(record, JSON.stringify({ fingerprint, outputs: after }));
  } catch (error) {
    rmSync(record, { force: true });
    for (const [output, backup] of backups) {
      if (!existsSync(backup)) continue;
      rmSync(output, { recursive: true, force: true });
      renameSync(backup, output);
    }
    throw error;
  } finally {
    rmSync(workspace, { recursive: true, force: true });
  }
  return true;
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const args = process.argv.slice(2);
  const boundary = args.indexOf("--");
  if (boundary < 0)
    throw new Error("Pass action arguments followed by -- and its command");
  const options = { inputs: [fileURLToPath(import.meta.url)], outputs: [] };
  for (let index = 0; index < boundary; index += 2) {
    const [key, value] = args.slice(index, index + 2);
    if (key === "--input") options.inputs.push(value);
    else if (key === "--inputs-file") {
      const inputs = JSON.parse(readFileSync(value, "utf8"));
      if (
        !Array.isArray(inputs) ||
        inputs.some((input) => typeof input !== "string")
      )
        throw new Error("Input manifest must be an array of paths");
      options.inputs.push(...inputs);
    } else if (key === "--output") options.outputs.push(value);
    else if (key === "--record") options.record = value;
    else throw new Error(`Unknown build option: ${key}`);
  }
  if (!options.record || !options.outputs.length)
    throw new Error("Declare the action record and outputs");
  const command = args.slice(boundary + 1);
  options.identity = { command, node: process.version };
  contentBuild(options, () => {
    const result = spawnSync(command[0], command.slice(1), {
      stdio: "inherit",
      windowsHide: true,
    });
    if (result.error) throw result.error;
    if (result.status !== 0)
      throw new Error(`Build action failed: ${result.status}`);
  });
}
