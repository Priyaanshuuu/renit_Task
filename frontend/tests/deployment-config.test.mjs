import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";

function loadConfig(origin) {
  const env = { ...process.env };
  if (origin === undefined) delete env.BACKEND_ORIGIN;
  else env.BACKEND_ORIGIN = origin;
  return spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "-e",
      'import { config } from "./vercel.mjs"; console.log(JSON.stringify(config));',
    ],
    { env, encoding: "utf8" },
  );
}

test("deployment keeps API paths on the configured backend and serves the existing SPA build", () => {
  const result = loadConfig("https://wind-api.example.com/");
  assert.equal(result.status, 0, result.stderr);
  const config = JSON.parse(result.stdout);
  assert.deepEqual(config.rewrites, [
    {
      source: "/api/:path*",
      destination: "https://wind-api.example.com/api/:path*",
    },
  ]);
  assert.equal(config.outputDirectory, "build/client");
});

test("deployment fails clearly when the backend origin is missing or includes an invalid URL/path", () => {
  for (const origin of [
    undefined,
    "not-a-url",
    "http://wind-api.example.com",
    "https://wind-api.example.com/api",
    "https://user:password@wind-api.example.com",
    "https://wind-api.example.com?key=value",
  ]) {
    const result = loadConfig(origin);
    assert.notEqual(result.status, 0);
  }
});
