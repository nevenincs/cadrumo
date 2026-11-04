// Preserves the final owned cadrumo-agent log files of a packaged run as
// evidence before the run's storage is deleted. Only the log names the
// product-log gate reads are captured, and only when they resolve inside
// `<storage>/agent/`; nothing else in that tree is ever opened.
import { realpathSync, statSync } from "node:fs";
import { basename, isAbsolute, relative, resolve } from "node:path";

import { agentLogGroups } from "./product-log.mjs";

/** An evidence-name part: no separators, no characters outside a safe set. */
export function sanitizeEvidencePart(text) {
  return String(text)
    .replace(/[^A-Za-z0-9._-]/g, "_")
    .replace(/^\.+/, "_");
}

/** True when `child` resolves strictly inside `parent` once links are followed. */
export function resolvesInside(parent, child) {
  try {
    const inside = relative(realpathSync(parent), realpathSync(child));
    return !!inside && !inside.startsWith("..") && !isAbsolute(inside);
  } catch {
    return false;
  }
}

/**
 * Captures the agent logs of `storage` as `<prefix>-agent-<hash8>-<file>`.
 * Never throws: evidence collection does not own the cleanup outcome.
 */
export function captureAgentLogs({ results, storage, prefix }) {
  const captures = [];
  try {
    const agentDirectory = resolve(storage, "agent");
    for (const group of agentLogGroups(storage)) {
      const hash = sanitizeEvidencePart(basename(group.root)).slice(0, 8);
      for (const file of [...group.structured, ...group.stderr]) {
        const name = `${prefix}-agent-${hash}-${sanitizeEvidencePart(basename(file))}`;
        let regular = false;
        try {
          regular = statSync(file).isFile();
        } catch {
          // Unreadable entries are reported as refused below.
        }
        if (!regular || !resolvesInside(agentDirectory, file)) {
          captures.push({ name, status: "refused_outside_agent_storage" });
          continue;
        }
        captures.push(results.logEvidence(name, file));
      }
    }
  } catch {
    // Keep cleanup and the original failing check authoritative.
  }
  return captures;
}
