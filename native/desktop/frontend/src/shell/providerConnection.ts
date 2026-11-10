import type {
  ProviderAuthKind,
  ProviderTransport,
} from "@/components/settings/types";
import type { Translate } from "./strings";

/** How a way is reached, in words, wherever a way is named. A way that takes
 * no key is a server on this computer, whatever its transport, and is not
 * called a key connection. */
export function connectionWords(
  t: Translate,
  way: { transport: ProviderTransport; authKind: ProviderAuthKind },
): string {
  if (way.authKind === "none") return t("desktop.providers.connection_local");
  return way.transport === "api"
    ? t("desktop.providers.connection_api")
    : t("desktop.providers.connection_app");
}
