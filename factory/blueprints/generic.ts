// Blueprint: Generic — fallback for any idea not matching a vertical
export const generic = {
  brand: { name: "LUMEN", tagline: "Built for you. Shipped today.", colors: { bg: "#FFF8F0", text: "#0a0a0a", accent: "#0a0a0a" } },
  pricing: { range: "\u20B91,999–\u20B914,999", avg: 2499, margin: "60%", valuationMultiple: 3 },
  catalog: { count: 12, categories: ["New In","Bestsellers"], drops: ["Drop 01"] },
  routes: ["/","/catalog","/product/[id]","/cart","/checkout","/admin","/api/checkout"],
  worth: { aov: 2499, kpi: ["Orders","Revenue","AOV","Valuation"] },
  growth: { loops: ["weekly_drop","ugc_flywheel","retention"], headline: "Ship weekly + prove demand + retain" },
};
export default generic;
