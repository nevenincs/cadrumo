import { useEffect, useState } from "react";
import type { AboutInfo } from "../ipc/contract";
import { failureCode } from "../errors";
import type { Host } from "./host";
import type { Translate } from "./strings";

/** What the shell knows of this installation: not asked for yet, read, or
 * refused with the host's typed code. */
export type AboutState =
  | { status: "loading" }
  | { status: "ready"; info: AboutInfo }
  | { status: "failed"; code: string };

/** Reads the installation's About facts once. Null when the host offers none. */
export function useAbout(host: Host): AboutState | null {
  const [state, setState] = useState<AboutState>({ status: "loading" });
  const offered = host.about !== undefined;
  useEffect(() => {
    if (!host.about) return;
    let current = true;
    host.about().then(
      (info) => current && setState({ status: "ready", info }),
      (error: unknown) =>
        current && setState({ status: "failed", code: failureCode(error) }),
    );
    return () => {
      current = false;
    };
  }, [host]);
  return offered ? state : null;
}

/** The version the product states for itself, with the build type marked on a
 * debug build; absent facts are not replaced by guesses. */
export function versionLine(info: AboutInfo): string | null {
  return info.display_version ?? info.version;
}

function field(t: Translate, value: string | null): string {
  return value ?? t("desktop.about.unavailable");
}

/** The plain-text report the Copy button puts on the clipboard. */
export function aboutReport(t: Translate, info: AboutInfo): string {
  const row = (label: string, value: string | null) =>
    `${t(label)}: ${field(t, value)}`;
  const lines = [
    `${field(t, info.product)} ${field(t, versionLine(info))}`,
    row("desktop.about.build_id", info.build_id),
    row("desktop.about.build_type", info.build_type),
    row("desktop.about.build_date", info.build_date),
    row("desktop.about.channel", info.channel),
    row("desktop.about.target", info.target),
    "",
    `[${t("desktop.about.application")}]`,
    row("desktop.about.version", info.version),
    "",
    `[${t("desktop.about.runtime")}]`,
    row("desktop.about.python", info.python),
  ];
  const components = info.components.filter(
    (component) => component.role !== "desktop",
  );
  const describe = (c: AboutInfo["components"][number]) =>
    [
      field(t, c.name),
      field(t, c.version),
      c.build_id,
      c.build_type,
    ]
      .filter((part) => part !== null)
      .join(" ");
  for (const c of components.filter((c) => c.role === "interpreter"))
    lines.push(`${t("desktop.about.interpreter")}: ${describe(c)}`);
  lines.push("", `[${t("desktop.about.managers")}]`);
  for (const c of components.filter((c) => c.role === "manager"))
    lines.push(`${t("desktop.about.manager")}: ${describe(c)}`);
  lines.push(
    `${t("desktop.about.desktop_host")}: ${[
      field(t, info.desktop.version),
      info.desktop.build_id,
      info.desktop.build_type,
    ]
      .filter((part) => part !== null)
      .join(" ")}`,
  );
  if (info.agent) {
    lines.push(
      "",
      `[${t("desktop.about.agent")}]`,
      row("desktop.about.agent_version", info.agent.version),
    );
    if (info.agent.dependencies.length > 0)
      lines.push(
        `${t("desktop.about.dependencies", { count: info.agent.dependencies.length })}:`,
        ...info.agent.dependencies.map((d) => `  ${d.name} ${d.version}`),
      );
  }
  const tools = Object.entries(info.tools);
  if (tools.length > 0)
    lines.push(
      "",
      `[${t("desktop.about.tools")}]`,
      ...tools.map(([name, version]) => `${name}: ${version}`),
    );
  if (info.distributions.length > 0)
    lines.push(
      "",
      `[${t("desktop.about.packages", { count: info.distributions.length })}]`,
      ...info.distributions.map((d) => `  ${d.name} ${d.version}`),
    );
  return lines.join("\n");
}
