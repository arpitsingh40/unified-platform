// Blueprint: Beauty / skincare
export const beauty = {
  brand: { name: "GLO", tagline: "Skin first. Science second. Glow always.", colors: { bg: "#FFF9F0", text: "#1a1a1a", accent: "#E8A0BF" } },
  pricing: { range: "\u20B9499–\u20B92,999", avg: 1299, margin: "72%", valuationMultiple: 4 },
  catalog: { count: 18, categories: ["Cleansers","Serums","Moisturizers","Masks","Kits"], drops: ["Drop 01 — Glow","Drop 02 — Repair","Drop 03 — Protect"] },
  routes: ["/","/catalog","/product/[id]","/cart","/checkout","/admin","/api/checkout"],
  worth: { aov: 1299, kpi: ["Orders","Revenue","AOV","Repeat %", "Valuation (4×)"] },
  growth: { loops: ["ugc_flywheel","retention","weekly_drop"], headline: "UGC before/after + subscription refill loop" },
};
export default beauty;
