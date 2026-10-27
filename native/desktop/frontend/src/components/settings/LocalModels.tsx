import { useId, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  capabilityWords,
  localModelOrder,
  roleRefusalWords,
  rolesOf,
  type RoleLane,
  type RoleModel,
} from "../../shell/agentModelRoles";
import type { AgentRecommendedCapability } from "../../shell/agentSession";
import { useModelRoles, type ModelRoleHost } from "../../shell/modelRoles";
import { useStrings, type Translate } from "../../shell/strings";
import { ModelFacts } from "../agent/ModelRolesDialog";
import { refusalWords } from "../setup/setupWords";

/** Why a model was not removed, in words. */
function removalWords(t: Translate, code: string): string {
  switch (code) {
    case "model_still_selected":
      return t("desktop.providers.local_model_remove_still_selected");
    case "model_not_removed":
      return t("desktop.providers.local_model_remove_failed");
    default:
      return refusalWords(t, code);
  }
}

/** A catalogue model and its download or removal action. */
function LocalModelRow({
  model,
  recommended,
  locale,
  busy,
  refusal,
  onDownload,
  onRemove,
}: {
  model: RoleModel;
  recommended: AgentRecommendedCapability[];
  locale: string;
  busy: boolean;
  refusal: string | null;
  onDownload?: () => void;
  onRemove?: () => void;
}) {
  const t = useStrings();
  const headingId = useId();
  return (
    <li
      data-model={model.id}
      data-recommended={recommended.join(" ") || undefined}
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
        {recommended.map((capability) => (
          <Badge key={capability} variant="inverse">
            {t("desktop.providers.local_model_recommended", {
              capability: capabilityWords(t, capability),
            })}
          </Badge>
        ))}
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
        {model.installed === true && onRemove && (
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

/** Local model downloads; document-task configuration opens separately. */
export function LocalModels({
  lane,
  host,
  locale,
  onSetUp,
  onRemove,
  onConfigure,
}: {
  lane: RoleLane | null;
  host: ModelRoleHost;
  locale: string;
  /** Opens setup's review of the local AI; absent where this window offers
   * no setup. */
  onSetUp?: (model: string) => void;
  onConfigure: () => void;
  /** Removes one model no role selects, answering the refusal's code or
   * null; absent where this window offers no setup. */
  onRemove?: (model: string) => Promise<string | null>;
}) {
  const t = useStrings();
  const selections = useModelRoles(host);
  const { snapshot, busy, outcomes, change } = selections;
  const [removing, setRemoving] = useState<string | null>(null);
  const [removals, setRemovals] = useState<Record<string, string>>({});
  // The roles that use a model are cleared first, so setup does not pull it
  // again; the model is removed only once none does.
  const remove = async (key: string, model: string, usedBy: string[]) => {
    if (!onRemove) return;
    setRemoving(key);
    setRemovals((held) => {
      const next = { ...held };
      delete next[key];
      return next;
    });
    try {
      const cleared = await change(
        key,
        usedBy.map((role) => ({
          role,
          act: (revision: string) => selections.clear(role, revision),
        })),
      );
      if (!cleared) return;
      const code = await onRemove(model);
      if (code) setRemovals((held) => ({ ...held, [key]: code }));
    } finally {
      setRemoving(null);
    }
  };
  const readable =
    snapshot.kind === "ready" && snapshot.value.state === "readable";
  const selected = readable ? rolesOf(snapshot.value) : [];
  return (
    <section data-slot="local-models" className="grid gap-2 pt-1">
      <h6 className="text-sm font-medium text-foreground">
        {t("desktop.providers.local_models_title")}
      </h6>
      <p className="text-sm text-muted-foreground">
        {t("desktop.providers.local_models_lead")}
      </p>
      <Button variant="outline" size="sm" onClick={onConfigure}>
        {t("desktop.agent.model_roles_title")}
      </Button>
      {!lane ? (
        <p className="text-sm text-muted-foreground">
          {t("desktop.providers.local_models_none")}
        </p>
      ) : (
        <ul className="grid gap-2">
          {localModelOrder(lane).map(({ model, recommended }) => {
            const key = `${lane.id}/${model.id}`;
            const outcome = outcomes[key];
            const usedBy = selected
              .filter(
                (selection) =>
                  selection.lane === lane.id && selection.model === model.id,
              )
              .map((selection) => selection.role);
            return (
              <LocalModelRow
                key={model.id}
                model={model}
                recommended={recommended}
                locale={locale}
                busy={busy !== null || removing !== null}
                refusal={
                  outcome?.kind === "refused"
                    ? roleRefusalWords(t, outcome.code)
                    : removals[key]
                      ? removalWords(t, removals[key])
                      : null
                }
                onDownload={onSetUp ? () => onSetUp(model.id) : undefined}
                onRemove={
                  onRemove && readable
                    ? () => void remove(key, model.id, usedBy)
                    : undefined
                }
              />
            );
          })}
        </ul>
      )}
    </section>
  );
}
