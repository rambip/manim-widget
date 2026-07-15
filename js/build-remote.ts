// Release-only build: bundles our own glue code (index.js, registry.js,
// player.js, diff.js, camera.js, anim.js, mob.js) WITHOUT inlining
// manim-web. Instead, every `from "manim-web"` import is left external and
// rewritten to a jsDelivr URL pinned to manim-web's own published npm
// version, pointing at its self-contained `/browser` bundle (three.js and
// friends already inlined there — see manim-web/vite.browser.config.ts).
// This is `ManimWidget(js="remote")`'s _esm — anywidget/marimo fetch
// manim-web once from the CDN instead of embedding it (and re-downloading
// it) per widget instance. Output is packaged alongside the offline bundle
// as static/index.remote.js. Not used by build.ts/build-test.ts, which stay
// fully offline and self-contained.
import manimWebPkg from "../manim-web/package.json";

const version = manimWebPkg.version;
const cdnUrl = `https://cdn.jsdelivr.net/npm/manim-web@${version}/dist/manim-web.browser.js`;

const outdir = "../src/manim_widget/static";
const outPath = `${outdir}/index.remote.js`;

const result = await Bun.build({
  entrypoints: ["src/index.js"],
  outdir,
  naming: "index.remote.js",
  format: "esm",
  minify: true,
  external: ["manim-web"],
});

if (!result.success) {
  for (const log of result.logs) {
    console.error(log);
  }
  process.exit(1);
}

const rewritten = (await Bun.file(outPath).text()).replaceAll('"manim-web"', `"${cdnUrl}"`);
await Bun.write(outPath, rewritten);

console.log(`Wrote ${outPath} pinned to ${cdnUrl}`);
