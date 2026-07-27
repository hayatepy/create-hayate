import { existsSync, readFileSync, readdirSync } from "node:fs";
import { extname, join, resolve } from "node:path";

const root = resolve("dist");
const required = [
  join(root, "index.html"),
  join(root, "principles", "index.html"),
  join(root, "404.html"),
];

for (const path of required) {
  if (!existsSync(path)) {
    throw new Error(`Missing static route: $${path}`);
  }
}

function htmlFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? htmlFiles(path) : extname(path) === ".html" ? [path] : [];
  });
}

const documents = htmlFiles(root).map((path) => [path, readFileSync(path, "utf8")]);
const privateSignatures = [
  "/api/todos",
  "Cf-Access-Authenticated-User-Email",
  "data-private-record-count",
  "localStorage",
];

for (const [path, document] of documents) {
  for (const signature of privateSignatures) {
    if (document.includes(signature)) {
      throw new Error(`Private runtime signature $${signature} leaked into $${path}`);
    }
  }
}

const home = readFileSync(required[0], "utf8");
if (!home.includes('data-runtime-boundary="browser-only"')) {
  throw new Error("The static page is missing its explicit runtime-island boundary");
}

console.log(`Verified $${documents.length} static HTML files without private Hayate data.`);
