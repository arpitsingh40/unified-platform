// Blueprint: Food / D2C snacks, beverages
export const food = {
  brand: { name: "MUNCH", tagline: "Crave-worthy. Guilt-free. Delivered.", colors: { bg: "#FFFBEB", text: "#1a1a1a", accent: "#F59E0B" } },
  pricing: { range: "\u20B9199–\u20B91,499", avg: 599, margin: "55%", valuationMultiple: 3 },
  catalog: { count: 20, categories: ["Snacks","Beverages","Combos","Seasonal","Merch"], drops: ["Drop 01 — Crunch","Drop 02 — Sip","Drop 03 — Feast"] },
  routes: ["/","/catalog","/product/[id]","/cart","/checkout","/admin","/api/checkout"],
  worth: { aov: 599, kpi: ["Orders","Revenue","AOV","Repeat %", "Valuation (3×)"] },
  growth: { loops: ["retention","ugc_flywheel","weekly_drop"], headline: "Subscription + office bulk + festive gifting" },
};
export default food;
