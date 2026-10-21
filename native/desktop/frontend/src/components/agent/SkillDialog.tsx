import { useEffect, useState, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { failureCode } from "../../errors";
import type {
  AgentSkillAppliesWhen,
  AgentSkillDetail,
  AgentSkillVerification,
  SkillCommand,
} from "../../shell/agentSkills";
import { useStrings } from "../../shell/strings";

type Answer =
  | { kind: "loading" }
  | { kind: "failed"; code: string }
  | { kind: "review"; skill: AgentSkillDetail }
  | { kind: "verify"; result: AgentSkillVerification };

const listed = (values: readonly unknown[]) =>
  values
    .map((value) => (typeof value === "string" ? value : JSON.stringify(value)))
    .join(", ");

/** When the agent applies the skill on its own, line by line, from what its
 * frontmatter says. Keys it does not know yet are not shown. */
function AppliesWhen({ rule }: { rule: AgentSkillAppliesWhen }) {
  const t = useStrings();
  const lines: ReactNode[] = [];
  if (rule.always === true) lines.push(t("desktop.agent.skill_applies_always"));
  const facts = Array.isArray(rule.profile_facts) ? rule.profile_facts : [];
  if (facts.length > 0) {
    lines.push(
      <>
        {rule.profile_match === "any"
          ? t("desktop.agent.skill_applies_profile_any")
          : t("desktop.agent.skill_applies_profile_all")}
        <ul className="mt-1 list-disc pl-5 font-mono text-sm">
          {facts.map((fact, index) => (
            <li key={index}>
              {fact.fact} {fact.match}{" "}
              {listed(Array.isArray(fact.values) ? fact.values : [])}
            </li>
          ))}
        </ul>
      </>,
    );
  }
  if (typeof rule.workflow_phase === "string" && rule.workflow_phase)
    lines.push(
      t("desktop.agent.skill_applies_phase", { phase: rule.workflow_phase }),
    );
  if (typeof rule.temporal_trigger === "string" && rule.temporal_trigger)
    lines.push(
      t("desktop.agent.skill_applies_time", {
        trigger: rule.temporal_trigger,
      }),
    );
  if (lines.length === 0) lines.push(t("desktop.agent.skill_applies_asked"));
  return (
    <ul className="grid gap-1 text-base">
      {lines.map((line, index) => (
        <li key={index}>{line}</li>
      ))}
    </ul>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="grid min-w-0 gap-1.5">
      <h3 className="text-xs font-semibold tracking-wider text-faint uppercase">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Review({
  skill,
  locale,
}: {
  skill: AgentSkillDetail;
  locale: string;
}) {
  const t = useStrings();
  const size = new Intl.NumberFormat(locale, {
    style: "unit",
    unit: "byte",
    unitDisplay: "narrow",
  });
  return (
    <>
      <Section title={t("desktop.agent.skill_applies_when")}>
        <AppliesWhen rule={skill.applies_when} />
      </Section>
      <Section title={t("desktop.agent.skill_files")}>
        <ul className="grid gap-0.5 font-mono text-sm">
          {skill.files.map((file) => (
            <li key={file.path} className="flex min-w-0 gap-3">
              <span className="min-w-0 flex-1 truncate">{file.path}</span>
              <span className="shrink-0 text-muted-foreground">
                {size.format(file.bytes)}
              </span>
            </li>
          ))}
        </ul>
      </Section>
      <Section title="SKILL.md">
        <pre
          tabIndex={0}
          aria-label="SKILL.md"
          className="max-h-96 overflow-auto rounded-md border bg-muted p-3 font-mono text-sm whitespace-pre-wrap"
        >
          {skill.content}
        </pre>
      </Section>
    </>
  );
}

function Verification({ result }: { result: AgentSkillVerification }) {
  const t = useStrings();
  return (
    <>
      <p role="status" className="text-base font-medium">
        {result.valid
          ? result.findings.length === 0
            ? t("desktop.agent.skill_verify_clean")
            : t("desktop.agent.skill_verify_warned")
          : t("desktop.agent.skill_verify_failed")}
      </p>
      {result.findings.length > 0 && (
        <ul
          aria-label={t("desktop.agent.skill_findings")}
          className="grid gap-2"
        >
          {result.findings.map((finding, index) => (
            <li key={index} className="grid gap-0.5 rounded-md border p-2.5">
              <span className="flex flex-wrap items-center gap-2">
                <Badge
                  variant={finding.severity === "error" ? "danger" : "warning"}
                >
                  {finding.severity === "error"
                    ? t("desktop.agent.skill_finding_error")
                    : t("desktop.agent.skill_finding_warning")}
                </Badge>
                <code className="text-sm">{finding.code}</code>
                {finding.path && (
                  <span className="font-mono text-sm text-muted-foreground">
                    {finding.path}
                  </span>
                )}
              </span>
              <span className="text-base">{finding.message}</span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

/**
 * A skill command's answer: the skill in full for a review, or the agent's
 * checks of it for a verification. It reads its answer when it opens.
 */
export function SkillDialog({
  command,
  locale,
  review,
  verify,
  onClose,
}: {
  command: SkillCommand;
  locale: string;
  review?: (name: string) => Promise<AgentSkillDetail>;
  verify?: (name: string) => Promise<AgentSkillVerification>;
  onClose: () => void;
}) {
  const t = useStrings();
  const [read, setRead] = useState<Answer>({ kind: "loading" });
  // Where the command was written: the focus goes back there on close, as
  // the dialog opened from a key in it rather than from a button.
  const [opener] = useState(() =>
    document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null,
  );
  const { kind, name } = command;
  useEffect(() => {
    let current = true;
    setRead({ kind: "loading" });
    const asked: Promise<Answer> | undefined =
      kind === "review"
        ? review?.(name).then((skill) => ({ kind: "review", skill }))
        : verify?.(name).then((result) => ({ kind: "verify", result }));
    if (!asked) {
      setRead({ kind: "failed", code: "agent_skills_unavailable" });
      return;
    }
    asked.then(
      (answer) => {
        if (current) setRead(answer);
      },
      (error: unknown) => {
        if (current) setRead({ kind: "failed", code: failureCode(error) });
      },
    );
    return () => {
      current = false;
    };
  }, [kind, name, review, verify]);

  const description =
    read.kind === "review" ? read.skill.description : undefined;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        closeLabel={t("desktop.agent.skill_close")}
        onCloseAutoFocus={(event) => {
          if (!opener?.isConnected) return;
          event.preventDefault();
          opener.focus();
        }}
        placement="top"
        data-slot="skill-dialog"
        className="w-palette overflow-y-auto"
      >
        <DialogHeader>
          <DialogTitle className="font-mono">
            {kind === "review"
              ? t("desktop.agent.skill_review_title", { name })
              : t("desktop.agent.skill_verify_title", { name })}
          </DialogTitle>
          <DialogDescription>
            {description ??
              (kind === "review"
                ? t("desktop.agent.skill_command_review")
                : t("desktop.agent.skill_command_verify"))}
          </DialogDescription>
        </DialogHeader>
        {read.kind === "loading" && (
          <p className="flex items-center gap-2 text-base text-faint">
            <Spinner />
            {t("desktop.agent.skill_loading")}
          </p>
        )}
        {read.kind === "failed" && (
          <p role="alert" className="text-base">
            {read.code === "agent_gateway_skill_not_found"
              ? t("desktop.agent.skill_not_found", { name })
              : t("desktop.agent.skill_failed")}
          </p>
        )}
        {read.kind === "review" && (
          <Review skill={read.skill} locale={locale} />
        )}
        {read.kind === "verify" && <Verification result={read.result} />}
      </DialogContent>
    </Dialog>
  );
}
