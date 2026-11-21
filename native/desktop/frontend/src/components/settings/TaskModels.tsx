import { useId, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { NativeSelect } from "@/components/ui/native-select";
import type { ServedCatalogAnswer } from "../../shell/agentCatalogContract";
import { catalogChoices, effortWords } from "../../shell/agentCatalog";
import type { TaskModelChoice } from "../../shell/agentSession";
import { described, labelled } from "../../shell/compose";
import { addedTo, listRefusalWords } from "../../shell/localModelLanes";
import { useLocalModels, type LocalModelHost } from "../../shell/localModels";
import type { TaskModelEntry } from "../../shell/localModelsContract";
import { modelListState, useWindowReturn } from "../../shell/modelListState";
import { connectionWords } from "../../shell/providerConnection";
import { useStrings, type Translate } from "../../shell/strings";
import {
  taskEfforts,
  taskKindRows,
  taskLanes,
  type TaskKindRow,
  type TaskLaneOption,
} from "../../shell/taskModels";
import type { ProviderOption, ProviderWay } from "../agent/types";
import { ModelListNotice } from "../agent/ModelListNotice";
import { ReadState } from "../agent/ReadState";
import { EngineDoor } from "../setup/EngineDoor";

/** The value a model option carries: its lane and its id, which no lane id
 * or model id contains. */
const optionOf = (lane: string, model: string) => `${lane}\n${model}`;

/** The default every kind starts on: the model documents are read with. */
const READING = "";

/** A lane a task can be set to, with the picker's own standing of it: why it
 * cannot run yet, where the catalog says so. */
type LaneStanding = {
  lane: TaskLaneOption;
  provider: ProviderOption;
  way: ProviderWay;
};

/** The words a held lane is said with, as the model picker says them. */
const heldWords = (t: Translate, { provider, way }: LaneStanding) =>
  labelled(
    t,
    described(t, provider.name, connectionWords(t, way)),
    way.unavailableReason ?? t("desktop.agent.unavailable"),
  );

/**
 * What each kind of background task the agent serves runs with: a model on
 * a lane, and an effort where the lane takes one for that model, or, by
 * default, the model documents are read with. The kinds, lanes, models and
 * efforts are the ones the catalogue serves; each change is stored by the
 * agent service at the revision read, and says whether it was. A lane that
 * cannot run yet is said with its reason and the step the picker offers for
 * it, and a list that cannot be read says why and how it is set right.
 */
export function TaskModels({
  host,
  catalog,
  catalogStatus,
  catalogFailure = null,
  onRetryCatalog,
  onShowProvider,
}: {
  host: LocalModelHost;
  /** The catalogue the agent serves, once read. */
  catalog: ServedCatalogAnswer | null;
  catalogStatus: "ready" | "loading" | "failed";
  /** The refusal the catalogue read answered, while it is failed. */
  catalogFailure?: string | null;
  onRetryCatalog: () => void;
  /** Opens a provider's own settings, where it is signed in to, set up or
   * has its models downloaded. */
  onShowProvider?: (provider: string) => void;
}) {
  const t = useStrings();
  const { snapshot, retry, busy, outcomes, change } = useLocalModels(host);
  const lists = snapshot.kind === "ready" ? snapshot.value : null;
  useWindowReturn(
    snapshot.kind === "failed" && modelListState(snapshot.code) !== null
      ? retry
      : null,
  );
  const rows = useMemo(
    () => (catalog && lists ? taskKindRows(catalog, lists) : []),
    [catalog, lists],
  );
  const lanes = useMemo(
    () => (catalog && lists ? taskLanes(catalog, lists) : []),
    [catalog, lists],
  );
  // The picker's standing of each lane, from the same catalogue and lists.
  const standings = useMemo((): LaneStanding[] => {
    if (!catalog || !lists) return [];
    const offer = catalogChoices(t, catalog, {
      lanes: lists.local_lanes,
      added: (lane) => addedTo(lists, lane),
    });
    return lanes.flatMap((lane) => {
      const provider = offer.providers.find(
        (held) => held.id === lane.provider,
      );
      const way = provider?.ways.find((held) => held.id === lane.way);
      return provider && way ? [{ lane, provider, way }] : [];
    });
  }, [catalog, lists, lanes, t]);
  const held = standings.filter(({ way }) => !way.selectable);
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
  if (!lists || !catalog)
    return <ReadState read={{ kind: "loading" }} icon="settings" />;
  const choose = (kind: string, choice: TaskModelChoice | null) =>
    void change(kind, (revision) => chooseTask(kind, choice, revision));
  // The step the picker offers for a held lane, where this window has one:
  // the engine's door, asking again, or the provider's own settings, where
  // it is signed in to, set up or has its models downloaded.
  const step = ({ way, provider }: LaneStanding) => {
    if (way.engineNotRunning)
      return <EngineDoor door={way.engineNotRunning.door} />;
    const show = onShowProvider ? () => onShowProvider(provider.id) : undefined;
    const [kind, words, act] =
      way.heldStep === "retry"
        ? ["retry", t("desktop.agent.retry"), onRetryCatalog]
        : way.heldStep === "sign_in"
          ? ["sign_in", t("desktop.providers.sign_in_action"), show]
          : way.modelsToDownload
            ? ["download", t("desktop.agent.download_models"), show]
            : ["set_up", t("desktop.agent.set_up_providers"), show];
    return (
      act && (
        <Button variant="outline" size="xs" data-held-step={kind} onClick={act}>
          {words}
        </Button>
      )
    );
  };
  const selectable = (lane: string) =>
    standings.find((standing) => standing.lane.id === lane)?.way.selectable ??
    true;
  return (
    <div className="grid gap-3">
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
      {held.length > 0 && (
        <ul data-slot="task-models-held" className="grid gap-2">
          {held.map((standing) => (
            <li
              key={standing.lane.id}
              data-held-lane={standing.lane.id}
              className="grid justify-items-start gap-1.5 text-sm text-muted-foreground"
            >
              <span>{heldWords(t, standing)}</span>
              {step(standing)}
            </li>
          ))}
        </ul>
      )}
      <ul className="grid gap-4">
        {rows.map((row) => {
          const outcome = outcomes[row.id];
          return (
            <TaskModelRow
              key={row.id}
              row={row}
              lanes={lanes}
              selectable={selectable}
              busy={busy !== null || lists.unreadable}
              words={
                outcome?.kind === "saved"
                  ? {
                      role: "status",
                      text: t("desktop.providers.task_model_saved"),
                    }
                  : outcome?.kind === "refused"
                    ? {
                        role: "alert",
                        text:
                          outcome.code === "agent_local_models_unknown"
                            ? t("desktop.providers.task_model_refused")
                            : listRefusalWords(t, outcome.code),
                      }
                    : null
              }
              onChoose={(choice) => choose(row.id, choice)}
            />
          );
        })}
      </ul>
    </div>
  );
}

function TaskModelRow({
  row,
  lanes,
  selectable,
  busy,
  words,
  onChoose,
}: {
  row: TaskKindRow;
  lanes: readonly TaskLaneOption[];
  /** Whether a task can run on the lane now, as the picker says. */
  selectable: (lane: string) => boolean;
  busy: boolean;
  words: { role: "status" | "alert"; text: string } | null;
  onChoose: (choice: TaskModelChoice | null) => void;
}) {
  const t = useStrings();
  const modelId = useId();
  const effortId = useId();
  const descriptionId = useId();
  const setting = row.setting;
  // A stored setting the catalogue no longer offers is still what the kind
  // is set to, so it stays shown, named as stored.
  const offered = (entry: TaskModelEntry) =>
    lanes.some(
      (lane) =>
        lane.id === entry.lane &&
        lane.models.some((model) => model.id === entry.model),
    );
  const efforts = setting
    ? taskEfforts(lanes, setting.lane, setting.model)
    : [];
  const storedEffort =
    setting?.effort && !efforts.some((effort) => effort === setting.effort)
      ? setting.effort
      : null;
  return (
    <li data-slot="task-model" data-task-kind={row.id} className="grid gap-2">
      <Field>
        <FieldLabel htmlFor={modelId}>
          {t("desktop.providers.task_model_model", { task: row.name })}
        </FieldLabel>
        <FieldDescription id={descriptionId}>
          {row.description}
        </FieldDescription>
        <NativeSelect
          id={modelId}
          controlSize="sm"
          aria-describedby={descriptionId}
          disabled={busy}
          value={setting ? optionOf(setting.lane, setting.model) : READING}
          onChange={(event) => {
            const value = event.target.value;
            if (value === READING) {
              onChoose(null);
              return;
            }
            const [lane, model] = value.split("\n");
            if (lane === undefined || model === undefined) return;
            // An effort carries over where the new model takes it.
            const effort =
              setting?.effort &&
              taskEfforts(lanes, lane, model).some(
                (held) => held === setting.effort,
              )
                ? setting.effort
                : null;
            onChoose({ lane, model, effort });
          }}
        >
          <option value={READING}>
            {t("desktop.providers.task_model_reading")}
          </option>
          {setting && !offered(setting) && (
            <option value={optionOf(setting.lane, setting.model)}>
              {`${setting.lane} · ${setting.model}`}
            </option>
          )}
          {lanes
            .filter((lane) => lane.models.length > 0)
            .map((lane) => (
              <optgroup
                key={lane.id}
                label={lane.name}
                disabled={!selectable(lane.id) || undefined}
                data-lane={lane.id}
              >
                {lane.models.map((model) => (
                  <option
                    key={model.id}
                    value={optionOf(lane.id, model.id)}
                    disabled={!model.installed || undefined}
                    data-installed={model.installed ? undefined : "false"}
                  >
                    {model.installed
                      ? model.name
                      : t("desktop.agent.model_not_installed", {
                          name: model.name,
                        })}
                  </option>
                ))}
              </optgroup>
            ))}
        </NativeSelect>
      </Field>
      {setting && (efforts.length > 0 || storedEffort) && (
        <Field>
          <FieldLabel htmlFor={effortId}>
            {t("desktop.providers.task_model_effort", { task: row.name })}
          </FieldLabel>
          <NativeSelect
            id={effortId}
            controlSize="sm"
            disabled={busy}
            value={setting.effort ?? ""}
            onChange={(event) => {
              const effort = event.target.value;
              onChoose({
                lane: setting.lane,
                model: setting.model,
                effort: effort === "" ? null : effort,
              });
            }}
          >
            <option value="">{t("desktop.agent.effort_default")}</option>
            {storedEffort && (
              <option value={storedEffort}>{storedEffort}</option>
            )}
            {efforts.map((effort) => (
              <option key={effort} value={effort}>
                {effortWords(t, effort)}
              </option>
            ))}
          </NativeSelect>
        </Field>
      )}
      {words && (
        <p role={words.role} className="text-sm">
          {words.text}
        </p>
      )}
    </li>
  );
}
