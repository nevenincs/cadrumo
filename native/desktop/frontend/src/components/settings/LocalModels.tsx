import { useId, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Icon } from "@/components/ui/icon";
import {
  capabilityWords,
  localModelOrder,
  roleRefusalWords,
  rolesOf,
  roleWords,
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

/** One model of the lane: what it is, whether this computer holds it, the
 * roles that use it, and the choice of roles that downloads it. */
function LocalModelRow({
  model,
  recommended,
  roles,
  usedBy,
  locale,
  busy,
  refusal,
  removal,
  onUse,
  onRemove,
}: {
  model: RoleModel;
  recommended: AgentRecommendedCapability[];
  roles: string[];
  usedBy: string[];
  locale: string;
  busy: boolean;
  refusal: string | null;
  /** Why the last removal of this model was refused, if it was. */
  removal: string | null;
  onUse: (roles: string[]) => void;
  /** Removes the model from this computer; absent while nothing can. */
  onRemove?: () => void;
}) {
  const t = useStrings();
  const headingId = useId();
  const [picking, setPicking] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const missing = model.installed === false;
  const open = () => {
    setPicked(usedBy);
    setPicking(true);
  };
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
          <Badge variant={missing ? "neutral" : "success"}>
            {missing
              ? t("desktop.providers.local_model_absent")
              : t("desktop.providers.local_model_installed")}
          </Badge>
        )}
      </div>
      <ModelFacts model={model} locale={locale} />
      <p className="text-sm text-muted-foreground">
        {usedBy.length > 0
          ? t("desktop.providers.local_model_used_by", {
              roles: usedBy.map((role) => roleWords(t, role)).join(", "),
            })
          : t("desktop.providers.local_model_unused")}
      </p>
      {picking ? (
        <fieldset className="grid gap-1.5" disabled={busy}>
          <legend className="text-sm text-foreground">
            {t("desktop.providers.local_model_pick_roles")}
          </legend>
          {roles.map((role) => (
            <label key={role} className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={picked.includes(role)}
                onChange={(event) => {
                  const on = event.currentTarget.checked;
                  setPicked((held) =>
                    on
                      ? [...held, role]
                      : held.filter((named) => named !== role),
                  );
                }}
              />
              {roleWords(t, role)}
            </label>
          ))}
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={busy || picked.length === 0}
              onClick={() => {
                onUse(picked);
                setPicking(false);
              }}
            >
              {missing
                ? t("desktop.providers.local_model_download")
                : t("desktop.providers.local_model_use")}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setPicking(false)}>
              {t("desktop.providers.cancel")}
            </Button>
          </div>
        </fieldset>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={busy || roles.length === 0}
            onClick={open}
          >
            {missing
              ? t("desktop.providers.local_model_download")
              : t("desktop.providers.local_model_choose_roles")}
          </Button>
          {model.installed === true && onRemove && (
            <Button
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={onRemove}
            >
              {t("desktop.providers.local_model_remove")}
            </Button>
          )}
        </div>
      )}
      {refusal && (
        <p role="alert" className="flex items-start gap-2 text-sm">
          <Icon name="alert" className="mt-0.5 text-destructive" />
          <span>{roleRefusalWords(t, refusal)}</span>
        </p>
      )}
      {removal && (
        <p role="alert" className="flex items-start gap-2 text-sm">
          <Icon name="alert" className="mt-0.5 text-destructive" />
          <span>{removalWords(t, removal)}</span>
        </p>
      )}
    </li>
  );
}

/**
 * The models a lane on this computer runs: what cadrumo-agent recommends
 * first, each with what it is and whether it is here. Downloading a model is
 * choosing the roles it reads for and then approving setup's plan, so a model
 * is pulled only once it is selected and only as the person approved.
 */
export function LocalModels({
  lane,
  host,
  locale,
  onSetUp,
  onRemove,
}: {
  lane: RoleLane | null;
  host: ModelRoleHost;
  locale: string;
  /** Opens setup's review of the local AI; absent where this window offers
   * no setup. */
  onSetUp?: () => void;
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
  const roles = selected.map((selection) => selection.role);
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
          {t("desktop.agent.model_roles_loading")}
        </p>
      ) : !readable ? (
        <p role="alert" className="text-sm">
          {snapshot.kind === "ready"
            ? t("desktop.agent.model_roles_unreadable")
            : t("desktop.agent.model_roles_failed")}
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
                roles={roles}
                usedBy={usedBy}
                locale={locale}
                busy={busy !== null || removing !== null}
                refusal={outcome?.kind === "refused" ? outcome.code : null}
                removal={removals[key] ?? null}
                onRemove={
                  onRemove
                    ? () => void remove(key, model.id, usedBy)
                    : undefined
                }
                onUse={(picked) =>
                  void change(
                    key,
                    picked.map((role) => ({
                      role,
                      act: (revision: string) =>
                        selections.set(role, lane.id, model.id, revision),
                    })),
                  ).then((stored) => {
                    if (stored && model.installed !== true) onSetUp?.();
                  })
                }
              />
            );
          })}
        </ul>
      )}
    </section>
  );
}
