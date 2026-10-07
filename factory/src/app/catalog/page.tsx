import { CATEGORIES, DROPS, PRODUCTS } from "@/lib/catalog";
import ProductCard from "@/components/ProductCard";

export default function CatalogPage({ searchParams }: { searchParams: { cat?: string; drop?: string; q?: string } }) {
  const cat = searchParams.cat;
  const drop = searchParams.drop;
  const q = (searchParams.q || "").toLowerCase();
  const filtered = PRODUCTS.filter(p => {
    if (cat && cat !== "New In" && p.category !== cat) return false;
    if (drop && p.drop !== drop) return false;
    if (q && !(`${p.name} ${p.color} ${p.category}`.toLowerCase().includes(q))) return false;
    return true;
  });
  return (
    <div className="mx-auto max-w-[1280px] px-4 py-6">
      <div className="flex flex-wrap gap-2">
        <a href="/catalog" className={`px-3 py-1.5 text-xs border ${!cat ? "bg-black text-white" : "bg-white"}`}>ALL ({PRODUCTS.length})</a>
        {CATEGORIES.map(c => (
          <a key={c} href={`/catalog?cat=${encodeURIComponent(c)}`} className={`px-3 py-1.5 text-xs border ${cat === c ? "bg-black text-white" : "bg-white"}`}>{c.toUpperCase()}</a>
        ))}
        <span className="ml-auto text-xs text-black/60 py-1.5">{filtered.length} styles • Drops: {DROPS.join(" • ")}</span>
      </div>
      <form className="mt-4 flex gap-2">
        <input name="q" defaultValue={searchParams.q || ""} placeholder="Search: linen, cargo, dress..." className="flex-1 border border-black/20 px-3 py-2 text-sm" />
        <button className="bg-black text-white px-5 text-sm">SEARCH</button>
        <a href="/catalog" className="border px-5 py-2 text-sm">CLEAR</a>
      </form>
      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        {filtered.map(p => <ProductCard key={p.id} p={p} />)}
      </div>
      {filtered.length === 0 && <div className="mt-10 text-center text-black/60">No matches. Try another drop or category.</div>}
    </div>
  );
}
