// Blueprint: Fashion — extends DRIFT template (seeded from catalog.ts)
export const fashion = {
  brand: { name: "DRIFT", tagline: "New drops weekly. Gone forever.", colors: { bg: "#FFF8F0", text: "#0a0a0a", accent: "#FF3B30" } },
  pricing: { range: "\u20B91,599–\u20B92,199", avg: 1399, margin: "65%", valuationMultiple: 2.5 },
  catalog: { count: 24, categories: ["Tops","Bottoms","Dresses","Outerwear","Accessories"], drops: ["Drop 01 — Monsoon","Drop 02 — Afterhours","Drop 03 — Off-Duty"] },
  routes: ["/","/catalog","/product/[id]","/cart","/checkout","/admin","/api/checkout"],
  worth: { aov: 1399, kpi: ["Orders","Revenue","AOV","Valuation (2.5×)"] },
  growth: { loops: ["weekly_drop","ugc_flywheel","retention","pricing_test"], headline: "Weekly drops + UGC flywheel + COD→repeat" },
};
export default fashion;
