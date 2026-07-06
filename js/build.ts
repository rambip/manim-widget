import UnpluginTypia from "@typia/unplugin/bun";

const result = await Bun.build({
  entrypoints: ["src/index.js"],
  outdir: "../src/manim_widget/static",
  naming: "[name].js",
  format: "esm",
  minify: true,
  conditions: ["source"],
  plugins: [UnpluginTypia({ cache: true, log: false })],
});

if (!result.success) {
  for (const log of result.logs) {
    console.error(log);
  }
  process.exit(1);
}

await Bun.write("../src/manim_widget/static/style.css", Bun.file("src/style.css"));
