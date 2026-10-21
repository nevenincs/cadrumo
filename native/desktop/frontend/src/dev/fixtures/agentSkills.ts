import type {
  AgentSkillDetail,
  AgentSkillSummary,
  AgentSkillVerification,
} from "../../shell/agentSkills";

// Made-up skills shaped as cadrumo-agent serves its own: names, words and
// digests are the fixture's, never the bundled skills'.

/** How the scenario host serves skills: a handful, hundreds for scrolling,
 * a read that fails, or none at all. */
export type FixtureSkills = "bundled" | "many" | "failed" | "unavailable";

const digestOf = (seed: string) => {
  let hash = 0;
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return hash.toString(16).padStart(8, "0").repeat(8);
};

const skill = (
  name: string,
  description: string,
  applies_when: AgentSkillSummary["applies_when"],
  extra: string[] = [],
): AgentSkillSummary => ({
  name,
  description,
  applies_when,
  digest: digestOf(name),
  files: ["SKILL.md", ...extra].map((path) => ({
    path,
    bytes: 900 + path.length * 37,
    digest: digestOf(`${name}/${path}`),
  })),
});

/** Sorted by name, as the agent lists them. */
export const FIXTURE_SKILLS: readonly AgentSkillSummary[] = [
  skill(
    "cadrumo-iva-trimestral",
    "Prepara la autoliquidación trimestral del IVA a partir del libro registro.",
    {
      profile_facts: [
        {
          fact: "regimen_iva",
          match: "in",
          values: ["general", "simplificado"],
        },
      ],
      profile_match: "all",
      temporal_trigger: "quarter_close",
    },
    ["references/casillas.md"],
  ),
  skill(
    "cadrumo-renta-anual",
    "Revisa el borrador de la renta y lo cuadra con los datos del perfil.",
    { workflow_phase: "annual_review" },
  ),
  skill(
    "cadrumo-retenciones",
    "Comprueba las retenciones practicadas y soportadas del periodo.",
    {
      profile_facts: [
        { fact: "actividad", match: "equals", values: ["profesional"] },
        { fact: "empleados", match: "gt", values: [0] },
      ],
      profile_match: "any",
    },
  ),
  skill(
    "cadrumo-facturas",
    "Lee facturas recibidas y propone su asiento en el libro.",
    { always: true },
    ["references/campos.md", "examples/factura.json"],
  ),
  skill(
    "cadrumo-calendario",
    "Explica los plazos de presentación que se acercan.",
    { always: true },
  ),
  skill(
    "cadrumo-revision-fuentes",
    "Contrasta una cifra con su fuente oficial antes de usarla.",
    {},
  ),
].sort((a, b) => (a.name < b.name ? -1 : 1));

/** Hundreds of skills, for a list that must scroll and never cap. */
export const MANY_FIXTURE_SKILLS: readonly AgentSkillSummary[] = [
  ...FIXTURE_SKILLS,
  ...Array.from({ length: 240 }, (_, index) =>
    skill(
      `cadrumo-prueba-${String(index).padStart(3, "0")}`,
      `Habilidad de prueba número ${index}.`,
      {},
    ),
  ),
].sort((a, b) => (a.name < b.name ? -1 : 1));

const frontmatter = (summary: AgentSkillSummary) =>
  [
    "---",
    `name: ${summary.name}`,
    `description: ${summary.description}`,
    `applies_when: ${JSON.stringify(summary.applies_when)}`,
    "---",
  ].join("\n");

export function fixtureSkillDetail(
  summary: AgentSkillSummary,
): AgentSkillDetail {
  return {
    ...structuredClone(summary),
    content: `${frontmatter(summary)}\n\n# ${summary.name}\n\n${summary.description}\n\n## Pasos\n\n1. Lee los datos del perfil.\n2. Comprueba cada fuente.\n3. Propón el resultado para que la persona lo revise.\n`,
  };
}

/** The checks of one skill: one passes with a warning, one fails, the rest
 * pass clean. */
export function fixtureSkillVerification(
  summary: AgentSkillSummary,
): AgentSkillVerification {
  const findings: AgentSkillVerification["findings"] =
    summary.name === "cadrumo-facturas"
      ? [
          {
            severity: "warning",
            code: "token_budget",
            message: "SKILL.md uses 4 120 tokens of a 4 000 token budget.",
            path: "SKILL.md",
          },
        ]
      : summary.name === "cadrumo-revision-fuentes"
        ? [
            {
              severity: "error",
              code: "applies_when_empty",
              message: "applies_when names no condition.",
              path: "SKILL.md",
            },
          ]
        : [];
  return {
    name: summary.name,
    digest: summary.digest,
    valid: !findings.some((finding) => finding.severity === "error"),
    findings,
  };
}
