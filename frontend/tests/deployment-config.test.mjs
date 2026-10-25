import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";

test("static deployment config supplies an explicit HTTPS API destination", async () => {
  const config = JSON.parse(
    await readFile(new URL("../vercel.json", import.meta.url), "utf8"),
  );
  assert.equal(config.framework, "vite");
  assert.equal(config.outputDirectory, "build/client");
  assert.equal(config.rewrites.length, 1);
  const rewrite = config.rewrites[0];
  assert.equal(rewrite.source, "/api/:path*");
  assert.equal(typeof rewrite.destination, "string");
  assert.equal(rewrite.destination, "https://renittask.vercel.app/api/:path*");
  assert.equal(new URL(rewrite.destination).protocol, "https:");
});

test("frontend has one Vercel configuration, without a conflicting dynamic config", async () => {
  const files = await readdir(new URL("../", import.meta.url));
  const configs = files.filter((name) =>
    /^vercel\.(json|ts|mts|js|mjs|cjs|toml)$/.test(name),
  );
  assert.deepEqual(configs, ["vercel.json"]);
});
