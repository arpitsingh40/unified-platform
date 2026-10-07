// Blueprint: Digital / SaaS / courses / templates
export const digital = {
  brand: { name: "LUMEN", tagline: "Ship faster. Learn once. Compound forever.", colors: { bg: "#F8FAFF", text: "#0f172a", accent: "#6366F1" } },
  pricing: { range: "\u20B9499–\u20B99,999", avg: 2499, margin: "85%", valuationMultiple: 6 },
  catalog: { count: 12, categories: ["Templates","Courses","Tools","Bundles"], drops: ["Pack 01 — Starter","Pack 02 — Pro","Pack 03 — Scale"] },
  routes: ["/","/catalog","/product/[id]","/cart","/checkout","/admin","/api/checkout"],
  worth: { aov: 2499, kpi: ["Orders","Revenue","AOV","Valuation (6×)"] },
  growth: { loops: ["weekly_drop","pricing_test","ugc_flywheel"], headline: "Templates → courses → community → 85% margin flywheel" },
};
export default digital;
