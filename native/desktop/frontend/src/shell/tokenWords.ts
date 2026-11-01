import type { Translate } from "./strings";

/** A token in the chrome's word where the chrome has one under `prefix`, and
 * the token as it is stored otherwise: the registry may serve one the chrome
 * does not word yet. */
export function wordOrToken(
  t: Translate,
  prefix: string,
  token: string,
): string {
  const key = `${prefix}${token}`;
  const said = t(key);
  return said === key ? token : said;
}
