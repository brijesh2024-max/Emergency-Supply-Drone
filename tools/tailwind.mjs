import { compile } from "tailwindcss";
import { writeFile, readFile, readdir } from "node:fs/promises";
const compiler = await compile("@tailwind utilities;");
const inputs = await readdir("components");
const candidates = new Set();
for (const file of inputs.filter((f) => f.endsWith(".tsx"))) {
  const source = await readFile("components/" + file, "utf8");
  for (const match of source.matchAll(/className="([^"]+)"/g)) {
    for (const value of match[1].split(/\s+/)) candidates.add(value);
  }
}
await writeFile("app/utilities.css", compiler.build([...candidates]));
