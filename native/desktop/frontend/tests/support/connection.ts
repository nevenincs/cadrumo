import { label } from "./strings";

/** The words for how a lane is reached, from what the catalogue serves of it:
 * a lane that needs no key is a server on this computer, whatever its
 * transport. */
export const connectionLabel = (served: {
  transport: string;
  auth_kind?: string;
}): string =>
  label(
    served.auth_kind === "none"
      ? "desktop.providers.connection_local"
      : served.transport === "api"
        ? "desktop.providers.connection_api"
        : "desktop.providers.connection_app",
  );
