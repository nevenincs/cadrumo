import {
  existsSync,
  lstatSync,
  readFileSync,
  realpathSync,
} from "node:fs";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const repository = realpathSync(resolve(desktop, "../.."));
const cacheSetting = /^(CMAKE_HOME_DIRECTORY|CMAKE_CACHEFILE_DIR):[^=]*=(.*)$/;
const admitted = new Map();

function pathKey(path) {
  const normalized = resolve(path);
  return process.platform === "win32" ? normalized.toLowerCase() : normalized;
}

function samePath(left, right) {
  return pathKey(left) === pathKey(right);
}

function linkedMember(path, root) {
  const relativePath = relative(root, path);
  if (
    !relativePath ||
    relativePath === ".." ||
    relativePath.startsWith(`..${sep}`) ||
    isAbsolute(relativePath)
  )
    throw new Error(`CMake output path is outside its binary directory: ${path}`);

  let current = root;
  for (const part of relativePath.split(sep)) {
    current = resolve(current, part);
    try {
      if (lstatSync(current).isSymbolicLink())
        throw new Error(`Linked CMake output path: ${current}`);
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
  }
}

function enrolledPresets(sourceRoot) {
  const projects = [
    { file: resolve(sourceRoot, "CMakePresets.json"), source: sourceRoot },
    {
      file: resolve(sourceRoot, "native/desktop/CMakePresets.json"),
      source: resolve(sourceRoot, "native/desktop"),
    },
  ];
  const presets = new Map();
  for (const project of projects) {
    linkedMember(project.file, sourceRoot);
    const document = JSON.parse(readFileSync(project.file, "utf8"));
    if (!Array.isArray(document.configurePresets))
      throw new Error(`CMake presets have no configure preset list: ${project.file}`);
    let visibleCount = 0;
    for (const preset of document.configurePresets) {
      if (!preset || typeof preset !== "object" || preset.hidden === true) continue;
      const name = preset.name;
      if (
        typeof name !== "string" ||
        !name ||
        name.startsWith(".") ||
        name === ".." ||
        name.includes("/") ||
        name.includes("\\") ||
        name.includes(":")
      )
        throw new Error(`CMake configure preset has an invalid name: ${String(name)}`);
      visibleCount += 1;
      const owner = realpathSync(project.source);
      const previous = presets.get(name);
      if (previous && !samePath(previous, owner))
        throw new Error(`CMake configure preset name is ambiguous: ${name}`);
      presets.set(name, owner);
    }
    if (!visibleCount)
      throw new Error(`CMake presets have no visible configure presets: ${project.file}`);
  }
  return presets;
}

function requireFile(path, description) {
  let stat;
  try {
    stat = lstatSync(path);
  } catch (error) {
    if (error.code === "ENOENT")
      throw new Error(`${description} is missing: ${path}`);
    throw error;
  }
  if (stat.isSymbolicLink() || !stat.isFile())
    throw new Error(`${description} is linked or not a file: ${path}`);
}

function configuredSources(build, expectedSource) {
  const manifestPath = resolve(build, "build-paths.json");
  const cachePath = resolve(build, "CMakeCache.txt");
  requireFile(manifestPath, "CMake build-path manifest");
  requireFile(cachePath, "CMake cache");

  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  if (
    typeof manifest.source !== "string" ||
    !manifest.paths ||
    typeof manifest.paths !== "object" ||
    Array.isArray(manifest.paths)
  )
    throw new Error(`CMake build-path manifest is incomplete: ${manifestPath}`);
  if (!samePath(realpathSync(manifest.source), expectedSource))
    throw new Error(`CMake build-path manifest belongs to another source tree: ${manifestPath}`);

  const settings = new Map();
  for (const line of readFileSync(cachePath, "utf8").split(/\r?\n/)) {
    const match = cacheSetting.exec(line);
    if (match) settings.set(match[1], match[2]);
  }
  const cacheSource = settings.get("CMAKE_HOME_DIRECTORY");
  const cacheBuild = settings.get("CMAKE_CACHEFILE_DIR");
  if (!cacheSource || !cacheBuild)
    throw new Error(`CMake cache has no source or binary directory: ${cachePath}`);
  if (!samePath(realpathSync(cacheSource), expectedSource))
    throw new Error(`CMake cache belongs to another source tree: ${cachePath}`);
  if (!samePath(realpathSync(cacheBuild), build))
    throw new Error(`CMake cache belongs to another binary directory: ${cachePath}`);
  return manifest.paths;
}

function declaredPaths(build, manifestPaths) {
  const paths = {};
  for (const [name, member] of Object.entries(manifestPaths)) {
    if (
      typeof member !== "string" ||
      !member ||
      member.startsWith("/") ||
      member.includes("\\") ||
      member.includes(":") ||
      member.split("/").some((part) => !part || part === "." || part === "..")
    )
      throw new Error(`Invalid CMake output directory: ${String(member)}`);
    const target = resolve(build, ...member.split("/"));
    linkedMember(target, build);
    paths[name] = target;
  }
  return paths;
}

/** Read and verify the full declared output map for an already configured desktop build. */
export function readBuildPaths(binaryDir, repositoryRoot) {
  if (typeof binaryDir !== "string" || !isAbsolute(binaryDir))
    throw new Error("Select an absolute CMake build directory.");
  if (binaryDir.split(/[\\/]/).includes(".."))
    throw new Error("Desktop build directory must not contain traversal components.");
  if (typeof repositoryRoot !== "string" || !isAbsolute(repositoryRoot))
    throw new Error("The repository root must be absolute.");

  const source = realpathSync(repositoryRoot);
  const presets = enrolledPresets(source);
  const buildOwner = resolve(source, "build");
  linkedMember(buildOwner, source);
  if (!existsSync(buildOwner) || !lstatSync(buildOwner).isDirectory())
    throw new Error(`Repository build directory is missing: ${buildOwner}`);

  const selected = resolve(binaryDir);
  const relativeBuild = relative(buildOwner, selected);
  if (
    !relativeBuild ||
    relativeBuild.includes(sep) ||
    relativeBuild === ".." ||
    relativeBuild.startsWith(`..${sep}`) ||
    !presets.has(relativeBuild)
  )
    throw new Error(`Desktop build directory is not build/<visible configure preset>: ${selected}`);
  const expectedSource = presets.get(relativeBuild);

  const canonical = resolve(buildOwner, relativeBuild);
  linkedMember(canonical, source);
  if (!existsSync(canonical) || !lstatSync(canonical).isDirectory())
    throw new Error(`Desktop build directory is missing: ${canonical}`);
  if (!samePath(realpathSync(canonical), canonical) || !samePath(selected, canonical))
    throw new Error(`Desktop build directory is not its enrolled physical path: ${selected}`);

  const manifestPaths = configuredSources(canonical, expectedSource);
  return Object.freeze(declaredPaths(canonical, manifestPaths));
}

/** Return one CMake-declared output below an admitted desktop binary directory. */
export function buildPath(name) {
  const binaryDir = process.env.CADRUMO_CMAKE_BINARY_DIR;
  if (!binaryDir || !isAbsolute(binaryDir))
    throw new Error("Select an absolute CMake build directory.");
  const key = pathKey(binaryDir);
  let paths = admitted.get(key);
  if (!paths) {
    paths = readBuildPaths(binaryDir, repository);
    admitted.set(key, paths);
  }
  const target = paths[name];
  if (!target) throw new Error(`Invalid CMake output directory: ${name}`);
  return target;
}
