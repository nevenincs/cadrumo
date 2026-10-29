import { useState, type ReactNode } from "react";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import type { AeatSyncAreaId } from "../../shell/aeatSync";
import {
  aeatSyncRunProblems,
  aeatSyncRunShare,
  useAeatSyncRun,
  type AeatSyncRunArea,
  type AeatSyncRunItem,
  type AeatSyncRunPort,
  type AeatSyncRunSnapshot,
} from "../../shell/aeatSyncRun";
import { useStrings, type Translate } from "../../shell/strings";
import { OUTCOME_ICONS } from "./outcomeIcons";
import { UnknownWarning } from "./UnknownWarning";

const KEY = "desktop.aeat_sync.progress.";

type Retry = (
  area: AeatSyncAreaId,
  item: number,
  acknowledgedUnknown: boolean,
) => void;

function Standing({
  icon,
  children,
}: {
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <p className="flex items-start gap-2 text-sm text-foreground [&>svg]:mt-0.5">
      {icon}
      <span className="min-w-0 [overflow-wrap:anywhere]">{children}</span>
    </p>
  );
}

/** The one action a settled part offers. */
function Action({
  t,
  area,
  name,
  item,
  busy,
  confirming,
  onConfirm,
  onRetry,
}: {
  t: Translate;
  area: AeatSyncAreaId;
  name: string;
  item: AeatSyncRunItem;
  busy: boolean;
  confirming: boolean;
  onConfirm(item: number | null): void;
  onRetry: Retry;
}) {
  if (item.state === "failed")
    return (
      <Button
        size="xs"
        variant="outline"
        disabled={busy}
        aria-label={t(`${KEY}try_again_for`, { name })}
        onClick={() => onRetry(area, item.item, false)}
      >
        {t(`${KEY}try_again`)}
      </Button>
    );
  if (item.state === "unknown" && !confirming)
    return (
      <Button
        size="xs"
        variant="outline"
        disabled={busy}
        aria-label={t(`${KEY}check_again_for`, { name })}
        onClick={() => onConfirm(item.item)}
      >
        {t(`${KEY}check_again`)}
      </Button>
    );
  return null;
}

function ItemLine({ t, item }: { t: Translate; item: AeatSyncRunItem }) {
  const outcome = item.state;
  if (outcome === "waiting" || outcome === "not_started")
    return (
      <Standing icon={<Icon name="pending" />}>
        {t(`${KEY}${outcome}`)}
      </Standing>
    );
  if (outcome === "running")
    return <Standing icon={<Spinner />}>{t(`${KEY}running`)}</Standing>;
  return (
    <div className="flex flex-col gap-0.5">
      <Standing icon={<Icon name={OUTCOME_ICONS[outcome]} />}>
        {t(`${KEY}outcome.${outcome}`)}
      </Standing>
      {item.state === "failed" && item.reason && (
        <p className="pl-6 text-sm text-muted-foreground">
          {t(`${KEY}reason.${item.reason}`)}
        </p>
      )}
    </div>
  );
}

function AreaRow({
  t,
  area,
  busy,
  confirming,
  onConfirm,
  onRetry,
}: {
  t: Translate;
  area: AeatSyncRunArea;
  busy: boolean;
  confirming: number | null;
  onConfirm(item: number | null): void;
  onRetry: Retry;
}) {
  const name = t(`desktop.aeat_sync.area.${area.area}.name`);
  const only =
    area.items.length === 1 && area.items[0]!.year === null
      ? area.items[0]!
      : null;
  const { outcome } = area;
  // Year rows say how each part stands; the header speaks for an area that
  // is one part or has none yet.
  let header: ReactNode;
  if (!only && area.items.length > 0) {
    header = null;
  } else if (area.state === "waiting" || area.state === "not_started") {
    header = (
      <Standing icon={<Icon name="pending" />}>
        {t(`${KEY}${area.state}`)}
      </Standing>
    );
  } else if (area.state === "running") {
    header = <Standing icon={<Spinner />}>{t(`${KEY}running`)}</Standing>;
  } else if (only) {
    header = <ItemLine t={t} item={only} />;
  }
  return (
    <li
      data-area={area.area}
      data-state={area.state}
      data-outcome={outcome ?? undefined}
      className="flex flex-col gap-2 overflow-hidden rounded-lg border bg-card p-3"
    >
      <div className="flex items-start gap-2">
        <span className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-foreground">{name}</h3>
          {header}
        </span>
        {only && area.state === "finished" && (
          <Action
            t={t}
            area={area.area}
            name={name}
            item={only}
            busy={busy}
            confirming={confirming === only.item}
            onConfirm={onConfirm}
            onRetry={onRetry}
          />
        )}
      </div>
      {only && confirming === only.item && (
        <UnknownWarning
          busy={busy}
          onProceed={() => {
            onConfirm(null);
            onRetry(area.area, only.item, true);
          }}
          onCancel={() => onConfirm(null)}
        />
      )}
      {!only && area.items.length > 0 && (
        <ul className="flex flex-col divide-y rounded-md border">
          {area.items.map((item) => (
            <li
              key={item.item}
              data-state={item.state}
              className="flex flex-col gap-2 px-3 py-2"
            >
              <div className="flex items-start gap-2">
                <span className="w-12 shrink-0 text-sm font-medium tabular-nums text-foreground">
                  {item.year}
                </span>
                <span className="min-w-0 flex-1">
                  <ItemLine t={t} item={item} />
                </span>
                <Action
                  t={t}
                  area={area.area}
                  name={`${name} ${item.year ?? ""}`.trim()}
                  item={item}
                  busy={busy}
                  confirming={confirming === item.item}
                  onConfirm={onConfirm}
                  onRetry={onRetry}
                />
              </div>
              {confirming === item.item && (
                <UnknownWarning
                  busy={busy}
                  onProceed={() => {
                    onConfirm(null);
                    onRetry(area.area, item.item, true);
                  }}
                  onCancel={() => onConfirm(null)}
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function Summary({
  t,
  snapshot,
  busy,
  onStop,
}: {
  t: Translate;
  snapshot: AeatSyncRunSnapshot;
  busy: boolean;
  onStop(): void;
}) {
  const { state } = snapshot;
  const problems = aeatSyncRunProblems(snapshot);
  const { settled, total } = aeatSyncRunShare(snapshot);
  let icon: ReactNode;
  let key: string;
  if (state === "running" || state === "paused" || state === "stopping") {
    icon = state === "paused" ? <Icon name="pause" /> : <Spinner />;
    key =
      state === "stopping"
        ? `${KEY}stopping`
        : state === "paused"
          ? `${KEY}paused_status`
          : `${KEY}running`;
  } else if (state === "stopped") {
    icon = <Icon name="stop" />;
    key = `${KEY}stopped`;
  } else if (problems > 0) {
    icon = <Icon name="alert" />;
    key = `${KEY}done_problems`;
  } else {
    icon = <Icon name="check" />;
    key = `${KEY}done_all`;
  }
  const stoppable =
    state === "running" || state === "paused" || state === "stopping";
  return (
    <div
      className="flex flex-col gap-2 rounded-lg border bg-card p-3"
      data-run={state}
    >
      <div className="flex items-center gap-3">
        <p
          role="status"
          className="flex min-w-0 flex-1 items-center gap-2 text-base font-medium text-foreground"
        >
          {icon}
          <span>{t(key)}</span>
        </p>
        {stoppable && (
          <Button
            variant="outline"
            size="sm"
            disabled={busy || state === "stopping"}
            onClick={onStop}
          >
            <Icon name="stop" size="sm" />
            {t(`${KEY}stop`)}
          </Button>
        )}
      </div>
      {(state === "running" || state === "stopping") && total > 0 && (
        <Progress
          value={settled}
          max={total}
          aria-label={t(`${KEY}title`)}
          className="text-primary"
        />
      )}
      {state === "running" && (
        <p className="text-sm text-muted-foreground">{t(`${KEY}stop_hint`)}</p>
      )}
    </div>
  );
}

type Run = ReturnType<typeof useAeatSyncRun>;

/**
 * The update from AEAT as it goes: each kind of data in the order it is read,
 * saying in plain words what is happening and how each part came out. Stop is
 * always at hand and lets the step in progress finish. A failed part is read
 * again only when the person presses; a part whose outcome is unknown is
 * never shown as done or as failed, and is read again only after the person
 * is told it may already have been brought. The host owns the queue and the
 * outcomes; this draws what it serves. `paused` replaces the sign-in prompt
 * of a run whose AEAT session ended, for a caller that signs in itself before
 * it resumes the run.
 */
export function AeatSyncRunView({
  run,
  paused,
}: {
  run: Run;
  paused?: ReactNode;
}) {
  const t = useStrings();
  const [confirming, setConfirming] = useState<number | null>(null);
  const { snapshot } = run;
  return (
    <section
      aria-label={t(`${KEY}title`)}
      className="aeat-sync-progress flex w-full flex-col gap-3"
    >
      {run.error && (
        <Alert role="alert" tone="danger" icon={<Icon name="alert" />}>
          {t(`${KEY}unavailable`)}
        </Alert>
      )}
      {run.problem && (
        <Alert role="alert" tone="danger" icon={<Icon name="alert" />}>
          {t(
            run.problem === "unknown"
              ? `${KEY}action_unknown`
              : `${KEY}action_failed`,
          )}
        </Alert>
      )}
      {run.loading && !snapshot && (
        <div
          role="status"
          className="flex items-center gap-2 text-muted-foreground"
        >
          <Spinner />
          {t("desktop.aeat_sync.loading")}
        </div>
      )}
      {snapshot && (
        <>
          <Summary
            t={t}
            snapshot={snapshot}
            busy={run.busy}
            onStop={() => void run.stop()}
          />
          {snapshot.state === "paused" &&
            (paused ?? (
              <Alert tone="warning" icon={<Icon name="alert" />}>
                <AlertTitle>{t(`${KEY}paused`)}</AlertTitle>
                <span className="mt-1">
                  <Button
                    size="sm"
                    disabled={run.busy}
                    onClick={() => void run.resume()}
                  >
                    {t(`${KEY}resume`)}
                  </Button>
                </span>
              </Alert>
            ))}
          <ul aria-label={t(`${KEY}title`)} className="flex flex-col gap-3">
            {snapshot.areas.map((area) => (
              <AreaRow
                key={area.area}
                t={t}
                area={area}
                busy={run.busy}
                confirming={confirming}
                onConfirm={setConfirming}
                onRetry={(id, item, acknowledged) =>
                  void run.retry(id, item, acknowledged)
                }
              />
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

/** The update as it goes, followed from `port` for the profile `reader`. */
export function AeatSyncProgress({
  port,
  reader,
  shown = true,
}: {
  port: AeatSyncRunPort;
  reader: string;
  shown?: boolean;
}) {
  return <AeatSyncRunView run={useAeatSyncRun(port, reader, shown)} />;
}
