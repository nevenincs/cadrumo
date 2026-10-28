import { useId, useState, type FormEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import {
  addedTo,
  laneModelList,
  listRefusalWords,
  sizeWords,
  type CatalogLane,
  type LaneModel,
} from "../../shell/localModelLanes";
import type { AgentModelLicenceFacts } from "../../shell/agentSession";
import { useLocalModels, type LocalModelHost } from "../../shell/localModels";
import { useProvisioning } from "../../shell/provisioning";
import { useStrings, type Translate } from "../../shell/strings";
import { StepFigure, type StepProgress } from "../setup/ProvisioningRow";
import { refusalWords } from "../setup/setupWords";

const licenceWords = (licence: AgentModelLicenceFacts) =>
  licence.spdx && licence.spdx !== licence.name
    ? `${licence.name} (${licence.spdx})`
    : licence.name;

/** Why a model was not removed from this computer, in words. */
function removalWords(t: Translate, code: string): string {
  return code === "model_not_removed"
    ? t("desktop.providers.local_model_remove_failed")
    : refusalWords(t, code);
}

/** What the catalog states of one model: its licence, said even where it is
 * not known, and its download size where it is. */
function ModelFacts({ model, locale }: { model: LaneModel; locale: string }) {
  const t = useStrings();
  return (
    <ul data-slot="model-facts" className="grid gap-0.5 text-sm">
      <li data-fact="licence">
        {model.licence
          ? t("desktop.providers.local_model_licence", {
              licence: licenceWords(model.licence),
            })
          : t("desktop.providers.local_model_licence_unknown")}
      </li>
      {model.sizeBytes !== null && (
        <li data-fact="size">
          {t("desktop.providers.local_model_size", {
            size: sizeWords(locale, model.sizeBytes),
          })}
        </li>
      )}
    </ul>
  );
}

/** One listed model, its download's progress while the local AI's setup
 * pulls it, and its download or removal action. */
function LocalModelRow({
  model,
  added,
  locale,
  busy,
  refusal,
  progress,
  onDownload,
  onRemove,
}: {
  model: LaneModel;
  added: boolean;
  locale: string;
  busy: boolean;
  refusal: string | null;
  /** What the local AI's latest setup reports of this model, where it
   * planned it and its outcome is still news. */
  progress: StepProgress | null;
  onDownload?: () => void;
  onRemove?: () => void;
}) {
  const t = useStrings();
  const headingId = useId();
  return (
    <li
      data-model={model.id}
      data-added={added || undefined}
      data-installed={model.installed ?? undefined}
      aria-labelledby={headingId}
      className="grid gap-1.5 rounded-md bg-background p-2"
    >
      <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
        <h6
          id={headingId}
          className="min-w-0 font-medium wrap-anywhere text-foreground"
        >
          {model.name}
        </h6>
        {model.installed !== null && (
          <Badge variant={model.installed ? "success" : "neutral"}>
            {t(
              model.installed
                ? "desktop.providers.local_model_installed"
                : "desktop.providers.local_model_absent",
            )}
          </Badge>
        )}
      </div>
      <ModelFacts model={model} locale={locale} />
      {progress && (
        <StepFigure progress={progress} name={model.name} locale={locale} />
      )}
      <div className="flex flex-wrap gap-2">
        {model.installed !== true && (
          <Button
            variant="outline"
            size="sm"
            disabled={busy || !onDownload}
            onClick={onDownload}
          >
            {t("desktop.providers.local_model_download")}
          </Button>
        )}
        {onRemove && (
          <Button variant="ghost" size="sm" disabled={busy} onClick={onRemove}>
            {t("desktop.providers.local_model_remove")}
          </Button>
        )}
      </div>
      {refusal && (
        <p role="alert" className="flex items-start gap-2 text-sm">
          <Icon name="alert" className="mt-0.5 text-destructive" />
          <span>{refusal}</span>
        </p>
      )}
    </li>
  );
}

/** Adds a model to the lane's list by the name the local AI pulls it by. */
function AddModel({
  busy,
  onAdd,
}: {
  busy: boolean;
  onAdd: (model: string) => Promise<boolean>;
}) {
  const t = useStrings();
  const nameId = useId();
  const [name, setName] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const model = name.trim();
    if (!model) return;
    void onAdd(model).then((added) => {
      if (added) setName("");
    });
  };
  return (
    <form
      data-slot="local-model-add"
      className="flex flex-wrap items-end gap-2"
      onSubmit={submit}
    >
      <Field className="min-w-0 flex-1">
        <FieldLabel htmlFor={nameId}>
          {t("desktop.providers.local_model_add_label")}
        </FieldLabel>
        <Input
          id={nameId}
          value={name}
          autoComplete="off"
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          onChange={(event) => setName(event.currentTarget.value)}
        />
      </Field>
      <Button
        type="submit"
        variant="outline"
        size="sm"
        disabled={busy || name.trim() === ""}
      >
        {t("desktop.providers.local_model_add")}
      </Button>
    </form>
  );
}

/** A local lane's model list: what the agent recommends and what the person
 * added by name, each downloaded and removed here through the local AI's
 * setup, whose progress each model shows. The list is what the agent's model
 * picker offers of the lane; the model the person picks there is the one the
 * agent and document reading run with. */
export function LocalModels({
  lane,
  host,
  locale,
  onRemoved,
}: {
  lane: CatalogLane | null;
  host: LocalModelHost;
  locale: string;
  /** Told once a model is removed from this computer. */
  onRemoved?: () => void;
}) {
  const t = useStrings();
  const store = useProvisioning();
  const { snapshot, busy, outcomes, change } = useLocalModels(host);
  // Downloading and removing are setup's: offered only where this window
  // offers setup, and a download waits while the local AI sets up.
  const localAi = store.localAiRow;
  const settingUp = localAi !== null && store.liveRunOf(localAi.item) !== null;
  const onSetUp =
    store.offered && localAi !== null
      ? (model: string) => {
          if (lane) store.downloadModel(lane.id, model);
        }
      : undefined;
  const onRemove = store.offered ? store.removeModel : undefined;
  /** What the latest local AI setup says of `model`: its progress while it
   * runs, and how it ended while the catalog does not yet show the model
   * here, or when it failed. */
  const progressOf = (model: LaneModel): StepProgress | null => {
    const part = store.modelPart(model.id);
    if (!part) return null;
    if (part.result === null) return settingUp ? part : null;
    return part.result.failure !== null || model.installed !== true
      ? part
      : null;
  };
  const [removing, setRemoving] = useState<string | null>(null);
  const [removals, setRemovals] = useState<Record<string, string>>({});
  const readable =
    snapshot.kind === "ready" && snapshot.value.state === "readable";
  const listed =
    lane && snapshot.kind === "ready"
      ? laneModelList(lane, addedTo(snapshot.value, lane.id))
      : [];
  // Removing deletes the download first, then takes a model the person added
  // off the list; a recommended model stays listed.
  const remove = async (key: string, model: LaneModel, added: boolean) => {
    if (!lane) return;
    setRemoving(key);
    setRemovals((held) => {
      const next = { ...held };
      delete next[key];
      return next;
    });
    try {
      if (model.installed === true) {
        if (!onRemove) return;
        const code = await onRemove(model.id);
        if (code) {
          setRemovals((held) => ({ ...held, [key]: code }));
          return;
        }
        onRemoved?.();
      }
      if (added)
        await change(key, (revision) =>
          host.remove(lane.id, model.id, revision),
        );
    } finally {
      setRemoving(null);
    }
  };
  const working = busy !== null || removing !== null;
  return (
    <section data-slot="local-models" className="grid gap-2 pt-1">
      <h6 className="text-sm font-medium text-foreground">
        {t("desktop.providers.local_models_title")}
      </h6>
      <p className="text-sm text-muted-foreground">
        {t("desktop.providers.local_models_lead")}
      </p>
      {!lane ? (
        <p className="text-sm text-muted-foreground">
          {t("desktop.providers.local_models_none")}
        </p>
      ) : snapshot.kind === "loading" ? (
        <p className="text-sm text-muted-foreground">
          {t("desktop.providers.local_models_loading")}
        </p>
      ) : snapshot.kind === "failed" ? (
        <p role="alert" className="flex items-start gap-2 text-sm">
          <Icon name="alert" className="mt-0.5 text-destructive" />
          <span>{t("desktop.providers.local_models_failed")}</span>
        </p>
      ) : (
        <>
          {!readable && (
            <div
              data-slot="local-models-unreadable"
              className="grid gap-2 text-sm"
            >
              <p role="alert" className="flex items-start gap-2">
                <Icon name="alert" className="mt-0.5 text-destructive" />
                <span>{t("desktop.providers.local_models_unreadable")}</span>
              </p>
              <Button
                variant="outline"
                size="sm"
                className="justify-self-start"
                disabled={working}
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
          {listed.length > 0 && (
            <ul className="grid gap-2">
              {listed.map(({ model, added }) => {
                const key = `${lane.id}/${model.id}`;
                const outcome = outcomes[key];
                const removable =
                  (model.installed === true && onRemove !== undefined) ||
                  (added && readable);
                return (
                  <LocalModelRow
                    key={model.id}
                    model={model}
                    added={added}
                    locale={locale}
                    busy={working || (settingUp && model.installed !== true)}
                    progress={progressOf(model)}
                    refusal={
                      removals[key]
                        ? removalWords(t, removals[key])
                        : outcome?.kind === "refused"
                          ? listRefusalWords(t, outcome.code)
                          : null
                    }
                    onDownload={onSetUp ? () => onSetUp(model.id) : undefined}
                    onRemove={
                      removable
                        ? () => void remove(key, model, added)
                        : undefined
                    }
                  />
                );
              })}
            </ul>
          )}
          {readable && (
            <>
              <AddModel
                busy={working}
                onAdd={(model) =>
                  change("add", (revision) =>
                    host.add(lane.id, model, revision),
                  )
                }
              />
              {outcomes.add?.kind === "refused" && (
                <p role="alert" className="flex items-start gap-2 text-sm">
                  <Icon name="alert" className="mt-0.5 text-destructive" />
                  <span>{listRefusalWords(t, outcomes.add.code)}</span>
                </p>
              )}
            </>
          )}
        </>
      )}
    </section>
  );
}
