import UnpluginTypia from "@typia/unplugin/bun";

const result = await Bun.build({
  entrypoints: ["src/test_cli.js"],
  outdir: "node_modules/.cache/manim-widget-test",
  naming: "[name].js",
  format: "esm",
  target: "bun",
  conditions: ["source"],
  external: ["opentype.js"],
  plugins: [UnpluginTypia({ cache: true, log: false })],
});

if (!result.success) {
  for (const log of result.logs) {
    console.error(log);
  }
  process.exit(1);
}
