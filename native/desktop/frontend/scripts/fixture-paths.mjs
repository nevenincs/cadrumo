// Where the generated window projections live: the host's native build tree,
// build/<preset>/fixtures/window, beside the other outputs of that build. The
// preset is the one the repository enrols for the machine running the tooling,
// as dev/fixture_projections/location.py states it for the Python side.
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const HOST_PRESETS = {
  "win32:x64": "windows-x64",
  "linux:x64": "linux-x86-64",
  "linux:arm64": "linux-aarch64",
  "darwin:arm64": "macos-arm64",
};

const repository = fileURLToPath(new URL("../../../../", import.meta.url));

export function hostPreset() {
  const preset = HOST_PRESETS[`${process.platform}:${process.arch}`];
  if (!preset)
    throw new Error(
      `No configure preset is enrolled for ${process.platform} ${process.arch}.`,
    );
  return preset;
}

/** The directory of the generated window projections in the host's build tree. */
export function windowFixtures() {
  return resolve(repository, "build", hostPreset(), "fixtures", "window");
}
