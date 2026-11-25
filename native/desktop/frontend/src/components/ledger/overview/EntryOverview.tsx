import { useId, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon, type IconName } from "@/components/ui/icon";
import { useStrings } from "../../../shell/strings";
import type {
  OverviewGroup,
  OverviewModel,
  OverviewValue,
} from "./overviewModel";

/** The one thing an overview offers: to open the entry where it is
 * changed. */
export type OverviewAction = {
  label: string;
  icon: IconName;
  run: () => void;
};

/** A fact's value, drawn so that not set and not known never look like a
 * stored value or like each other: not set is quiet, not known carries the
 * unknown mark. */
function Value({ value }: { value: OverviewValue }) {
  if (value.kind === "absent")
    return <span className="text-muted-foreground">{value.text}</span>;
  if (value.kind === "unknown")
    return (
      <span className="inline-flex items-start gap-1 text-muted-foreground">
        <Icon name="unknown" size="xs" className="mt-0.5 shrink-0" />
        <span>{value.text}</span>
      </span>
    );
  return (
    <span className="grid">
      <span className={cn(value.figure && "tabular-nums")}>{value.text}</span>
      {value.detail && (
        <span className="text-xs text-muted-foreground">{value.detail}</span>
      )}
    </span>
  );
}

function Group({ group }: { group: OverviewGroup }) {
  const heading = useId();
  return (
    <section
      aria-labelledby={heading}
      data-group={group.id}
      className="ledger-overview-group grid gap-1.5 border-t border-border pt-3"
    >
      <h3
        id={heading}
        className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
      >
        {group.heading}
      </h3>
      {group.facts.length > 0 && (
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
          {group.facts.map((fact) => (
            <div
              key={fact.id}
              data-fact={fact.id}
              data-state={fact.value.kind}
              className="col-span-2 grid grid-cols-subgrid"
            >
              <dt className="text-muted-foreground">{fact.label}</dt>
              <dd className="min-w-0 break-words">
                <Value value={fact.value} />
              </dd>
            </div>
          ))}
        </dl>
      )}
      {group.notes && group.notes.length > 0 && (
        <ul className="grid gap-1 text-sm">
          {group.notes.map((note, at) => (
            <li
              key={at}
              data-note={note.tone}
              className="flex items-start gap-1.5 break-words"
            >
              {note.tone === "warning" && (
                <Icon
                  name="alert"
                  size="xs"
                  className="mt-0.5 shrink-0 text-warning"
                />
              )}
              <span className="min-w-0">{note.text}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * The overview of one ledger entry: a movement, an invoice or a document,
 * in a window over the page that only reads. Its heading names the entry and
 * its amount, chips say its state, and groups of facts follow, each stored,
 * not set or not known. One action opens the entry where it is changed.
 *
 * `onClosed` hands the focus back as the overview closes, told whether the
 * action was taken, which may want the focus for itself.
 */
export function EntryOverview({
  model,
  action,
  onClose,
  onClosed,
}: {
  model: OverviewModel;
  action: OverviewAction | null;
  onClose: () => void;
  onClosed?: (acted: boolean) => void;
}) {
  const t = useStrings();
  const content = useRef<HTMLDivElement>(null);
  const acted = useRef(false);
  const chipsLabel = useId();
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        ref={content}
        placement="top"
        className="ledger-overview w-dialog-md gap-3"
        data-entry-kind={model.kind}
        closeLabel={t("desktop.ledger.overview.close")}
        // The summary is read, not filled in: it takes the focus itself, so
        // Enter does not run the action before anything was read.
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          content.current?.focus();
        }}
        onCloseAutoFocus={(event) => {
          if (!onClosed) return;
          event.preventDefault();
          onClosed(acted.current);
        }}
      >
        <DialogHeader>
          <p className="ledger-overview-kind text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {model.kindLabel}
          </p>
          <DialogTitle className="ledger-overview-title break-words">
            {model.title}
          </DialogTitle>
          <DialogDescription className="ledger-overview-subtitle break-words">
            {model.subtitle}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
          {model.amount && (
            <div className="ledger-overview-amount grid min-w-0">
              <span className="text-lg font-medium break-words tabular-nums">
                {model.amount.text}
              </span>
              {model.amount.detail && (
                <span className="text-sm text-muted-foreground">
                  {model.amount.detail}
                </span>
              )}
              {model.amount.converted && (
                <span
                  className="ledger-overview-converted text-sm"
                  data-state={model.amount.converted.value.kind}
                >
                  <span className="text-muted-foreground">
                    {model.amount.converted.label}
                  </span>{" "}
                  <Value value={model.amount.converted.value} />
                </span>
              )}
            </div>
          )}
          {model.chips.length > 0 && (
            <>
              <span id={chipsLabel} className="sr-only">
                {t("desktop.ledger.overview.state")}
              </span>
              <ul
                aria-labelledby={chipsLabel}
                className="ledger-overview-chips flex flex-wrap gap-1"
              >
                {model.chips.map((chip) => (
                  <li key={chip.id} data-chip={chip.id}>
                    <Badge variant={chip.tone}>
                      {chip.icon && <Icon name={chip.icon} size="xs" />}
                      {chip.text}
                    </Badge>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
        {model.notice && (
          <p className="ledger-overview-notice flex items-center gap-1.5 text-sm">
            <span
              aria-hidden="true"
              className="h-4 border-l-2 border-dashed border-foreground"
            />
            {model.notice}
          </p>
        )}
        {model.groups.map((group) => (
          <Group key={group.id} group={group} />
        ))}
        <DialogFooter sticky className="justify-between">
          <p className="text-xs text-muted-foreground">
            {t("desktop.ledger.overview.read_only")}
          </p>
          {action && (
            <Button
              size="sm"
              className="ledger-overview-action"
              onClick={() => {
                acted.current = true;
                action.run();
                onClose();
              }}
            >
              <Icon name={action.icon} />
              {action.label}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
