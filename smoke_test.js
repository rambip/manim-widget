import { MobjectRegistry } from "./js/src/registry.js";
import fs from "fs";

const testData = JSON.parse(fs.readFileSync("./tests/fixtures/circle_scene.json", "utf-8"));

console.log("Testing registry loading...");
console.log(`FPS: ${testData.fps}`);
console.log(`Sections: ${testData.sections.length}`);

const section = testData.sections[0];
const commands = section.construct;

console.log(`\nCommands in first section: ${commands.length}`);
for (const cmd of commands) {
  console.log(`  - ${cmd.cmd}: ${cmd.id || 'N/A'}`);
}

const registry = new MobjectRegistry();
const mobjectMap = new Map();
for (const cmd of commands) {
  if (cmd.cmd === "add" && cmd.state) {
    mobjectMap.set(cmd.id, { id: cmd.id, ...cmd.state });
  }
}
registry.load(mobjectMap);

console.log(`\nRegistry loaded ${registry.getAll().length} mobjects`);
console.log(`Registry keys: ${Array.from(registry._registry.keys()).join(', ')}`);

const circle = registry.get("0");
if (circle) {
  console.log(`Circle found: kind=${circle._entry?.kind || 'unknown'}`);
  console.log(`Circle has setPoints: ${typeof circle.setPoints === 'function'}`);
  console.log(`Circle has setPosition: ${typeof circle.setPosition === 'function'}`);
  console.log(`Circle has setFillOpacity: ${typeof circle.setFillOpacity === 'function'}`);
  console.log(`Circle _entry:`, JSON.stringify({kind: circle._entry?.kind, id: circle._entry?.id}));
} else {
  console.log("ERROR: Circle not found in registry!");
  process.exit(1);
}

console.log("\nSmoke test passed!");
