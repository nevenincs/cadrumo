import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { NativeSelect } from "@/components/ui/native-select";
import { Spinner } from "@/components/ui/spinner";
import type { AgentModelRoleSelection } from "../../ipc/contract";
import {
  capabilityWords,
  laneWords,
  roleLanes,
  roleRefusalWords,
  roleWords,
  sizeWords,
  type RoleLane,
  type RoleModel,
} from "../../shell/agentModelRoles";
import type {
  AgentCatalogAnswer,
  AgentModelLicenceFacts,
} from "../../shell/agentSession";
import {
  useModelRoles,
  type ModelRoleHost,
  type RoleChange,
  type RoleOutcome,
} from "../../shell/modelRoles";
import { useStrings } from "../../shell/strings";

type Draft = { lane: string; model: string };

type LicenceText =
  | { kind: "loading" }
  | { kind: "shown"; text: string }
  | { kind: "unavailable" };

const licenceWords = (licence: AgentModelLicenceFacts) =>
  licence.spdx && licence.spdx !== licence.name
    ? `${licence.name} (${licence.spdx})`
    : licence.name;

/** What the catalog states of one model: its licence, whether it reads
 * images, and its download size, each said even where it is not known. */
export function ModelFacts({
  model,
  locale,
}: {
  model: RoleModel;
  locale: string;
}) {
  const t = useStrings();
  return (
    <ul data-slot="model-facts" className="grid gap-0.5 text-sm">
      <li data-fact="licence">
        {model.licence
          ? t("desktop.agent.model_role_licence", {
              licence: licenceWords(model.licence),
            })
          : t("desktop.agent.model_role_licence_unknown")}
      </li>
      <li data-fact="vision">
        {model.vision === true
          ? t("desktop.agent.model_role_vision_yes")
          : model.vision === false
            ? t("desktop.agent.model_role_vision_no")
            : t("desktop.agent.model_role_vision_unknown")}
      </li>
      {model.sizeBytes !== null && (
        <li data-fact="size">
          {t("desktop.agent.model_role_size", {
            size: sizeWords(locale, model.sizeBytes),
          })}
        </li>
      )}
    </ul>
  );
}

/** One role: what is chosen for it, and the lane and model the person may
 * choose, save or clear. Nothing is chosen for the person: choosing a lane
 * leaves the model unchosen, and the agent's recommendation is a button. */
function RoleRow({
  selection,
  lanes,
  locale,
  busy,
  outcome,
  licence,
  onSave,
  onClear,
}: {
  selection: AgentModelRoleSelection;
  lanes: readonly RoleLane[];
  locale: string;
  busy: boolean;
  outcome: RoleOutcome | undefined;
  licence?: ModelRoleHost["licence"];
  onSave: (lane: string, model: string) => void;
  onClear: () => void;
}) {
  const t = useStrings();
  const laneId = useId();
  const modelId = useId();
  const headingId = useId();
  const [draft, setDraft] = useState<Draft>({
    lane: selection.lane ?? "",
    model: selection.model ?? "",
  });
  const [text, setText] = useState<LicenceText | null>(null);
  // A selection read again (after a save elsewhere, or a conflict) is what
  // the row starts from.
  const [held, setHeld] = useState(selection);
  if (held.lane !== selection.lane || held.model !== selection.model) {
    setHeld(selection);
    setDraft({ lane: selection.lane ?? "", model: selection.model ?? "" });
    setText(null);
  }
  const role = roleWords(t, selection.role);
  // A stored choice the catalog no longer lists is still shown as stored.
  const listed = lanes.map((one) => ({ id: one.id, words: laneWords(t, one) }));
  const offered =
    selection.lane && !lanes.some((one) => one.id === selection.lane)
      ? [...listed, { id: selection.lane, words: selection.lane }]
      : listed;
  const lane = lanes.find((one) => one.id === draft.lane);
  const model = lane?.models.find((one) => one.id === draft.model);
  const storedLane = lanes.find((one) => one.id === selection.lane);
  const storedModel = storedLane?.models.find(
    (one) => one.id === selection.model,
  );
  const changed =
    draft.lane !== (selection.lane ?? "") ||
    draft.model !== (selection.model ?? "");
  const choose = (next: Draft) => {
    setDraft(next);
    setText(null);
  };
  const showLicence = () => {
    if (!licence || !lane || !model) return;
    setText({ kind: "loading" });
    licence(lane.provider, lane.transport, model.id).then(
      (answer) => setText({ kind: "shown", text: answer.text }),
      () => setText({ kind: "unavailable" }),
    );
  };

  return (
    <section
      data-role={selection.role}
      aria-labelledby={headingId}
      className="grid gap-2 rounded-lg bg-accent p-3"
    >
      <h3 id={headingId} className="font-medium text-foreground">
        {t("desktop.agent.model_role_heading", { role })}
      </h3>
      <p data-slot="role-current" className="text-sm text-muted-foreground">
        {selection.lane && selection.model
          ? t("desktop.agent.model_role_current", {
              model: storedModel?.name ?? selection.model,
              lane: storedLane ? laneWords(t, storedLane) : selection.lane,
            })
          : t("desktop.agent.model_role_none")}
      </p>
      <Field>
        <FieldLabel htmlFor={laneId}>
          {t("desktop.agent.model_role_lane", { role })}
        </FieldLabel>
        <NativeSelect
          id={laneId}
          controlSize="sm"
          value={draft.lane}
          disabled={busy}
          onChange={(event) => choose({ lane: event.target.value, model: "" })}
        >
          <option value="">{t("desktop.agent.model_role_choose_lane")}</option>
          {offered.map((one) => (
            <option key={one.id} value={one.id}>
              {one.words}
            </option>
          ))}
        </NativeSelect>
      </Field>
      {lane && (
        <Field>
          <FieldLabel htmlFor={modelId}>
            {t("desktop.agent.model_role_model", { role })}
          </FieldLabel>
          <NativeSelect
            id={modelId}
            controlSize="sm"
            value={draft.model}
            disabled={busy}
            onChange={(event) =>
              choose({ lane: draft.lane, model: event.target.value })
            }
          >
            <option value="">
              {t("desktop.agent.model_role_choose_model")}
            </option>
            {lane.models.map((one) => (
              <option key={one.id} value={one.id}>
                {one.name}
              </option>
            ))}
            {draft.model !== "" &&
              !lane.models.some((one) => one.id === draft.model) && (
                <option value={draft.model}>{draft.model}</option>
              )}
          </NativeSelect>
          {lane.recommended.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {lane.recommended.map((offer) => (
                <Button
                  key={offer.capability}
                  type="button"
                  variant="outline"
                  size="xs"
                  data-recommended={offer.capability}
                  disabled={busy || draft.model === offer.model}
                  onClick={() =>
                    choose({ lane: draft.lane, model: offer.model })
                  }
                >
                  {t("desktop.agent.model_role_recommended", {
                    capability: capabilityWords(t, offer.capability),
                    model:
                      lane.models.find((one) => one.id === offer.model)?.name ??
                      offer.model,
                  })}
                </Button>
              ))}
            </div>
          )}
        </Field>
      )}
      {model && (
        <>
          <ModelFacts model={model} locale={locale} />
          {licence && model.licence && (
            <div className="grid gap-1">
              <Button
                type="button"
                variant="link"
                size="xs"
                className="justify-self-start"
                onClick={showLicence}
                disabled={text?.kind === "loading"}
              >
                {t("desktop.agent.model_role_licence_show")}
              </Button>
              {text?.kind === "shown" && (
                <pre
                  tabIndex={0}
                  aria-label={licenceWords(model.licence)}
                  className="max-h-48 overflow-auto rounded-md bg-card p-2 font-mono text-sm whitespace-pre-wrap"
                >
                  {text.text}
                </pre>
              )}
              {text?.kind === "unavailable" && (
                <FieldDescription>
                  {t("desktop.agent.model_role_licence_unavailable")}
                </FieldDescription>
              )}
            </div>
          )}
        </>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          disabled={busy || !lane || !model || !changed}
          onClick={() => onSave(draft.lane, draft.model)}
        >
          {t("desktop.agent.model_role_save")}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy || selection.lane === null}
          onClick={onClear}
        >
          {t("desktop.agent.model_role_clear")}
        </Button>
        {busy && <Spinner />}
        {outcome?.kind === "saved" && (
          <span role="status" className="text-sm text-muted-foreground">
            {t("desktop.agent.model_role_saved")}
          </span>
        )}
      </div>
      {outcome?.kind === "refused" && (
        <p role="alert" className="text-sm text-foreground">
          {roleRefusalWords(t, outcome.code)}
        </p>
      )}
    </section>
  );
}

/**
 * The person's model for each role that reads their documents, chosen from
 * the agent's catalog. Every role the service names is listed, chosen or
 * not; a role may be cleared, and nothing is ever chosen for the person.
 */
export function ModelRolesDialog({
  host,
  catalog,
  locale,
  onClose,
}: {
  host: ModelRoleHost;
  /** The catalog the column read last, served or declared; null while unread. */
  catalog: AgentCatalogAnswer | null;
  locale: string;
  onClose: () => void;
}) {
  const t = useStrings();
  const { snapshot, busy, outcomes, change: changeRoles } = useModelRoles(host);
  const lanes = catalog ? roleLanes(catalog) : [];
  const change = (role: string, act: RoleChange["act"]) =>
    void changeRoles(role, [{ role, act }]);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        closeLabel={t("desktop.agent.model_roles_close")}
        placement="top"
        data-slot="model-roles-dialog"
        className="w-palette overflow-y-auto"
      >
        <DialogHeader>
          <DialogTitle>{t("desktop.agent.model_roles_title")}</DialogTitle>
          <DialogDescription>
            {t("desktop.agent.model_roles_lead")}
          </DialogDescription>
        </DialogHeader>
        {snapshot.kind === "loading" && (
          <p className="flex items-center gap-2 text-base text-faint">
            <Spinner />
            {t("desktop.agent.model_roles_loading")}
          </p>
        )}
        {snapshot.kind === "failed" && (
          <p role="alert" className="text-base">
            {t("desktop.agent.model_roles_failed")}
          </p>
        )}
        {snapshot.kind === "ready" && snapshot.value.state === "unreadable" && (
          <p role="alert" className="text-base">
            {t("desktop.agent.model_roles_unreadable")}
          </p>
        )}
        {snapshot.kind === "ready" && snapshot.value.state === "readable" && (
          <>
            {lanes.length === 0 && (
              <p className="text-base text-muted-foreground">
                {t("desktop.agent.model_roles_no_lanes")}
              </p>
            )}
            <div className="grid gap-3">
              {snapshot.value.roles.map((selection) => (
                <RoleRow
                  key={selection.role}
                  selection={selection}
                  lanes={lanes}
                  locale={locale}
                  busy={busy === selection.role}
                  outcome={outcomes[selection.role]}
                  licence={host.licence}
                  onSave={(lane, model) =>
                    change(selection.role, (revision) =>
                      host.set(selection.role, lane, model, revision),
                    )
                  }
                  onClear={() =>
                    change(selection.role, (revision) =>
                      host.clear(selection.role, revision),
                    )
                  }
                />
              ))}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
