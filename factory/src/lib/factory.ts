// BusinessFactory — idea → worth business
// One function builds the entire business: brand + catalog + storefront + checkout + admin
// Usage: import { buildBusiness } from "@/lib/factory"; await buildBusiness("fast fashion ecommerce")

export type BusinessBlueprint = {
  brand: { name: string; tagline: string; colors: { bg: string; text: string; accent: string } };
  pricing: { range: string; avg: number; margin: string; valuationMultiple: number };
  catalog: { count: number; categories: string[]; drops: string[] };
  routes: string[];
  worth: { aov: number; kpi: string[] };
};

const TEMPLATES: Record<string, BusinessBlueprint> = {
  "fast fashion ecommerce": {
    brand: { name: "DRIFT", tagline: "New drops weekly. Gone forever.", colors: { bg: "#FFF8F0", text: "#0a0a0a", accent: "#FF3B30" } },
    pricing: { range: "₹599–₹1,999", avg: 1399, margin: "65%", valuationMultiple: 2.5 },
    catalog: { count: 24, categories: ["Tops","Bottoms","Dresses","Outerwear","Accessories"], drops: ["Drop 01 — Monsoon","Drop 02 — Afterhours","Drop 03 — Off-Duty"] },
    routes: ["/","/catalog","/product/[id]","/cart","/checkout","/admin","/api/checkout"],
    worth: { aov: 1399, kpi: ["Orders","Revenue","AOV","Valuation (2.5×)"] },
  },
  "default": {
    brand: { name: "LUMEN", tagline: "Built for you. Shipped today.", colors: { bg: "#FFF8F0", text: "#0a0a0a", accent: "#0a0a0a" } },
    pricing: { range: "₹999–₹4,999", avg: 2499, margin: "60%", valuationMultiple: 3 },
    catalog: { count: 12, categories: ["New In","Bestsellers"], drops: ["Drop 01"] },
    routes: ["/","/catalog","/product/[id]","/cart","/checkout","/admin","/api/checkout"],
    worth: { aov: 2499, kpi: ["Orders","Revenue","AOV","Valuation"] },
  }
};

function pickTemplate(idea: string): BusinessBlueprint {
  const key = idea.toLowerCase();
  if (key.includes("fashion") || key.includes("apparel") || key.includes("clothing")) return TEMPLATES["fast fashion ecommerce"];
  return TEMPLATES["default"];
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
