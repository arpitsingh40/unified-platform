// BusinessFactory — idea → worth business (unified-platform, FORGE)
// Delegates to blueprints/* registry (fashion/beauty/food/digital/generic).
// Business-os LLM fallback (factory_bridge.generate_catalog) remains source of truth when key=custom.

import { pickBlueprint as pick } from "../../blueprints";

export type BusinessBlueprint = {
  brand: { name: string; tagline: string; colors: { bg: string; text: string; accent: string } };
  pricing: { range: string; avg: number; margin: string; valuationMultiple: number };
  catalog: { count: number; categories: string[]; drops: string[] };
  routes: string[];
  worth: { aov: number; kpi: string[] };
};

function pickTemplate(idea: string): BusinessBlueprint {
  const b = pick(idea);
  const { key: _k, ...rest } = b as BusinessBlueprint & { key: string };
  return rest;
}

// The function you asked for — call this from anywhere in your code
export async function buildBusiness(idea: string): Promise<BusinessBlueprint & { idea: string; builtAt: string }> {
  const blueprint = pickTemplate(idea);
  // In prod: here we would call LLM to generate brand/catalog + scaffold files + seed DB
  // For now: returns the blueprint that the scaffold already implements
  // Extend this to write files: generate src/lib/catalog.ts, update brand in layout.tsx, etc.
  return {
    idea,
    builtAt: new Date().toISOString(),
    ...blueprint,
  };
}

// Helper: one-liner to build + log worth
export async function buildAndLog(idea: string) {
  const b = await buildBusiness(idea);
  console.log(`[Factory] "${idea}" → ${b.brand.name}: ${b.brand.tagline} | ${b.catalog.count} SKUs | ${b.pricing.range} | routes: ${b.routes.join(", ")}`);
  return b;
}
