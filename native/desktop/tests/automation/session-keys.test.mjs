import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  removeLeftSessionKeys,
  sessionKeyTargets,
  storageProfileIds,
} from "./session-keys.mjs";

const target = (profile) =>
  `${profile}:${randomUUID()}@cadrumo:profile-session:v2`;
const store = (name) =>
  spawnSync("cmdkey", [`/generic:${name}`, "/user:probe", "/pass:probe"], {
    encoding: "utf8",
  }).status === 0;
const remove = (name) => spawnSync("cmdkey", [`/delete:${name}`]);

test("storageProfileIds answers the bucket ids of a storage root", () => {
  const root = mkdtempSync(join(tmpdir(), "cadrumo-session-keys-"));
  try {
    const id = randomUUID();
    mkdirSync(join(root, "buckets", id), { recursive: true });
    mkdirSync(join(root, "buckets", "not-a-profile"), { recursive: true });
    assert.deepEqual(storageProfileIds(root), [id]);
    assert.deepEqual(storageProfileIds(join(root, "absent")), []);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test(
  "a session key a run adds is found and removed; one stored before it is kept",
  { skip: process.platform !== "win32" && "the credential store is Windows" },
  () => {
    const profile = randomUUID();
    const earlier = target(profile);
    const added = target(profile);
    const other = target(randomUUID());
    try {
      assert(store(earlier), "cmdkey stored the earlier key");
      const before = sessionKeyTargets([profile]);
      assert.deepEqual(before, [earlier]);
      assert(store(added), "cmdkey stored the run's key");
      assert(store(other), "cmdkey stored another profile's key");

      const { left, failed } = removeLeftSessionKeys([profile], before);
      assert.deepEqual(left, [added]);
      assert.deepEqual(failed, []);
      assert.deepEqual(sessionKeyTargets([profile]), [earlier]);
      assert.equal(sessionKeyTargets([randomUUID()]).length, 0);
      const stillOther = spawnSync("cmdkey", ["/list"], { encoding: "utf8" });
      assert(
        stillOther.stdout.includes(other),
        "another profile's key is kept",
      );

      assert.deepEqual(removeLeftSessionKeys([profile], before).left, []);
    } finally {
      for (const name of [earlier, added, other]) remove(name);
    }
  },
);
