import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import type { SedeViewPort, SedeViewSize } from "../../shell/sedeView";
import {
  useFocusTarget,
  useNavigationGuard,
} from "../../shell/navigation/hooks";
import { useStrings } from "../../shell/strings";
import { PaneHeader, type PaneControl } from "../PaneHeader";
import { publishing, takesInput } from "./browserModel";
import { endText, failureText, publicationText } from "./browserWords";
import { BrowserPrompts } from "./BrowserPrompts";
import { BrowserSurface, type SurfaceHandle } from "./BrowserSurface";
import { BrowserToolbar } from "./BrowserToolbar";
import { PageDialog } from "./PageDialog";
import { useSedeView } from "./useSedeView";

/** The register element the page belongs to, which a navigation names. */
const ELEMENT = "browser";

export type BrowserPageProps = {
  port: SedeViewPort;
  /** What stands in the page while the account withholds the browser: the
   * account's own account of why, and the ways on. No view opens then. */
  withheld?: ReactNode;
  /** The page's own element, for whoever sends focus to it. */
  page?: RefObject<HTMLElement | null>;
  /** False while the page is put aside rather than unloaded: its view goes on
   * and its images are credited, but nothing is drawn. */
  shown?: boolean;
  /** The pane's title and controls, which the page's header carries. */
  pane: {
    title: string;
    controls: PaneControl[];
    onToggleMaximize: () => void;
  };
  /** The shell's own chords, which never reach the page. */
  isShellChord: (event: KeyboardEvent) => boolean;
};

/**
 * The Browser page: the profile worker's own browser, streamed into a canvas.
 * It starts at the AEAT Sede, the person browses it freely, and a login made
 * in it is the profile's login for every command that reads from the AEAT.
 * Nothing it holds is kept: the frames, addresses, titles and typed keys live
 * in memory for as long as the page does. The window keeps the page while
 * it is put aside, so the view goes on; unmounting it closes the view, which
 * publishes its session first.
 */
export function BrowserPage(props: BrowserPageProps) {
  return props.withheld ? <Withheld {...props} /> : <OpenBrowser {...props} />;
}

function Withheld({ withheld, page, shown = true, pane }: BrowserPageProps) {
  return (
    <div className={shown ? "contents" : "hidden"}>
      <PaneHeader
        title={pane.title}
        controls={pane.controls}
        onToggleMaximize={pane.onToggleMaximize}
      />
      <section
        ref={page}
        tabIndex={-1}
        aria-label={pane.title}
        className="flex min-h-0 flex-1 flex-col bg-background focus-visible:-outline-offset-2"
      >
        {withheld}
      </section>
    </div>
  );
}

function OpenBrowser({
  port,
  page,
  shown = true,
  pane,
  isShellChord,
}: BrowserPageProps) {
  const t = useStrings();
  const surface = useRef<SurfaceHandle>(null);
  const [size, setSize] = useState<SedeViewSize | null>(null);
  const measured = useCallback(
    (next: SedeViewSize) =>
      setSize((last) =>
        last &&
        last.cssWidth === next.cssWidth &&
        last.cssHeight === next.cssHeight &&
        last.scale === next.scale
          ? last
          : next,
      ),
    [],
  );
  const view = useSedeView({
    port,
    size,
    draw: (image) => surface.current?.draw(image) ?? Promise.resolve(),
  });
  const { state } = view;
  const busy = publishing(state);
  const live = state.phase === "open";

  useFocusTarget(ELEMENT, () => surface.current?.element() ?? null);
  // Work in flight is not cut off by a navigation: publishing the session
  // holds it, and a dialog the page opened is answered first.
  useNavigationGuard(
    ELEMENT,
    busy ? "busy" : state.dialogs.length > 0 ? "modal" : "clean",
  );

  // What was drawn is a page of taxpayer data: it goes when the view does.
  const finished = state.phase === "ended" || state.phase === "failed";
  useEffect(() => {
    if (finished) surface.current?.clear();
  }, [finished]);

  // A page dialog waits for the person to come back to the page.
  const dialog = shown ? state.dialogs[0] : undefined;
  return (
    <div className={shown ? "contents" : "hidden"}>
      <PaneHeader
        title={pane.title}
        controls={pane.controls}
        onToggleMaximize={pane.onToggleMaximize}
      >
        <BrowserToolbar
          page={state.page}
          usable={takesInput(state)}
          external={state.page !== null && (live || busy)}
          onNavigate={view.navigate}
          onExternal={() => view.openExternal()}
        />
      </PaneHeader>
      <section
        ref={page}
        tabIndex={-1}
        aria-label={pane.title}
        aria-busy={busy || state.phase === "opening" || undefined}
        className="relative flex min-h-0 flex-1 flex-col bg-background focus-visible:-outline-offset-2"
      >
        <BrowserSurface
          ref={surface}
          shown={shown}
          enabled={takesInput(state)}
          label={t("desktop.browser.surface")}
          isShellChord={isShellChord}
          onSize={measured}
          onInput={view.input}
        />
        {live && (
          <BrowserPrompts
            acquiring={state.page?.mode === "acquiring"}
            problem={state.problem}
            downloads={state.downloads}
            choosers={state.choosers}
            notices={state.notices}
            note={state.note}
            onAnswerDownload={view.answerDownload}
            onAnswerChooser={view.answerChooser}
            onOpenExternal={view.openExternal}
            onDismissNotice={view.dismissNotice}
            onDismissNote={view.dismissNote}
            onDismissProblem={view.dismissProblem}
          />
        )}
        {(state.phase === "opening" || state.phase === "waiting") && (
          <EmptyState
            busy
            role="status"
            className="absolute inset-0 bg-background"
            description={
              state.phase === "opening"
                ? t("desktop.browser.opening")
                : t("desktop.browser.waiting")
            }
          />
        )}
        {busy && (
          <EmptyState
            busy
            role="status"
            className="absolute inset-0 bg-background/80"
            description={t("desktop.browser.closing")}
          />
        )}
        {state.phase === "failed" && state.failure && (
          <EmptyState
            role="status"
            icon="unplug"
            className="absolute inset-0 bg-background"
            description={failureText(t, state.failure)}
          >
            <Button size="sm" onClick={view.reopen}>
              {t("desktop.browser.retry")}
            </Button>
          </EmptyState>
        )}
        {state.phase === "ended" && state.end && (
          <EmptyState
            role="status"
            icon="unplug"
            className="absolute inset-0 bg-background"
            heading={endText(t, state.end.reason)}
            description={
              state.end.publication
                ? publicationText(t, state.end.publication)
                : undefined
            }
          >
            <Button size="sm" onClick={view.reopen}>
              {t("desktop.browser.reopen")}
            </Button>
          </EmptyState>
        )}
      </section>
      {dialog && (
        <PageDialog
          key={dialog.dialog_id}
          dialog={dialog}
          onAnswer={(accept, promptText) =>
            view.answerDialog(dialog.dialog_id, accept, promptText)
          }
        />
      )}
    </div>
  );
}
