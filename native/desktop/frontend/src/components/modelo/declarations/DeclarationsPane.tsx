import type { ReactNode, RefObject } from "react";
import { PaneHeader, type PaneControl } from "../../PaneHeader";
import type { LeaveGuard } from "../../ledger/editing/LedgerEditing";
import type { OpenableSurface } from "../details/Details";
import { WorkspaceScreen } from "../workspace/WorkspaceScreen";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract";
import { DeclarationsPage, type DeclarationsMemory } from "./DeclarationsPage";

/**
 * The first pane while it shows declarations: the list, or the one
 * declaration the shell holds open, under the pane's own header. What either
 * reads lives in its memory only and goes with the profile.
 */
export function DeclarationsPane({
  port,
  reader,
  workUnitId,
  onOpen,
  onCensus,
  onBack,
  onOpenSurface,
  canOpenSurface,
  openLink,
  guardLeave,
  memory,
  withheld,
  language,
  locale,
  shown,
  page,
  pane,
}: {
  port: ModeloPort;
  /** Whose declarations, or null while the account withholds them. */
  reader: string | null;
  /** The declaration open, or null for the list. */
  workUnitId: string | null;
  onOpen(workUnitId: string): void;
  /** Asks for the window's one census flow, where it has one. */
  onCensus?: () => void;
  /** Back to the list; the shell asks first where edits are staged. */
  onBack(): void;
  onOpenSurface(surface: OpenableSurface): void;
  /** Whether the window has a page for the area; only those are linked. */
  canOpenSurface(surface: OpenableSurface): boolean;
  openLink(url: string): void;
  /** Hands the shell the guard that asks before staged edits are dropped. */
  guardLeave(guard: LeaveGuard | null): void;
  /** What the list keeps of itself while a declaration is open, for one
   * profile. */
  memory: RefObject<DeclarationsMemory>;
  withheld: ReactNode;
  language: OutputLanguage;
  locale: string;
  shown: boolean;
  page: RefObject<HTMLElement | null>;
  pane: {
    title: string;
    controls: PaneControl[];
    onToggleMaximize(): void;
  };
}) {
  if (workUnitId === null || reader === null)
    return (
      <DeclarationsPage
        port={port}
        reader={reader}
        withheld={withheld}
        language={language}
        shown={shown}
        page={page}
        pane={pane}
        memory={memory}
        onOpen={onOpen}
        onCensus={onCensus}
      />
    );
  return (
    <>
      <PaneHeader
        title={pane.title}
        controls={pane.controls}
        onToggleMaximize={pane.onToggleMaximize}
      />
      <section
        ref={page}
        tabIndex={-1}
        aria-label={pane.title}
        className="declarations-workspace flex min-h-0 flex-1 flex-col overflow-hidden bg-background focus-visible:-outline-offset-2"
      >
        <WorkspaceScreen
          key={workUnitId}
          port={port}
          workUnitId={workUnitId}
          language={language}
          locale={locale}
          onBack={onBack}
          onOpenSurface={onOpenSurface}
          canOpenSurface={canOpenSurface}
          openLink={openLink}
          onLeaveGuard={guardLeave}
          // The list is read again on return only after a write.
          onWritten={() => {
            memory.current.stale = true;
          }}
        />
      </section>
    </>
  );
}
