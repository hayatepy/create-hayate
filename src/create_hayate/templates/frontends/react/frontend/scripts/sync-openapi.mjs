import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = resolve(frontendRoot, "..");
const checkedDocument = join(frontendRoot, "openapi.json");
const checkedTypes = join(frontendRoot, "src", "api", "schema.d.ts");
const checkOnly = process.argv.includes("--check");
const temporaryRoot = checkOnly
  ? mkdtempSync(join(tmpdir(), "hayate-openapi-"))
  : frontendRoot;
const generatedDocument = join(temporaryRoot, "openapi.json");
const generatedTypes = checkOnly
  ? join(temporaryRoot, "schema.d.ts")
  : checkedTypes;

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: projectRoot,
    encoding: "utf8",
    stdio: "inherit",
    ...options,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

try {
  const pythonPath = [join(projectRoot, "src"), process.env.PYTHONPATH]
    .filter(Boolean)
    .join(delimiter);
  run(
    "uv",
    [
      "run",
      "--project",
      projectRoot,
      "python",
      "-m",
      "hayate_openapi",
      "app:app",
      "--title",
      "$project_name",
      "--version",
      "0.1.0",
      "--output",
      generatedDocument,
    ],
    { env: { ...process.env, PYTHONPATH: pythonPath } },
  );

  const executable = join(
    frontendRoot,
    "node_modules",
    ".bin",
    process.platform === "win32" ? "openapi-typescript.cmd" : "openapi-typescript",
  );
  run(executable, [generatedDocument, "-o", generatedTypes], { cwd: frontendRoot });

  if (checkOnly) {
    const mismatches = [
      [checkedDocument, generatedDocument],
      [checkedTypes, generatedTypes],
    ].filter(
      ([checked, generated]) =>
        !existsSync(checked) ||
        readFileSync(checked, "utf8") !== readFileSync(generated, "utf8"),
    );
    if (mismatches.length) {
      for (const [checked] of mismatches) {
        console.error(`OpenAPI artifact is stale: $${checked}`);
      }
      console.error("Run `npm run api:generate` and commit the updated artifacts.");
      process.exitCode = 1;
    } else {
      console.log("OpenAPI document and generated TypeScript types are current.");
    }
  }
} finally {
  if (checkOnly) {
    rmSync(temporaryRoot, { recursive: true, force: true });
  }
}
