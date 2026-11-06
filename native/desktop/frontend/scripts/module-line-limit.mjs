// The most physical lines a TypeScript module may take: the bound the
// repository's module-size gate holds every committed module to. A generator
// refuses to write a module past it, and the lint rule reports one while it is
// edited.
export const MODULE_LINE_LIMIT = 1500;

// The lines of a text as stored: CRLF, CR and LF each end a line, and a last
// line without its line break counts.
export function physicalLines(text) {
  if (text === "") return 0;
  const breaks = text.match(/\r\n|\r|\n/g)?.length ?? 0;
  return /[\r\n]$/.test(text) ? breaks : breaks + 1;
}

// The refusal for each named module longer than the limit; empty when every
// module fits.
export function oversizedModules(modules) {
  return modules.flatMap(([name, text]) => {
    const lines = physicalLines(text);
    return lines > MODULE_LINE_LIMIT
      ? [`${name} takes ${lines} lines, more than ${MODULE_LINE_LIMIT}`]
      : [];
  });
}

// Ends the process with a failure, naming every module over the limit and
// what to change, before a generator writes any of them; returns when every
// module fits.
export function refuseOversizedModules(modules, remedy) {
  const refused = oversizedModules(modules);
  if (!refused.length) return;
  for (const refusal of refused) console.error(`${refusal}; ${remedy}`);
  process.exit(1);
}
