import type { ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import type { AboutComponent, AboutInfo, AboutNamed } from "../ipc/contract";
import { aboutReport, versionLine, type AboutState } from "../shell/about";
import { useStrings, type Translate } from "../shell/strings";

/** One labelled fact; a fact the package did not state says so. */
function Fact({ label, value }: { label: string; value: string | null }) {
  const t = useStrings();
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)] gap-x-3 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd
        className={
          value === null
            ? "min-w-0 text-muted-foreground"
            : "min-w-0 break-words text-foreground"
        }
      >
        {value ?? t("desktop.about.unavailable")}
      </dd>
    </div>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="grid gap-2" aria-labelledby={id}>
      <h3 id={id} className="text-sm font-medium text-foreground">
        {title}
      </h3>
      <dl className="grid gap-1">{children}</dl>
    </section>
  );
}

/** A long list, closed until opened, that scrolls inside the dialog. */
function Listing({
  id,
  title,
  items,
}: {
  id: string;
  title: string;
  items: AboutNamed[];
}) {
  return (
    <details data-about-list={id} className="group/details grid gap-2">
      <summary className="flex w-fit cursor-pointer list-none items-center gap-1 rounded-md text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
        <Icon
          name="forward"
          className="transition-transform group-open/details:rotate-90"
        />
        {title}
      </summary>
      <ul className="grid max-h-60 gap-0.5 overflow-y-auto rounded-md border p-2 text-sm">
        {items.map((item) => (
          <li
            key={item.name}
            className="grid grid-cols-[minmax(0,1fr)_auto] gap-3"
          >
            <span className="min-w-0 break-words">{item.name}</span>
            <span className="text-muted-foreground">{item.version}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

/** A component's version, with its build and build type where stated. */
function componentText(t: Translate, c: AboutComponent): string | null {
  if (c.version === null && c.build_id === null) return null;
  return [c.version ?? t("desktop.about.unavailable"), c.build_id, c.build_type]
    .filter((part) => part !== null)
    .join(" ");
}

export function buildTypeText(
  t: Translate,
  type: string | null,
): string | null {
  if (type === "debug") return t("desktop.about.build_type_debug");
  if (type === "release") return t("desktop.about.build_type_release");
  return type;
}

function Details({ info }: { info: AboutInfo }) {
  const t = useStrings();
  const byRole = (role: string) =>
    info.components.filter((component) => component.role === role);
  const desktop = [
    info.desktop.version ?? t("desktop.about.unavailable"),
    info.desktop.build_id,
    buildTypeText(t, info.desktop.build_type),
  ]
    .filter((part) => part !== null)
    .join(" ");
  return (
    <div className="grid gap-4">
      <Section id="about-application" title={t("desktop.about.application")}>
        <Fact label={t("desktop.about.version")} value={info.version} />
      </Section>
      <Section id="about-runtime" title={t("desktop.about.runtime")}>
        <Fact label={t("desktop.about.python")} value={info.python} />
        {byRole("interpreter").map((component) => (
          <Fact
            key={component.path ?? component.name}
            label={t("desktop.about.interpreter")}
            value={componentText(t, component)}
          />
        ))}
      </Section>
      <Section id="about-managers" title={t("desktop.about.managers")}>
        {byRole("manager").map((component) => (
          <Fact
            key={component.path ?? component.name}
            label={component.name ?? t("desktop.about.manager")}
            value={componentText(t, component)}
          />
        ))}
        <Fact label={t("desktop.about.desktop_host")} value={desktop} />
      </Section>
      {info.agent && (
        <Section id="about-agent" title={t("desktop.about.agent")}>
          <Fact
            label={t("desktop.about.agent_version")}
            value={info.agent.version}
          />
          {info.agent.dependencies.length > 0 && (
            <Listing
              id="dependencies"
              title={t("desktop.about.dependencies", {
                count: info.agent.dependencies.length,
              })}
              items={info.agent.dependencies}
            />
          )}
        </Section>
      )}
      {info.distributions.length > 0 && (
        <section className="grid gap-2">
          <Listing
            id="distributions"
            title={t("desktop.about.packages", {
              count: info.distributions.length,
            })}
            items={info.distributions}
          />
        </section>
      )}
      {Object.keys(info.tools).length > 0 && (
        <Section id="about-tools" title={t("desktop.about.tools")}>
          {Object.entries(info.tools).map(([name, version]) => (
            <Fact key={name} label={name} value={version} />
          ))}
        </Section>
      )}
    </div>
  );
}

/** The installation's name, version, build and parts, with a plain-text
 * report the person can copy for a support request. */
export function AboutDialog({
  open,
  onOpenChange,
  state,
  onCopy,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  state: AboutState | null;
  onCopy: (text: string) => void;
}) {
  const t = useStrings();
  const info = state?.status === "ready" ? state.info : null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="about grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden"
        closeLabel={t("desktop.about.close")}
      >
        <DialogHeader>
          <DialogTitle>{t("desktop.about.title")}</DialogTitle>
          <DialogDescription className="sr-only">
            {t("desktop.about.description")}
          </DialogDescription>
          {info && (
            <div className="grid gap-2">
              <p
                data-about-version
                className="flex flex-wrap items-center gap-2 text-base text-foreground"
              >
                <span>
                  {info.product ?? "Cadrumo"}{" "}
                  {versionLine(info) ?? t("desktop.about.unavailable")}
                </span>
                {info.build_type === "debug" && (
                  <Badge variant="warning">
                    {t("desktop.about.debug_badge")}
                  </Badge>
                )}
              </p>
              <dl className="grid gap-1">
                <Fact
                  label={t("desktop.about.build_id")}
                  value={info.build_id}
                />
                <Fact
                  label={t("desktop.about.build_type")}
                  value={buildTypeText(t, info.build_type)}
                />
                <Fact
                  label={t("desktop.about.build_date")}
                  value={info.build_date}
                />
                <Fact label={t("desktop.about.channel")} value={info.channel} />
                <Fact label={t("desktop.about.target")} value={info.target} />
              </dl>
            </div>
          )}
        </DialogHeader>
        <div className="min-h-0 overflow-y-auto pr-1">
          {state?.status === "ready" && <Details info={state.info} />}
          {state?.status === "loading" && (
            <p role="status" className="text-sm text-muted-foreground">
              {t("desktop.about.loading")}
            </p>
          )}
          {state?.status === "failed" && (
            <Alert tone="danger" role="alert" icon={<Icon name="alert" />}>
              {t("desktop.about.load_failed", { code: state.code })}
            </Alert>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            size="sm"
            disabled={!info}
            onClick={() => info && onCopy(aboutReport(t, info))}
          >
            <Icon name="copy" />
            {t("desktop.about.copy")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
