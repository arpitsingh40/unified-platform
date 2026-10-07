import Link from "next/link";
import { PRODUCTS, DROPS, formatINR } from "@/lib/catalog";
import ProductCard from "@/components/ProductCard";

export default function Home() {
  const newIn = PRODUCTS.slice(0, 8);
  return (
    <div>
      {/* Hero */}
      <section className="mx-auto max-w-[1280px] px-4 pt-6">
        <div className="grid md:grid-cols-[1.2fr_0.8fr] gap-4">
          <div className="relative bg-black text-white p-8 md:p-10 flex flex-col justify-between min-h-[420px]">
            <div className="text-xs tracking-[0.2em] text-white/60">DROP 01 — MONSOON • 24 STYLES • LIMITED RUN</div>
            <div>
              <h1 className="text-4xl md:text-5xl font-black leading-[0.9] tracking-tight">NEW DROP.<br/>GONE FOREVER.</h1>
              <p className="mt-3 text-white/70 max-w-[36ch]">Fast fashion at ₹599–₹1,999. New styles every Monday. Once sold out, never restocked. Free shipping over ₹1,999. COD available. 48h dispatch.</p>
              <div className="mt-6 flex gap-3">
                <Link href="/catalog" className="bg-white text-black px-6 py-3 text-sm font-semibold">SHOP NEW IN</Link>
                <Link href="/catalog?cat=Dresses" className="border border-white px-6 py-3 text-sm">DRESSES</Link>
              </div>
            </div>
            <div className="text-xs text-white/40">Starting at {formatINR(599)} • Avg {formatINR(1399)}</div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {newIn.slice(0, 4).map(p => (
              <div key={p.id} className="bg-white border border-black/10 p-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={p.image} alt={p.name} className="aspect-[3/4] w-full object-cover" />
                <div className="mt-2 text-xs font-medium line-clamp-1">{p.name}</div>
                <div className="text-sm font-semibold">{formatINR(p.price)}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Drops */}
      <section className="mx-auto max-w-[1280px] px-4 mt-8 flex flex-wrap gap-2">
        {DROPS.map(d => (
          <Link key={d} href={`/catalog?drop=${encodeURIComponent(d)}`} className="border border-black px-3 py-1.5 text-xs tracking-wide">{d}</Link>
        ))}
        <span className="text-xs text-black/60 py-1.5">New drops every Monday • 100 units per style • No restock</span>
      </section>

      {/* New In grid */}
      <section className="mx-auto max-w-[1280px] px-4 mt-8">
        <div className="flex items-baseline justify-between">
          <h2 className="font-black tracking-tight text-xl">NEW IN — DROP 01</h2>
          <Link href="/catalog" className="text-sm underline">View all 24</Link>
        </div>
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
          {newIn.map(p => <ProductCard key={p.id} p={p} />)}
        </div>
      </section>

      {/* Business model strip */}
      <section className="mx-auto max-w-[1280px] px-4 mt-10">
        <div className="grid md:grid-cols-3 gap-4 text-sm">
          <div className="bg-white border border-black/10 p-4">
            <div className="font-semibold">Worth Model</div>
            <div className="mt-1 text-black/60">AOV ₹1,399 • 65% margin • 30% repeat in 60 days • CAC via reels/UGC. Valuation = Revenue × 2.5× (fast fashion DTC benchmark).</div>
          </div>
          <div className="bg-white border border-black/10 p-4">
            <div className="font-semibold">Ops</div>
            <div className="mt-1 text-black/60">POD + micro-factory in Tiruppur. 48h dispatch. 14-day returns. COD at 30% orders. Replacement on sizing.</div>
          </div>
          <div className="bg-black text-white p-4">
            <div className="font-semibold">Launch Kit</div>
            <div className="mt-1 text-white/70">Reels (7), UGC brief, WhatsApp broadcast, influencer seeding (50 micro), pop-up plan — see <a className="underline" href="/admin">Admin</a>.</div>
          </div>
        </div>
      </section>
    </div>
  );
}
