import { plugin } from "bun";
import UnpluginTypia from "@typia/unplugin/bun";

plugin(UnpluginTypia({ cache: true, log: false }));
