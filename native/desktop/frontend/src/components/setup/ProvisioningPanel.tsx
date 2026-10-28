import { useEffect, useId, useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import type { SetupRow } from "../../ipc/contract";
import { useLocalAiLanes, type LocalAiSource } from "../../shell/localAiLanes";
import { useProvisioning } from "../../shell/provisioning";
import { useStrings } from "../../shell/strings";
import { LocalAi } from "./LocalAi";
import { ProvisioningRow, RowState } from "./ProvisioningRow";
import { failureWords, itemName, refusalWords } from "./setupWords";

// The one provisioning panel: every element the engine reports, one row
// each, each with its own status said once, its size, its own action, plan
// review, progress and cancel. Elements set up on their own and at the same
// time; closing the panel leaves every setup running. It opens once per
// launch while setup is not complete, from Settings, and from every
// recovery, scrolled to the element the recovery names.

/** The local AI's element: a dropdown holding its program and its model
 * list. Closed, its header says the element's status; open, the program
 * row inside says it instead. */
function LocalAiElement({
  row,
  locale,
  localAi,
}: {
  row: SetupRow;
  locale: string;
  localAi: LocalAiSource | null;
}) {
  const t = useStrings();
  const store = useProvisioning();
  const contentId = useId();
  const run = store.runOf(row.item);
  const live = run !== null && run.stage !== "settled";
  const focused = store.panel.focus === row.item;
  const [expanded, setExpanded] = useState(focused || live);
  // A plan of its own awaiting an answer, or the panel opened on it, opens
  // it again however it was left.
  const reviewing = run?.stage === "review" ? run.operation_id : null;
  const [opener, setOpener] = useState({
    reviewing,
    request: store.panel.request,
  });
  if (
    opener.reviewing !== reviewing ||
    opener.request !== store.panel.request
  ) {
    setOpener({ reviewing, request: store.panel.request });
    if ((reviewing !== null && opener.reviewing !== reviewing) || focused)
      setExpanded(true);
  }
  // A settled setup may have downloaded a model, and a removal took one
  // away: what the catalog says this computer holds is read again.
  const settled = run?.stage === "settled" ? run.operation_id : null;
  const [reads, setReads] = useState({ settled, count: 0 });
  if (reads.settled !== settled) setReads({ settled, count: reads.count + 1 });
  const { lanes, host } = useLocalAiLanes(localAi, expanded, reads.count);
  return (
    <li
      data-setup-element={row.item}
      data-expanded={expanded || undefined}
      className="grid gap-2 rounded-lg bg-accent p-3"
    >
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={contentId}
        className="group/toggle flex min-w-0 items-center gap-1.5 rounded-md text-left font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onClick={() => setExpanded((open) => !open)}
      >
        <Icon
          name="forward"
          className="shrink-0 text-muted-foreground transition-transform group-aria-expanded/toggle:rotate-90"
        />
        <span className="min-w-0 wrap-anywhere">{itemName(t, row.item)}</span>
      </button>
      {!expanded && <RowState row={row} />}
      {expanded && (
        <div id={contentId}>
          <LocalAi
            lanes={lanes}
            host={host}
            locale={locale}
            onRemoved={() =>
              setReads((held) => ({ ...held, count: held.count + 1 }))
            }
          />
        </div>
      )}
    </li>
  );
}

export function ProvisioningPanel({
  locale,
  onCopyDetails,
  localAi = null,
}: {
  locale: string;
  onCopyDetails: (details: string) => void;
  /** Where the local AI's model lists are read from; null where the window
   * offers none. */
  localAi?: LocalAiSource | null;
}) {
  const t = useStrings();
  const store = useProvisioning();
  const { panel, control, snapshot, rows, localAiRow } = store;
  const content = useRef<HTMLDivElement>(null);
  // The element a recovery named is brought into view each time it asks.
  useEffect(() => {
    if (!panel.open || panel.focus === null) return;
    const frame = window.requestAnimationFrame(() =>
      content.current
        ?.querySelector(
          `[data-setup-element="${CSS.escape(panel.focus ?? "")}"], [data-setup-row="${CSS.escape(panel.focus ?? "")}"]`,
        )
        ?.scrollIntoView({ block: "nearest" }),
    );
    return () => window.cancelAnimationFrame(frame);
  }, [panel.open, panel.focus, panel.request]);
  // A check the engine refused under a category of its own, or refused
  // because the person's selection of local models could not be admitted:
  // it reports no row, so its sentence is the only thing to say.
  const check = snapshot?.check?.stage === "failed" ? snapshot.check : null;
  const reading =
    control.read.kind === "loading" ||
    (snapshot !== null &&
      rows.length === 0 &&
      !check?.failure &&
      !check?.refusal);
  return (
    <Dialog open={panel.open} onOpenChange={(open) => !open && store.close()}>
      <DialogContent
        ref={content}
        placement="top"
        closeLabel={t("desktop.setup.close")}
        className="setup-dialog overflow-y-auto"
        onOpenAutoFocus={(event) => {
          if (!panel.takeFocus) {
            event.preventDefault();
            return;
          }
          // Opened on an element, the keyboard starts at its first control.
          if (panel.focus === null) return;
          const target = content.current?.querySelector<HTMLElement>(
            `[data-setup-element="${CSS.escape(panel.focus)}"] button, [data-setup-row="${CSS.escape(panel.focus)}"] button`,
          );
          if (!target) return;
          event.preventDefault();
          target.focus();
        }}
      >
        <DialogHeader>
          <DialogTitle>{t("desktop.setup.title")}</DialogTitle>
          <DialogDescription>{t("desktop.setup.panel_lead")}</DialogDescription>
        </DialogHeader>

        {check?.failure && (
          <Alert role="alert">{failureWords(t, check.failure)}</Alert>
        )}
        {check?.refusal && (
          <Alert role="alert">{refusalWords(t, check.refusal)}</Alert>
        )}

        {reading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner />
            {t("desktop.setup.checking")}
          </p>
        ) : control.read.kind === "failed" ? (
          <Alert role="alert">{refusalWords(t, control.read.code)}</Alert>
        ) : snapshot === null ? (
          <p className="text-sm text-foreground">
            {t("desktop.setup.unavailable")}
          </p>
        ) : (
          <ul className="setup-components grid gap-2">
            {rows.map((row) =>
              row.item === localAiRow?.item ? (
                <LocalAiElement
                  key={row.item}
                  row={row}
                  locale={locale}
                  localAi={localAi}
                />
              ) : (
                <ProvisioningRow key={row.item} row={row} locale={locale} />
              ),
            )}
          </ul>
        )}

        {control.refusal && (
          <Alert role="alert">{refusalWords(t, control.refusal)}</Alert>
        )}

        <DialogFooter>
          {snapshot?.details && (
            <Button
              variant="ghost"
              size="sm"
              className="mr-auto"
              onClick={() => onCopyDetails(snapshot.details)}
            >
              {t("desktop.setup.copy_details")}
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={store.close}>
            {store.incomplete
              ? t("desktop.setup.not_now")
              : t("desktop.setup.close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
