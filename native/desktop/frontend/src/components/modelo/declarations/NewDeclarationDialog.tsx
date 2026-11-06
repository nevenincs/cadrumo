import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
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
import { createWorkRequest, type ModeloPort } from "../../../shell/modelo";
import {
  creationWriteKey,
  type ModeloWriteHolds,
} from "../../../shell/modeloWriteHolds";
import { runOperation } from "../dialogs/operationRun";
import { WriteHoldNotice, useModeloWriteHold } from "../WriteHoldNotice";
import type { PublicPeriod } from "../../../shell/modeloContract/modelo";
import type {
  ModeloDeclarationCreationTargetV1 as Target,
  ModeloDeclarationListRowV1,
} from "../../../shell/modeloContract/modeloDeclarations";
import { useStrings } from "../../../shell/strings";

/** Where the dialog starts: a modelo, and a period within it. */
export type NewDeclarationStart = {
  modelo: string;
  period: PublicPeriod | null;
};

type Attempt =
  | { kind: "idle" }
  /** `words` is why, as the backend served it; null when it served none. */
  | { kind: "refused"; words: string | null }
  | { kind: "failed" };

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
  holds,
  onReload,
  refreshing,
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
  holds: ModeloWriteHolds;
  onReload: () => void;
  refreshing: boolean;
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
          holds={holds}
          onReload={onReload}
          refreshing={refreshing}
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
  holds,
  onReload,
  refreshing,
}: {
  port: ModeloPort;
  targets: readonly Target[];
  rows: readonly ModeloDeclarationListRowV1[];
  start: NewDeclarationStart | null;
  onOpen: (workUnitId: string) => void;
  onWritten: () => void;
  onClose: () => void;
  holds: ModeloWriteHolds;
  onReload: () => void;
  refreshing: boolean;
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
  const alive = useRef(false);
  const generation = useRef(0);
  const activeTarget = useRef("");
  useLayoutEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      generation.current += 1;
    };
  }, [holds, port]);

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
  const targetKey = picked ? creationWriteKey(picked) : "";
  const hold = useModeloWriteHold(holds, targetKey);
  useLayoutEffect(() => {
    activeTarget.current = targetKey;
  }, [targetKey]);
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
    const key = creationWriteKey(target);
    const lease = holds.begin(key);
    if (!lease) return;
    const mine = generation.current;
    setAttempt({ kind: "idle" });
    const outcome = await runOperation(
      port,
      () => port.submit("modelo.work.create", createWorkRequest(target)),
      () => alive.current && mine === generation.current,
    );
    const current = () =>
      alive.current &&
      mine === generation.current &&
      activeTarget.current === key;
    if (outcome.kind === "settled") {
      const result = outcome.result.outcome;
      if (result.kind === "success") {
        holds.needsRead(lease);
        onWritten();
        if (current()) {
          onOpen(result.unit.work_unit_id);
          onClose();
        }
      } else {
        holds.notWritten(lease);
        if (current()) setAttempt({ kind: "refused", words: null });
      }
    } else if (outcome.kind === "unknown") {
      holds.unknown(lease, outcome.operationId);
      onWritten();
    } else if (outcome.kind === "saved_unread") {
      holds.needsRead(lease, true);
      onWritten();
    } else {
      holds.notWritten(lease);
      if (current())
        setAttempt(
          outcome.kind === "refused"
            ? { kind: "refused", words: outcome.words }
            : { kind: "failed" },
        );
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

  const busy = hold?.phase === "running";
  const held = hold !== undefined;

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
                setAttempt({ kind: "idle" });
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
              {attempt.kind === "refused"
                ? (attempt.words ??
                  t("workspace.declarations.list.new.refused"))
                : t("workspace.declarations.list.new.failed")}
            </Alert>
          ) : null}
          <WriteHoldNotice
            holds={holds}
            target={targetKey}
            port={port}
            onReload={onReload}
            refreshing={refreshing}
            creation
          />
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
