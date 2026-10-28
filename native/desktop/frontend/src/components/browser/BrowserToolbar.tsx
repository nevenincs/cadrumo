import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Spinner } from "@/components/ui/spinner";
import type { SedeViewVerb } from "../../ipc/contract";
import { useStrings } from "../../shell/strings";
import type { PageAddress } from "./browserModel";

/**
 * The browser's controls, in the pane's header: back, forward, reload, the
 * AEAT start page, the page's origin and path, and the person's way to open
 * the page in their own browser. The address is shown, never typed: the window
 * names no address, and the query of a page is not shown. A page that is not
 * served over https, or whose origin is not known, shows that instead of an
 * address, and has none to open.
 */
export function BrowserToolbar({
  page,
  usable,
  external,
  onNavigate,
  onExternal,
}: {
  page: PageAddress | null;
  /** Whether the view takes the person's commands. */
  usable: boolean;
  /** Whether the host holds an address to open. */
  external: boolean;
  onNavigate: (verb: SedeViewVerb) => void;
  onExternal: () => void;
}) {
  const t = useStrings();
  const stated = page?.security === "secure";
  return (
    <div
      role="group"
      className="flex min-w-0 flex-1 items-center gap-0.5"
      data-browser-toolbar=""
    >
      <IconButton
        label={t("desktop.browser.back")}
        disabled={!usable || !page?.canGoBack}
        onClick={() => onNavigate("back")}
      >
        <Icon name="back" />
      </IconButton>
      <IconButton
        label={t("desktop.browser.forward")}
        disabled={!usable || !page?.canGoForward}
        onClick={() => onNavigate("forward")}
      >
        <Icon name="forward" />
      </IconButton>
      <IconButton
        label={t("desktop.browser.reload")}
        disabled={!usable}
        onClick={() => onNavigate("reload")}
      >
        <Icon name="sync" />
      </IconButton>
      <IconButton
        label={t("desktop.browser.home")}
        disabled={!usable}
        onClick={() => onNavigate("home")}
      >
        <Icon name="home" />
      </IconButton>
      <div
        role="group"
        aria-label={t("desktop.browser.address")}
        title={stated ? `${page.origin ?? ""}${page.path ?? ""}` : undefined}
        className="mx-1 flex h-control-xs min-w-0 flex-1 items-center gap-1.5 rounded-md bg-accent px-2 text-sm"
        data-browser-address=""
        data-browser-security={page?.security}
      >
        {page && !stated ? (
          <span className="flex min-w-0 items-center gap-1.5 text-warning">
            <Icon name={page.security === "insecure" ? "alert" : "unknown"} />
            <span className="min-w-0 truncate">
              {page.security === "insecure"
                ? t("desktop.browser.page_insecure")
                : t("desktop.browser.page_unknown")}
            </span>
          </span>
        ) : (
          <span className="min-w-0 truncate">
            <span className="text-muted-foreground">{page?.origin}</span>
            <span className="text-foreground">{page?.path}</span>
          </span>
        )}
        {page?.loading && <Spinner className="ml-auto" />}
      </div>
      <IconButton
        label={t("desktop.browser.external")}
        disabled={!external || !page?.external}
        onClick={onExternal}
      >
        <Icon name="external" />
      </IconButton>
    </div>
  );
}
