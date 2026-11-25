import type { ComponentProps, Dispatch, SetStateAction } from "react";
import { Toast } from "@/components/ui/toast";
import type { AboutState } from "../shell/about";
import type { Action } from "../shell/actions";
import { orientDockPane, swapDockPane } from "../shell/docking";
import type { Host } from "../shell/host";
import {
  DEFAULT_LAYOUT,
  DEFAULT_PREFS,
  type Layout,
  type Maximized,
  type Prefs,
} from "../shell/layout";
import type { NavigatorPrompt } from "../shell/navigation/useNavigator";
import type { SignInController } from "../shell/signIn";
import type { Translate } from "../shell/strings";
import type { useDocsNavigation } from "../shell/useDocsNavigation";
import type { useWindowOverlays } from "../shell/useWindowOverlays";
import { AboutDialog } from "./AboutDialog";
import { CommandPalette } from "./CommandPalette";
import { ContextMenu, type MenuAction, type MenuEntry } from "./ContextMenu";
import type { LanguageControl } from "./LanguageSelect";
import { NavigationPrompt } from "./NavigationPrompt";
import { ReconnectingNotice } from "./ReconnectingNotice";
import { Settings } from "./Settings";
import { ProvisioningPanel } from "./setup/ProvisioningPanel";

const isAction = (item: MenuEntry): item is MenuAction => "id" in item;

type Docs = ReturnType<typeof useDocsNavigation>;

/** What the window lays over the workspace: the settings, About, the
 * palette, a context menu, the toast, the reconnection notice, the
 * navigation's question and the setup panel. */
export function WindowOverlays({
  host,
  t,
  locale,
  account,
  signedIn,
  reader,
  overlays,
  prefs,
  setPrefs,
  setLayout,
  setMaximized,
  languageControl,
  about,
  actions,
  pastedLink,
  searchDocs,
  openDoc,
  searchDeclarations,
  openDeclarationHit,
  focusRail,
  copy,
  say,
  toast,
  askSignIn,
  prompt,
  setupOffered,
}: {
  host: Host;
  t: Translate;
  locale: string;
  account: SignInController;
  signedIn: boolean;
  reader: string | null;
  overlays: ReturnType<typeof useWindowOverlays>;
  prefs: Prefs;
  setPrefs: Dispatch<SetStateAction<Prefs>>;
  setLayout: Dispatch<SetStateAction<Layout>>;
  setMaximized: (update: SetStateAction<Maximized>) => void;
  languageControl: LanguageControl;
  about: AboutState | null;
  actions: Action[];
  pastedLink: ComponentProps<typeof CommandPalette>["pastedLink"];
  searchDocs: Docs["searchDocs"];
  openDoc: Docs["openDoc"];
  searchDeclarations: ComponentProps<
    typeof CommandPalette
  >["searchDeclarations"];
  openDeclarationHit: ComponentProps<
    typeof CommandPalette
  >["openDeclarationHit"];
  focusRail: () => void;
  copy: (text: string) => void;
  say: (text: string) => void;
  toast: string | null;
  askSignIn: () => void;
  prompt: NavigatorPrompt | null;
  setupOffered: boolean;
}) {
  const {
    settingsOpen,
    setSettingsOpen,
    aboutOpen,
    setAboutOpen,
    paletteOpen,
    setPaletteOpen,
    paletteExtra,
    menu,
    setMenu,
  } = overlays;
  const agentSession = host.agentSession;
  return (
    <>
      {settingsOpen && (
        <Settings
          prefs={prefs}
          setPrefs={(next) => {
            setPrefs(next);
            // The dock is the arrangement the window draws; a preference
            // that differs from it is carried into the dock as the
            // arrangement actions do.
            if (next.orientation !== prefs.orientation)
              setLayout((current) =>
                current.docking
                  ? {
                      ...current,
                      docking: orientDockPane(current.docking, "docs"),
                    }
                  : current,
              );
            if (next.order !== prefs.order)
              setLayout((current) =>
                current.docking
                  ? {
                      ...current,
                      docking: swapDockPane(current.docking, "docs"),
                    }
                  : current,
              );
          }}
          language={languageControl}
          close={() => setSettingsOpen(false)}
          about={
            about
              ? {
                  state: about,
                  onOpen: () => {
                    setSettingsOpen(false);
                    setAboutOpen(true);
                  },
                }
              : undefined
          }
          onReset={() => {
            setPrefs(DEFAULT_PREFS);
            setLayout((current) => ({
              ...DEFAULT_LAYOUT,
              logLevel: current.logLevel,
              calendarView: current.calendarView,
              profileView: current.profileView,
              ledgerView: current.ledgerView,
            }));
            setMaximized(null);
            say(t("desktop.settings.layout_reset"));
          }}
        />
      )}
      <AboutDialog
        open={aboutOpen && about !== null}
        onOpenChange={setAboutOpen}
        state={about}
        onCopy={copy}
      />
      {paletteOpen && (
        <CommandPalette
          actions={[...paletteExtra, ...actions]}
          pastedLink={pastedLink}
          language={languageControl}
          searchDocs={searchDocs}
          openDoc={openDoc}
          searchDeclarations={searchDeclarations}
          openDeclarationHit={openDeclarationHit}
          close={() => setPaletteOpen(false)}
          fallbackFocus={focusRail}
        />
      )}
      {menu && (
        <ContextMenu
          // Each menu is its own: it remembers where its own focus came
          // from.
          key={`${menu.at.x}:${menu.at.y}`}
          label={t("desktop.palette.actions")}
          items={menu.items}
          at={menu.at}
          choose={(id) => {
            const items = menu.items;
            setMenu(null);
            items
              .find(
                (item): item is MenuAction => isAction(item) && item.id === id,
              )
              ?.run?.();
          }}
        />
      )}
      <Toast>{toast}</Toast>
      <ReconnectingNotice
        reconnecting={account.reconnecting}
        onSignIn={askSignIn}
      />
      {prompt && <NavigationPrompt prompt={prompt} />}
      {setupOffered && (
        <ProvisioningPanel
          locale={locale}
          onCopyDetails={copy}
          signedOut={!signedIn}
          localAi={
            signedIn && agentSession && host.providerSettings
              ? {
                  session: agentSession,
                  providerSettings: host.providerSettings,
                  reader,
                }
              : null
          }
        />
      )}
    </>
  );
}
