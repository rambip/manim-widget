import UnpluginTypia from "@typia/unplugin/bun";

// manim-web compiles from TypeScript source (the `source` export condition) and
// relies on typia's compiler transform for runtime validation. The `bun build`
// CLI does not apply bunfig preload plugins, so bundle programmatically with the
// typia transform wired in explicitly.
const result = await Bun.build({
  entrypoints: ["src/index.js"],
  outdir: "../src/manim_widget/static",
  conditions: ["source"],
  format: "esm",
  minify: true,
  naming: "[name].js",
  plugins: [UnpluginTypia({ cache: true })],
});

if (!result.success) {
  for (const log of result.logs) console.error(log);
  process.exit(1);
}

const entry = result.outputs.find((o) => o.kind === "entry-point");
console.log(`Bundled ${result.outputs.length} output(s); entry ${entry?.path}`);
