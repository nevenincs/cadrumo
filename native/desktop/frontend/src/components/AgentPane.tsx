import type { ComponentProps } from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { primaryChord, type Action } from "../shell/actions";
import type { Host } from "../shell/host";
import type { useNavigator } from "../shell/navigation/useNavigator";
import type { SignInController } from "../shell/signIn";
import type { Translate } from "../shell/strings";
import type { useWindowSetup } from "../shell/useWindowSetup";
import { AgentColumn } from "./AgentColumn";
import type { OpenMenu } from "./ContextMenu";
import type { PaneControl } from "./PaneHeader";
import { PANE_SURFACE } from "./paneSurface";

type Navigator = ReturnType<typeof useNavigator>;

/** The agent's pane: the conversation, with the column's maximize and close
 * in its bar. */
export function AgentPane({
  host,
  t,
  locale,
  account,
  signedIn,
  shown,
  agentControl,
  body,
  openMenu,
  onToolRefused,
  openLink,
  openViewLink,
  settledSetups,
  maximizeControl,
  byId,
  toggleMaximize,
  close,
}: {
  host: Host;
  t: Translate;
  locale: string;
  account: SignInController;
  signedIn: boolean;
  shown: boolean;
  agentControl: ComponentProps<typeof AgentColumn>["control"];
  body: ComponentProps<typeof AgentColumn>["body"];
  openMenu: OpenMenu;
  onToolRefused: ReturnType<typeof useWindowSetup>["onToolRefused"];
  openLink: (url: string) => void;
  openViewLink: Navigator["openLink"];
  settledSetups: string | null;
  maximizeControl: PaneControl;
  byId: (id: string) => Action | undefined;
  toggleMaximize: () => void;
  close: () => void;
}) {
  return (
    <div className={cn(PANE_SURFACE, "pane-agent")}>
      {/* One bar: the conversation's own actions, then the column's maximize
          and close as every column has them. */}
      <AgentColumn
        control={agentControl}
        agent={host.agent}
        session={host.agentSession}
        providerSettings={host.providerSettings}
        agentAccess={host.agentAccess}
        writeClipboard={(text) => host.writeClipboard(text)}
        // The agent works only for a profile that is signed in here: not
        // for one the shell cannot tell about.
        reader={signedIn ? (account.status?.active_profile ?? null) : null}
        shown={shown}
        locale={locale}
        body={body}
        onToggleMaximize={toggleMaximize}
        onMenu={openMenu}
        onToolRefused={onToolRefused}
        onOpenLink={openLink}
        setupSettled={settledSetups}
        onOpenView={(url, opened) =>
          openViewLink(url, {
            opened: (shown) => opened?.(shown.opened),
          })
        }
        trailing={[
          maximizeControl,
          {
            id: "close",
            icon: "close",
            label: t("desktop.agent.hide"),
            shortcut: primaryChord(byId("agent.toggle")),
            run: close,
          } satisfies PaneControl,
        ].map((control) => (
          <IconButton
            key={control.id}
            label={control.label}
            shortcut={control.shortcut}
            aria-pressed={control.pressed}
            onClick={control.run}
          >
            <Icon name={control.icon} />
          </IconButton>
        ))}
      />
    </div>
  );
}
