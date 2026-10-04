import { readFileSync } from "node:fs";
import { isAbsolute, relative, resolve } from "node:path";
import { buildPath } from "./build-paths.mjs";

export function identity() {
  const value = JSON.parse(
    readFileSync(resolve(buildPath("generated"), "identity.json"), "utf8"),
  );
  for (const key of ["name", "application_id", "version"])
    if (typeof value[key] !== "string" || !value[key].trim())
      throw new Error(`Generated identity is missing ${key}`);
  return value;
}

export function server() {
  const value = JSON.parse(
    readFileSync(
      resolve(buildPath("generated"), "desktop-server.json"),
      "utf8",
    ),
  );
  if (typeof value.host !== "string" || !value.host.trim())
    throw new Error("Missing frontend bind address");
  for (const key of ["devPort", "previewPort"])
    if (!Number.isInteger(value[key]) || value[key] < 1 || value[key] > 65535)
      throw new Error(`Invalid frontend ${key}`);
  return value;
}

export function profile(configuration = process.env.CADRUMO_BUILD_CONFIG) {
  switch (configuration) {
    case "Debug":
      return { directory: "debug", debug: true, environment: {} };
    case "Release":
      return { directory: "release", debug: false, environment: {} };
    case "RelWithDebInfo":
      return {
        directory: "release",
        debug: false,
        environment: {
          CARGO_PROFILE_RELEASE_DEBUG: "2",
          CARGO_PROFILE_RELEASE_STRIP: "none",
        },
      };
    case "MinSizeRel":
      return {
        directory: "release",
        debug: false,
        environment: { CARGO_PROFILE_RELEASE_OPT_LEVEL: "s" },
      };
    default:
      throw new Error(
        "Select a supported CMake configuration through CADRUMO_BUILD_CONFIG",
      );
  }
}

export function artifactFile() {
  profile();
  return resolve(
    buildPath("generated"),
    `desktop-${process.env.CADRUMO_BUILD_CONFIG}.json`,
  );
}

export function executable() {
  const artifact = JSON.parse(readFileSync(artifactFile(), "utf8"));
  const owned = relative(
    resolve(buildPath("desktop_cargo"), profile().directory),
    artifact.executable,
  );
  if (
    !isAbsolute(artifact.executable) ||
    !owned ||
    owned.startsWith("..") ||
    isAbsolute(owned)
  )
    throw new Error(
      "Desktop executable must belong to the selected Cargo profile",
    );
  return artifact.executable;
}

const DOCS_SCHEME = "cadrumo-docs";

// The origin the webview serves the documentation scheme from. The desktop
// host applies the same rule at runtime and refuses a shell policy that does
// not frame exactly this origin.
export function docsOrigin(window, platform = process.platform) {
  if (platform === "win32")
    return `${window.useHttpsScheme ? "https" : "http"}://${DOCS_SCHEME}.localhost`;
  return `${DOCS_SCHEME}://localhost`;
}

// The template frames nothing; the build lets the shell frame the
// documentation origin of the platform it targets.
function shellPolicy(policy, origin) {
  if (typeof policy !== "string")
    throw new Error("The shell policy template must be one policy string.");
  const directives = policy.split(";").map((directive) => directive.trim());
  const frames = directives.filter((directive) =>
    /^frame-src(\s|$)/.test(directive),
  );
  if (frames.length !== 1 || frames[0] !== "frame-src 'none'")
    throw new Error("The shell policy template must frame nothing.");
  return directives
    .map((directive) =>
      directive === frames[0] ? `frame-src ${origin}` : directive,
    )
    .join("; ");
}

export function tauriConfig(
  template,
  product,
  frontend,
  icons,
  platform = process.platform,
) {
  const [main] = template.app.windows;
  return {
    ...template,
    productName: product.name,
    identifier: product.application_id,
    version: product.version,
    build: { ...template.build, frontendDist: frontend },
    app: {
      ...template.app,
      windows: template.app.windows.map((window) => ({
        ...window,
        title: product.name,
      })),
      security: {
        ...template.app.security,
        csp: shellPolicy(template.app.security.csp, docsOrigin(main, platform)),
      },
    },
    bundle: {
      ...template.bundle,
      icon: [resolve(icons, "icon.ico"), resolve(icons, "icon.png")],
    },
  };
}
