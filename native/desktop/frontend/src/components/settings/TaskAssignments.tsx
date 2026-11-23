import { useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
} from "@/components/ui/popover";
import {
  effortWords,
  EFFORTS,
  taskModelsOf,
  type AgentOffer,
  type OfferedModel,
  type OfferedTask,
} from "../../shell/agentOffer";
import { useAgentOffer } from "../../shell/agentOfferContext";
import type { TaskModelChoice } from "../../shell/agentSession";
import { described, noted } from "../../shell/compose";
import { listRefusalWords } from "../../shell/localModelLanes";
import { useLocalModels, type LocalModelHost } from "../../shell/localModels";
import { connectionWords } from "../../shell/providerConnection";
import { modelListState, useWindowReturn } from "../../shell/modelListState";
import { useStrings, type Translate } from "../../shell/strings";
import { ModelListNotice } from "../agent/ModelListNotice";
import { ModelMatrix } from "../agent/ModelMatrix";
import { ReadState } from "../agent/ReadState";

/** The model a task setting names, where a lane the offer has lists it. */
function modelOf(
  offer: AgentOffer,
  lane: string,
  model: string,
): OfferedModel | null {
  const held = offer.lanes.get(lane);
  return (
    (held ? taskModelsOf(held) : []).find((each) => each.model === model) ??
    null
  );
}

/** What a task runs with, in words: the model and its lane, a setting the
 * catalogue no longer offers, or the model documents are read with, said as
 * chosen or as the default that stands in until one is. */
function runsWith(t: Translate, offer: AgentOffer, task: OfferedTask): string {
  const { setting } = task;
  if (setting) {
    const lane = offer.lanes.get(setting.lane);
    const model = modelOf(offer, setting.lane, setting.model);
    // A lane that cannot run now keeps the setting: it is said with the
    // reason the lane gives, and runs again once the lane does.
    if (lane && model && !lane.runs)
      return noted(
        t,
        described(t, model.name, lane.name, connectionWords(t, lane)),
        lane.held?.words ?? t("desktop.agent.unavailable"),
      );
    if (!task.offered || !lane || !model)
      return t("desktop.providers.task_model_stored_unoffered", {
        model: model?.name ?? setting.model,
        lane: lane?.name ?? setting.lane,
      });
    return described(t, model.name, lane.name, connectionWords(t, lane));
  }
  const { reading } = offer;
  if (!reading) return t("desktop.providers.task_model_reading_none");
  const name =
    modelOf(offer, reading.lane, reading.model)?.name ?? reading.model;
  return reading.source === "chosen"
    ? t("desktop.providers.task_model_reading_chosen", { model: name })
    : t("desktop.providers.task_model_reading_default", { model: name });
}

/** The effort a task runs with, in words: the one set, else the provider's
 * own default, which a run that names no effort gets, with the catalogue's
 * default beside it where it names one. */
function effortOf(t: Translate, offer: AgentOffer, task: OfferedTask): string {
  const { setting } = task;
  const stored = EFFORTS.find((effort) => effort === setting?.effort);
  if (stored) return effortWords(t, stored);
  if (setting?.effort) return setting.effort;
  const fallback = setting
    ? modelOf(offer, setting.lane, setting.model)?.defaultEffort
    : null;
  return fallback
    ? noted(
        t,
        t("desktop.agent.effort_provider_default"),
        t("desktop.agent.effort_catalog_default", {
          effort: effortWords(t, fallback),
        }),
      )
    : t("desktop.agent.effort_provider_default");
}

/**
 * What each kind of background task the agent serves runs with, one compact
 * row per kind: the model and its lane, or the model documents are read with
 * (said as chosen or as the default standing in), the effort, which left
 * unset is the provider's own default, and a way to change both in the one
 * model matrix the agent column shares. Each change is stored by the agent
 * service at the revision read, and says whether it was; a list that cannot
 * be read says why and how it is set right.
 */
export function TaskAssignments({
  host,
  catalogStatus,
  catalogFailure = null,
  onRetryCatalog,
  onShowProvider,
}: {
  host: LocalModelHost;
  catalogStatus: "ready" | "loading" | "failed";
  /** The refusal the catalogue read answered, while it is failed. */
  catalogFailure?: string | null;
  onRetryCatalog: () => void;
  /** Opens a provider's own settings, where it is signed in to, set up,
   * turned on or has its models downloaded. */
  onShowProvider?: (provider: string) => void;
}) {
  const t = useStrings();
  const offer = useAgentOffer();
  const { snapshot, retry, busy, outcomes, change } = useLocalModels(host);
  const [editing, setEditing] = useState<string | null>(null);
  // The Change button the matrix was opened from, which it stands by.
  const anchor = useRef<HTMLElement | null>(null);
  // A step that leads to a provider's settings moves focus there; the
  // closing popover must not take it back to the row's button.
  const ledAway = useRef(false);
  const headingId = useId();
  const lists = snapshot.kind === "ready" ? snapshot.value : null;
  useWindowReturn(
    snapshot.kind === "failed" && modelListState(snapshot.code) !== null
      ? retry
      : null,
  );
  const chooseTask = host.chooseTask;
  if (!chooseTask) return null;
  if (snapshot.kind === "failed")
    return (
      <ModelListNotice
        code={snapshot.code}
        fault={t("desktop.providers.local_models_failed")}
        onRetry={retry}
        slot="task-models-lists"
      />
    );
  if (catalogStatus === "failed")
    return (
      <ModelListNotice
        code={catalogFailure ?? ""}
        fault={t("desktop.agent.read_failed")}
        onRetry={onRetryCatalog}
        slot="task-models-catalog"
      />
    );
  if (!lists || !offer)
    return <ReadState read={{ kind: "loading" }} icon="settings" />;
  const locked = busy !== null || lists.unreadable;
  const choose = (kind: string, choice: TaskModelChoice | null) =>
    void change(kind, (revision) => chooseTask(kind, choice, revision));
  const task = offer.tasks.find((held) => held.id === editing) ?? null;
  const show = onShowProvider
    ? (lane: { provider: string }) => {
        ledAway.current = true;
        setEditing(null);
        onShowProvider(lane.provider);
      }
    : undefined;
  // With no provider on, the way on is turning one on in its settings.
  const firstOff =
    [...offer.lanes.values()].find((lane) => lane.on === false) ??
    offer.turnedOff[0];
  return (
    // Narrow, a task is a block of its own: its name over what it runs
    // with, so neither is squeezed into a column of a few words.
    <div className="@container/tasks grid gap-3">
      <p className="text-sm text-muted-foreground">
        {t("desktop.providers.task_models_intro")}
      </p>
      {lists.unreadable && (
        <div data-slot="task-models-unreadable" className="grid gap-2 text-sm">
          <p role="alert" className="flex items-start gap-2">
            <Icon name="alert" className="mt-0.5 text-destructive" />
            <span>{t("desktop.providers.local_models_unreadable")}</span>
          </p>
          <Button
            variant="outline"
            size="sm"
            className="justify-self-start"
            disabled={busy !== null}
            onClick={() =>
              void change("reset", (revision) => host.reset(revision))
            }
          >
            {t("desktop.providers.local_models_reset")}
          </Button>
          {outcomes.reset?.kind === "refused" && (
            <p role="alert">{listRefusalWords(t, outcomes.reset.code)}</p>
          )}
        </div>
      )}
      <table className="w-full text-sm @max-md/tasks:block">
        <thead className="sr-only">
          <tr>
            <th scope="col">{t("desktop.providers.task_models_task")}</th>
            <th scope="col">{t("desktop.providers.task_models_runs_with")}</th>
            <th scope="col">{t("desktop.agent.effort")}</th>
            <th scope="col">{t("desktop.providers.task_model_change")}</th>
          </tr>
        </thead>
        <tbody className="@max-md/tasks:block">
          {offer.tasks.map((row) => {
            const outcome = outcomes[row.id];
            return (
              <tr
                key={row.id}
                data-slot="task-model"
                data-task-kind={row.id}
                data-offered={row.setting && !row.offered ? "false" : undefined}
                className="border-t align-top first:border-t-0 @max-md/tasks:flex @max-md/tasks:flex-wrap @max-md/tasks:items-start @max-md/tasks:gap-x-3 @max-md/tasks:py-2"
              >
                <th
                  scope="row"
                  className="py-2 pr-3 text-left font-normal @max-md/tasks:basis-full @max-md/tasks:p-0"
                >
                  <span className="block font-medium">{row.name}</span>
                  <span className="block text-muted-foreground">
                    {row.description}
                  </span>
                  {outcome && (
                    <span
                      role={outcome.kind === "refused" ? "alert" : "status"}
                      className={cn(
                        "block pt-1",
                        outcome.kind === "refused" && "text-destructive",
                      )}
                    >
                      {outcome.kind === "saved"
                        ? t("desktop.providers.task_model_saved")
                        : outcome.code === "agent_local_models_unknown"
                          ? t("desktop.providers.task_model_refused")
                          : listRefusalWords(t, outcome.code)}
                    </span>
                  )}
                </th>
                <td
                  data-slot="task-model-runs-with"
                  className="py-2 pr-3 @max-md/tasks:basis-full @max-md/tasks:p-0 @max-md/tasks:pt-1"
                >
                  {runsWith(t, offer, row)}
                </td>
                <td
                  data-slot="task-model-effort"
                  className="py-2 pr-3 @max-md/tasks:flex-1 @max-md/tasks:p-0 @max-md/tasks:pt-1 @max-md/tasks:text-muted-foreground"
                >
                  {effortOf(t, offer, row)}
                </td>
                <td className="py-2 text-right @max-md/tasks:p-0">
                  <Button
                    variant="outline"
                    size="xs"
                    disabled={locked}
                    aria-haspopup="dialog"
                    aria-expanded={editing === row.id}
                    aria-label={t("desktop.providers.task_model_change_label", {
                      task: row.name,
                    })}
                    onClick={(event) => {
                      anchor.current = event.currentTarget;
                      ledAway.current = false;
                      setEditing(row.id);
                    }}
                  >
                    {t("desktop.providers.task_model_change")}
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <Popover
        open={task !== null}
        onOpenChange={(open) => {
          if (!open) setEditing(null);
        }}
      >
        <PopoverAnchor virtualRef={anchor} />
        {task && (
          <PopoverContent
            align="end"
            aria-labelledby={headingId}
            // The matrix scrolls inside its own box; the popover holds it
            // whole, so nothing it lists is drawn past the popover's edge.
            className="flex w-dialog-lg flex-col gap-3 overflow-hidden"
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              if (!ledAway.current) anchor.current?.focus();
              ledAway.current = false;
            }}
          >
            <p id={headingId} className="font-medium">
              {t("desktop.providers.task_model_model", { task: task.name })}
            </p>
            <Button
              variant="outline"
              size="sm"
              className="justify-self-start"
              aria-pressed={task.setting === null}
              disabled={locked}
              onClick={() => choose(task.id, null)}
            >
              {t("desktop.providers.task_model_use_reading")}
            </Button>
            <p className="text-sm text-muted-foreground">
              {runsWith(t, offer, { ...task, setting: null })}
            </p>
            <ModelMatrix
              mode="task"
              label={t("desktop.providers.task_model_model", {
                task: task.name,
              })}
              value={
                task.setting
                  ? {
                      lane: task.setting.lane,
                      model: task.setting.model,
                      effort: task.setting.effort,
                    }
                  : null
              }
              disabled={locked}
              onChoose={({ lane, model, effort }) =>
                choose(task.id, { lane: lane.id, model, effort })
              }
              steps={{
                retry: onRetryCatalog,
                ...(show
                  ? { sign_in: show, download: show, set_up: show }
                  : {}),
              }}
              onOpenProviders={
                show && firstOff ? () => show(firstOff) : undefined
              }
            />
          </PopoverContent>
        )}
      </Popover>
    </div>
  );
}
