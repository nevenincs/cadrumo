/* Independent JavaScript consumer for the cadrumo-jcs-utf8-lf-v1 vectors.
 * This file is a later verification entrypoint; it is not run during the
 * source-only implementation lane. */

import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const corpus = JSON.parse(await readFile(path.join(here, "vectors.json"), "utf8"));

function utf8Bytes(value) {
  const bytes = [];
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      if (index + 1 >= value.length) throw new Error("lone high surrogate");
      const low = value.charCodeAt(index + 1);
      if (low < 0xdc00 || low > 0xdfff) throw new Error("lone high surrogate");
      const point = 0x10000 + ((code - 0xd800) << 10) + (low - 0xdc00);
      bytes.push(0xf0 | (point >> 18), 0x80 | ((point >> 12) & 0x3f), 0x80 | ((point >> 6) & 0x3f), 0x80 | (point & 0x3f));
      index += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      throw new Error("lone low surrogate");
    } else if (code < 0x80) {
      bytes.push(code);
    } else if (code < 0x800) {
      bytes.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f));
    } else {
      bytes.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
    }
  }
  return Uint8Array.from(bytes);
}

function utf16Compare(left, right) {
  const length = Math.min(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    const difference = left.charCodeAt(index) - right.charCodeAt(index);
    if (difference !== 0) return difference;
  }
  return left.length - right.length;
}

function canonicalString(value) {
  utf8Bytes(value);
  let output = '"';
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code === 0x22) output += '\\"';
    else if (code === 0x5c) output += '\\\\';
    else if (code === 0x08) output += "\\b";
    else if (code === 0x09) output += "\\t";
    else if (code === 0x0a) output += "\\n";
    else if (code === 0x0c) output += "\\f";
    else if (code === 0x0d) output += "\\r";
    else if (code < 0x20) output += `\\u${code.toString(16).padStart(4, "0")}`;
    else output += value[index];
  }
  return `${output}"`;
}

function canonicalNumber(value) {
  if (!Number.isFinite(value) || Object.is(value, -0)) throw new Error("inadmissible number");
  if (Number.isInteger(value) && !Number.isSafeInteger(value)) throw new Error("unsafe integer");
  return String(value);
}

function canonical(value) {
  if (value === null) return "null";
  if (value === true) return "true";
  if (value === false) return "false";
  if (typeof value === "string") return canonicalString(value);
  if (typeof value === "number") return canonicalNumber(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (!value || typeof value !== "object") throw new Error("unsupported value");
  return `{${Object.keys(value).sort(utf16Compare).map((key) => `${canonicalString(key)}:${canonical(value[key])}`).join(",")}}`;
}

function sha256Hex(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

for (const vector of corpus.vectors) {
  try {
    const bytes = Buffer.from(`${canonical(vector.value)}\n`, "utf8");
    if (vector.error === "rejected") throw new Error(`vector ${vector.id} was accepted`);
    const actual = bytes.toString("hex");
    if (actual !== vector.expected_utf8_hex) throw new Error(`vector ${vector.id} bytes differ`);
    if (vector.expected_sha256 && sha256Hex(bytes) !== vector.expected_sha256) throw new Error(`vector ${vector.id} digest differs`);
  } catch (error) {
    if (vector.error !== "rejected") throw error;
  }
}
