import { plugin } from "bun";
import UnpluginTypia from "@typia/unplugin/bun";

// manim-web compiles from TypeScript source (the `source` export condition) and
// relies on typia's compiler transform for runtime validation. Bun does not run
// that transform on its own, so register it as a global plugin for both `bun
// build` (bundling the widget) and `bun run` (the CLI integration harness).
plugin(UnpluginTypia({ cache: true }));
