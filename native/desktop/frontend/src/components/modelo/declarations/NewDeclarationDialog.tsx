import { useMemo, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import { ledgerFailure } from "../../../shell/ledger";
import { MODELO_ACTOR, type ModeloPort } from "../../../shell/modelo";
import type {
  ModeloDeclarationCreationTargetV1 as Target,
  ModeloDeclarationListRowV1,
  PublicPeriod,
} from "../../../shell/modeloContract";
import { useStrings } from "../../../shell/strings";
import { failureText } from "./declarationsWords";

/** Where the dialog starts: a modelo, and a period within it. */
export type NewDeclarationStart = {
  modelo: string;
  period: PublicPeriod | null;
};

type Attempt =
  | { kind: "idle" }
  | { kind: "creating" }
  | { kind: "refused"; code: string }
  | { kind: "failed"; code: string }
  /** The write may have happened: nothing is sent again until the list is
   * read again. */
  | { kind: "unknown" };

const at = (target: Target, period: PublicPeriod | null) =>
  period !== null &&
  target.filing_year === period.filing_year &&
  target.period_code === period.code;

/**
 * Choose a modelo, then a period, from the declarations the read model says
 * can be made. A period that already has a declaration opens it instead of
 * making another; the period due next is chosen first.
 */
export function NewDeclarationDialog({
  open,
  onOpenChange,
  port,
  targets,
  rows,
  start = null,
  onOpen,
  onWritten,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  port: ModeloPort;
  targets: readonly Target[];
  rows: readonly ModeloDeclarationListRowV1[];
  start?: NewDeclarationStart | null;
  onOpen: (workUnitId: string) => void;
  /** A write was sent: the list is read again, whatever came back. */
  onWritten: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open && (
        <Chooser
          port={port}
          targets={targets}
          rows={rows}
          start={start}
          onOpen={onOpen}
          onWritten={onWritten}
          onClose={() => onOpenChange(false)}
        />
      )}
    </Dialog>
  );
}

function Chooser({
  port,
  targets,
  rows,
  start,
  onOpen,
  onWritten,
  onClose,
}: {
  port: ModeloPort;
  targets: readonly Target[];
  rows: readonly ModeloDeclarationListRowV1[];
  start: NewDeclarationStart | null;
  onOpen: (workUnitId: string) => void;
  onWritten: () => void;
  onClose: () => void;
}) {
  const t = useStrings();
  const [modelo, setModelo] = useState<string | null>(start?.modelo ?? null);
  const [query, setQuery] = useState("");
  const [chosen, setChosen] = useState<PublicPeriod | null>(
    start?.period ?? null,
  );
  const [year, setYear] = useState<number | null>(
    start?.period?.filing_year ?? null,
  );
  const [attempt, setAttempt] = useState<Attempt>({ kind: "idle" });

  // The modelos offered, in the order the read model offers them.
  const modelos = useMemo(() => {
    const seen = new Map<string, { title: string; expected: boolean }>();
    for (const target of targets) {
      const held = seen.get(target.modelo);
      seen.set(target.modelo, {
        title: held?.title ?? target.modelo_title,
        expected: (held?.expected ?? false) || target.expected,
      });
    }
    return [...seen].map(([code, held]) => ({ code, ...held }));
  }, [targets]);
  const forModelo = targets.filter((x) => x.modelo === modelo);
  const years = [...new Set(forModelo.map((x) => x.filing_year))];
  const suggested = forModelo.find((x) => x.suggested) ?? forModelo[0] ?? null;
  const shownYear = year ?? suggested?.filing_year ?? null;
  const periods = forModelo.filter((x) => x.filing_year === shownYear);
  const picked =
    periods.find((x) => at(x, chosen)) ??
    periods.find((x) => x.suggested) ??
    periods[0] ??
    null;
  // One declaration a year asks which year; several ask which period.
  const yearly = years.every(
    (y) => forModelo.filter((x) => x.filing_year === y).length === 1,
  );

  const openCount = (code: string) =>
    rows.filter(
      (row) =>
        row.modelo === code &&
        row.work_unit_id !== null &&
        row.group !== "recorded",
    ).length;

  const create = async (target: Target) => {
    setAttempt({ kind: "creating" });
    try {
      const outcome = await port.submit("modelo.work.create", {
        modelo: target.modelo,
        period: { filing_year: target.filing_year, code: target.period_code },
        actor: MODELO_ACTOR,
      });
      onWritten();
      if (outcome.kind === "settled") {
        const result = outcome.result.outcome;
        if (result.kind === "success") {
          onOpen(result.unit.work_unit_id);
          onClose();
        } else setAttempt({ kind: "refused", code: result.reason });
      } else if (outcome.kind === "refused")
        setAttempt({ kind: "refused", code: outcome.reason ?? "refused" });
      // Paused or still running: its settlement was not seen.
      else setAttempt({ kind: "unknown" });
    } catch (error: unknown) {
      const failure = ledgerFailure(error);
      if (failure.code === "unknown") {
        onWritten();
        setAttempt({ kind: "unknown" });
      } else
        // A refusal settled without writing; any other failure never sent.
        setAttempt({
          kind: failure.code === "refused" ? "refused" : "failed",
          code: failureText(failure),
        });
    }
  };

  const q = query.trim().toLowerCase();
  const found = modelos.filter(
    (m) => !q || m.code.includes(q) || m.title.toLowerCase().includes(q),
  );
  const tile = (m: (typeof modelos)[number]) => {
    const count = openCount(m.code);
    return (
      <li key={m.code}>
        <button
          type="button"
          onClick={() => {
            setModelo(m.code);
            setChosen(null);
            setYear(null);
          }}
          className="new-declaration-modelo flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left hover:bg-accent"
        >
          <span className="flex h-8 w-12 items-center justify-center rounded-md border border-border-strong font-mono text-base font-semibold">
            {m.code}
          </span>
          <span className="min-w-0 flex-1 truncate text-base">{m.title}</span>
          {count > 0 && (
            <Badge>
              {t("workspace.declarations.list.new.open_count", { count })}
            </Badge>
          )}
          <Icon name="forward" size="xs" className="text-faint" />
        </button>
      </li>
    );
  };

  const busy = attempt.kind === "creating";
  const held = attempt.kind === "unknown";

  return (
    <DialogContent
      // Choosing a modelo, the list takes the room left and scrolls.
      className={cn(
        "new-declaration w-palette",
        modelo === null &&
          targets.length > 0 &&
          "grid-rows-[auto_auto_minmax(0,1fr)]",
      )}
      placement="top"
      closeLabel={t("workspace.modelo.key.close")}
    >
      {targets.length === 0 ? (
        <>
          <DialogHeader>
            <DialogTitle>
              {t("workspace.declarations.list.key.new")}
            </DialogTitle>
          </DialogHeader>
          <Alert icon={<Icon name="info" />}>
            {t("workspace.declarations.list.new.none")}
          </Alert>
        </>
      ) : modelo === null ? (
        <>
          <DialogHeader>
            <DialogTitle>
              {t("workspace.declarations.list.key.new")}
            </DialogTitle>
            <DialogDescription>
              {t("workspace.declarations.list.new.which_modelo")}
            </DialogDescription>
          </DialogHeader>
          <Input
            autoFocus
            placeholder={t(
              "workspace.declarations.list.new.search_placeholder",
            )}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label={t("workspace.declarations.list.search.modelo")}
          />
          {found.length === 0 ? (
            <p className="px-3 text-base text-muted-foreground">
              {t("workspace.declarations.list.new.no_match", { query })}
            </p>
          ) : (
            <div className="-mx-2 flex min-h-0 flex-col gap-3 overflow-y-auto px-2">
              {[true, false].map((expected) => {
                const list = found.filter((m) => m.expected === expected);
                if (!list.length) return null;
                return (
                  <div key={String(expected)}>
                    <h3 className="px-3 pb-1 text-sm font-medium text-muted-foreground">
                      {t(
                        expected
                          ? "workspace.declarations.list.new.expected"
                          : "workspace.declarations.list.new.other",
                      )}
                    </h3>
                    <ul>{list.map(tile)}</ul>
                  </div>
                );
              })}
            </div>
          )}
        </>
      ) : (
        <>
          <DialogHeader>
            <Button
              variant="link"
              size="xs"
              className="self-start text-sm text-muted-foreground"
              disabled={busy}
              onClick={() => {
                setModelo(null);
                setAttempt({ kind: "idle" });
              }}
            >
              <Icon name="back" size="xs" />{" "}
              {t("workspace.declarations.list.new.another")}
            </Button>
            <DialogTitle>
              {modelos.find((m) => m.code === modelo)?.title ?? modelo}
            </DialogTitle>
            <DialogDescription>
              {t(
                yearly
                  ? "workspace.declarations.list.new.which_year"
                  : "workspace.declarations.list.new.which_period",
              )}
            </DialogDescription>
          </DialogHeader>
          {!yearly && years.length > 1 && (
            <SegmentedControl
              aria-label={t("workspace.declarations.list.new.year")}
              value={String(shownYear)}
              onValueChange={(value) => {
                setYear(Number(value));
                setChosen(null);
              }}
              className="self-start"
            >
              {years.map((y) => (
                <SegmentedControlItem
                  key={y}
                  value={String(y)}
                  className="flex-none px-3"
                >
                  {y}
                </SegmentedControlItem>
              ))}
            </SegmentedControl>
          )}
          <div
            role="radiogroup"
            aria-label={t("workspace.declarations.list.column.period")}
            className={cn(
              "grid gap-2",
              yearly || periods.length === 1 ? "grid-cols-1" : "grid-cols-2",
            )}
          >
            {(yearly ? forModelo : periods).map((target) => {
              const pick = picked === target;
              return (
                <button
                  key={`${target.filing_year}-${target.period_code}`}
                  type="button"
                  role="radio"
                  aria-checked={pick}
                  disabled={busy}
                  onClick={() => {
                    setChosen({
                      filing_year: target.filing_year,
                      code: target.period_code,
                    });
                    setYear(target.filing_year);
                    setAttempt({ kind: "idle" });
                  }}
                  className="new-declaration-period flex flex-col items-start gap-0.5 rounded-lg border border-border px-3 py-2 text-left hover:bg-accent aria-checked:border-foreground aria-checked:bg-selected"
                >
                  <span className="text-base font-medium">
                    {target.period_words}
                  </span>
                  {target.deadline_text && (
                    <span className="text-sm text-muted-foreground">
                      {target.deadline_text}
                    </span>
                  )}
                  <span className="text-xs text-muted-foreground">
                    {target.existing
                      ? target.existing.state_words
                      : t("workspace.declarations.list.state.not_started")}
                  </span>
                </button>
              );
            })}
          </div>
          {attempt.kind === "refused" || attempt.kind === "failed" ? (
            <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
              {t(
                attempt.kind === "refused"
                  ? "workspace.declarations.list.new.refused"
                  : "workspace.declarations.list.new.failed",
              )}{" "}
              <code className="font-mono text-xs">{attempt.code}</code>
            </Alert>
          ) : attempt.kind === "unknown" ? (
            <Alert tone="warning" role="alert" icon={<Icon name="unknown" />}>
              <AlertTitle>
                {t("workspace.declarations.list.new.unknown")}
              </AlertTitle>
              <AlertDescription>
                {t("workspace.declarations.list.new.unknown_next")}
              </AlertDescription>
            </Alert>
          ) : null}
          <DialogFooter>
            <Button variant="ghost" onClick={onClose}>
              {t("workspace.modelo.editor.cancel")}
            </Button>
            <Button
              className="new-declaration-submit"
              disabled={picked === null || busy || held}
              onClick={() => {
                if (picked === null) return;
                if (picked.existing) {
                  onOpen(picked.existing.work_unit_id);
                  onClose();
                } else void create(picked);
              }}
            >
              {busy && <Spinner />}
              {t(
                busy
                  ? "workspace.declarations.list.new.creating"
                  : picked?.existing
                    ? "workspace.declarations.list.new.open_it"
                    : "workspace.declarations.list.new.create_declaration",
              )}
            </Button>
          </DialogFooter>
        </>
      )}
    </DialogContent>
  );
}
