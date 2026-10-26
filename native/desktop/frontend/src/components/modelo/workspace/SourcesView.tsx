import { Button } from "@/components/ui/button";
import { Icon, type IconName } from "@/components/ui/icon";
import type {
  ModeloFormAddressV1,
  ModeloFormSourceGroup,
  ModeloFormSourceGroupKind,
  ModeloFormSourceState,
  PublicModeloFormField,
} from "../../../shell/modeloContract";
import type { OpenableSurface } from "../details/Details";
import { useStrings } from "../../../shell/strings";
import { BoxNumber } from "../form/BoxNumber";
import { addressKey } from "../form/session";
import { Heading } from "./CheckView";

const KIND_ICON: Record<ModeloFormSourceGroupKind, IconName> = {
  records: "ledger",
  registers: "office",
  profile: "person",
  earlier_declarations: "page",
  aeat_data: "shield",
  yours: "user",
  replaced: "swap",
  assumed: "pending",
  needs_you: "alert",
  calculated: "sync",
  set_by_form: "lock",
  information: "info",
  blank: "erase",
  unnamed: "unknown",
};

const STATE_MARK: Record<
  ModeloFormSourceState,
  { icon: IconName; tone: string }
> = {
  produced: { icon: "check", tone: "text-success" },
  none_found: { icon: "alert", tone: "text-warning" },
  not_yet: { icon: "clock", tone: "text-faint" },
};

/** The areas a source can be corrected in, in the order a group offers
 * them. */
const OPENABLE: OpenableSurface[] = [
  "ledger",
  "withholding",
  "profile",
  "declarations",
];

function Boxes({
  addresses,
  fieldAt,
  onGo,
}: {
  addresses: ModeloFormAddressV1[];
  fieldAt(address: ModeloFormAddressV1): PublicModeloFormField | null;
  onGo(address: ModeloFormAddressV1): void;
}) {
  const t = useStrings();
  return (
    <span className="flex flex-wrap justify-end gap-1">
      {addresses.map((address) => {
        const box = fieldAt(address)?.box ?? null;
        if (!box) return null;
        return (
          <button
            key={addressKey(address)}
            type="button"
            onClick={() => onGo(address)}
            aria-label={t("workspace.modelo.sources.go_to_box", { box })}
            className="rounded-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <BoxNumber box={box} size="sm" />
          </button>
        );
      })}
    </span>
  );
}

/**
 * Where the form's values come from, as the read model groups them: each
 * group's sources, what each gave, and the boxes it fills. A source kept in
 * another area opens there, where its value is corrected.
 */
export function SourcesView({
  groups,
  fieldAt,
  onGo,
  onOpenSurface,
  canOpenSurface,
}: {
  groups: ModeloFormSourceGroup[];
  fieldAt(address: ModeloFormAddressV1): PublicModeloFormField | null;
  onGo(address: ModeloFormAddressV1): void;
  onOpenSurface(surface: OpenableSurface): void;
  /** Whether this window can open an area; a link that cannot is not drawn. */
  canOpenSurface(surface: OpenableSurface): boolean;
}) {
  const t = useStrings();
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <Heading
        title={t("workspace.modelo.sources.title")}
        lead={t("workspace.modelo.sources.lead")}
      />
      {groups.map((group) => {
        const surfaces = OPENABLE.filter(
          (surface) =>
            canOpenSurface(surface) &&
            group.readings.some((reading) => reading.surface === surface),
        );
        return (
          <section
            key={group.kind}
            aria-label={group.name}
            className="flex flex-col gap-2 rounded-xl border border-border bg-card p-5"
          >
            <div className="flex flex-wrap items-center gap-3">
              <Icon
                name={KIND_ICON[group.kind]}
                size="md"
                className="text-muted-foreground"
              />
              <h3 className="text-md font-medium">{group.name}</h3>
              {group.summary && (
                <span className="text-sm text-muted-foreground">
                  {group.summary}
                </span>
              )}
              {surfaces.length > 0 && (
                <span className="ml-auto flex gap-3">
                  {surfaces.map((surface) => (
                    <Button
                      key={surface}
                      size="sm"
                      variant="link"
                      onClick={() => onOpenSurface(surface)}
                    >
                      {t(`workspace.modelo.surface.open.${surface}`)}
                      <Icon name="forward" size="xs" />
                    </Button>
                  ))}
                </span>
              )}
            </div>
            {group.readings.length > 0 ? (
              <ul className="flex flex-col divide-y divide-border">
                {group.readings.map((reading) => {
                  const mark = STATE_MARK[reading.state];
                  return (
                    <li
                      key={`${reading.source_kind}-${reading.words}`}
                      className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 py-2"
                    >
                      <span className="flex items-center gap-1.5 text-base">
                        <Icon
                          name={mark.icon}
                          size="xs"
                          role="img"
                          aria-label={
                            reading.state === "produced"
                              ? reading.words
                              : t(`workspace.modelo.sources.${reading.state}`, {
                                  source: reading.words,
                                })
                          }
                          className={mark.tone}
                        />
                        {reading.words}
                      </span>
                      <Boxes
                        addresses={reading.addresses}
                        fieldAt={fieldAt}
                        onGo={onGo}
                      />
                    </li>
                  );
                })}
              </ul>
            ) : (
              <Boxes
                addresses={group.addresses}
                fieldAt={fieldAt}
                onGo={onGo}
              />
            )}
          </section>
        );
      })}
    </div>
  );
}
