import declarations from "@fixtures/modelo/declarations-en.json" with { type: "json" };

// The work units the seeded declarations list opens, found by the modelo the
// story names. The list is the application's own read, so a reseed moves the
// units and the stories follow it.

/** The work unit of the declaration the seeded list opens for `modelo`. */
export function seededUnit(modelo: string): string {
  const row = declarations.rows.find(
    (candidate) =>
      candidate.modelo === modelo &&
      candidate.opens_local_work &&
      typeof candidate.work_unit_id === "string",
  );
  if (!row || typeof row.work_unit_id !== "string")
    throw new Error(`the seeded list opens no declaration for ${modelo}`);
  return row.work_unit_id;
}
