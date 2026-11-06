// Holds every generated TypeScript module to the repository's module bound
// before a generator writes or compares any of them. The bound is not stated
// here: each generator receives it from its Python producer, which reads it
// from its one definition.

// The lines of a text as stored: CRLF, CR and LF each end a line, and a last
// line without its line break counts.
export function physicalLines(text) {
  if (text === "") return 0;
  const breaks = text.match(/\r\n|\r|\n/g)?.length ?? 0;
  return /[\r\n]$/.test(text) ? breaks : breaks + 1;
}

// The bound a producer handed over, refused unless it is a positive integer,
// so a producer that stopped sending it cannot disable the refusal.
export function moduleBound(bound) {
  if (!Number.isInteger(bound) || bound < 1)
    throw new Error(
      `the producer sent no positive integer module bound: ${JSON.stringify(bound)}`,
    );
  return bound;
}

// The refusal for each (path, text) module longer than the bound; empty when
// every module fits.
export function oversizedModules(modules, bound) {
  const limit = moduleBound(bound);
  return modules.flatMap(([path, text]) => {
    const lines = physicalLines(text);
    return lines > limit
      ? [`${path} takes ${lines} lines, more than ${limit}`]
      : [];
  });
}

// Ends the process with a failure, naming every module over the bound and
// what to change, before anything is written; returns when every module fits.
export function refuseOversizedModules(modules, bound, remedy) {
  const refused = oversizedModules(modules, bound);
  if (!refused.length) return;
  for (const refusal of refused) console.error(`${refusal}; ${remedy}`);
  process.exit(1);
}
