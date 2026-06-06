import UnpluginTypia from "@typia/unplugin/bun";

const result = await Bun.build({
  entrypoints: ["src/index.js"],
  outdir: "../src/manim_widget/static",
  naming: "[name].js",
  format: "esm",
  minify: true,
  conditions: ["source"],
  plugins: [UnpluginTypia({ cache: true })],
});

if (!result.success) {
  for (const log of result.logs) {
    console.error(log);
  }
  process.exit(1);
}
