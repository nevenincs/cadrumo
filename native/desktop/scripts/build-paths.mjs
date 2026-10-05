import { existsSync, readFileSync, realpathSync } from "node:fs";
import { dirname, isAbsolute, relative, resolve } from "node:path";

export function buildPath(name) {
  const binaryDir = process.env.CADRUMO_CMAKE_BINARY_DIR;
  if (!binaryDir || !isAbsolute(binaryDir))
    throw new Error("Select an absolute CMake build directory.");
  const root = realpathSync(binaryDir);
  const manifest = JSON.parse(
    readFileSync(resolve(root, "build-paths.json"), "utf8"),
  );
  const member = manifest.paths[name];
  if (
    typeof member !== "string" ||
    !member ||
    isAbsolute(member) ||
    member.includes(":") ||
    member.includes("\\") ||
    member.split("/").includes("..")
  )
    throw new Error(`Invalid CMake output directory: ${name}`);
  const target = resolve(root, member);
  for (let current = target; current !== root; current = dirname(current)) {
    const owned = relative(
      root,
      existsSync(current) ? realpathSync(current) : current,
    );
    if (!owned || owned.startsWith("..") || isAbsolute(owned))
      throw new Error(
        `CMake output directory escapes binary directory: ${name}`,
      );
  }
  if (target === root)
    throw new Error(`Invalid CMake output directory: ${name}`);
  return target;
}
