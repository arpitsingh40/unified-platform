// Blueprint registry — idea → BusinessBlueprint
// Deterministic pick first, LLM fallback lives in business-os/factory_bridge.py (never empty).

import fashion from "./fashion";
import beauty from "./beauty";
import food from "./food";
import digital from "./digital";
import generic from "./generic";

export type BusinessBlueprint = typeof fashion;

const REGISTRY: Record<string, BusinessBlueprint> = { fashion, beauty, food, digital, generic };

export function pickBlueprint(idea: string): BusinessBlueprint & { key: string } {
  const t = idea.toLowerCase();
  if (t.match(/fashion|apparel|clothing|streetwear|drops|drift/)) return { ...fashion, key: "fashion" };
  if (t.match(/beauty|skincare|cosmetic|makeup|glow|serum/)) return { ...beauty, key: "beauty" };
  if (t.match(/food|snack|beverage|drink|kitchen|spice|tea|coffee|munch/)) return { ...food, key: "food" };
  if (t.match(/saas|template|course|digital|software|app|platform|ai|tool/)) return { ...digital, key: "digital" };
  return { ...generic, key: "generic" };
}

// Re-export for consumers that want the full registry
export const blueprints = REGISTRY;
export { fashion, beauty, food, digital, generic };
export default pickBlueprint;
