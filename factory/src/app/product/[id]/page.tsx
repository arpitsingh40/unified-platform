"use client";
import { useState } from "react";
import { PRODUCTS, formatINR } from "@/lib/catalog";
import { addToCart } from "@/lib/cart";

export default function ProductPage({ params }: { params: { id: string } }) {
  const p = PRODUCTS.find(x => x.id === params.id);
  const [size, setSize] = useState<string>(p?.sizes[0] || "M");
  const [added, setAdded] = useState(false);
  if (!p) return <div className="mx-auto max-w-[1280px] px-4 py-10">Not found.</div>;
  return (
    <div className="mx-auto max-w-[1280px] px-4 py-6 grid md:grid-cols-2 gap-8">
      <div className="bg-white border border-black/10">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={p.image} alt={p.name} className="w-full aspect-[3/4] object-cover" />
      </div>
      <div>
        <div className="text-xs tracking-widest text-black/50">{p.drop} • {p.category}</div>
        <h1 className="mt-1 text-2xl font-black tracking-tight">{p.name}</h1>
        <div className="text-sm text-black/60">{p.color}</div>
        <div className="mt-3 flex items-baseline gap-3">
          <span className="text-xl font-bold">{formatINR(p.price)}</span>
          {p.compareAt && <span className="line-through text-black/40 text-sm">{formatINR(p.compareAt)}</span>}
          {p.badge && <span className="bg-black text-white text-xs px-2 py-1">{p.badge}</span>}
        </div>
        <div className="mt-6">
          <div className="text-xs tracking-widest">SIZE</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {p.sizes.map(s => (
              <button key={s} onClick={() => setSize(s)} className={`px-4 py-2 text-sm border ${size === s ? "bg-black text-white" : "bg-white"}`}>{s}</button>
            ))}
          </div>
        </div>
        <button
          onClick={() => { addToCart(p, size); setAdded(true); setTimeout(() => setAdded(false), 1800); }}
          className="mt-6 w-full bg-black text-white py-3 font-semibold"
        >
          {added ? "ADDED ✓" : "ADD TO CART"}
        </button>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-black/60">
          <div className="border p-3">48H DISPATCH • COD • FREE SHIPPING OVER ₹1,999</div>
          <div className="border p-3">14-DAY RETURNS • EXCHANGE FOR SIZE • NO QUESTIONS</div>
        </div>
        <div className="mt-6 text-sm leading-relaxed text-black/70">
          Cut for India. Breathable, durable, made to repeat. Limited run — once sold out, never restocked. Join the drop: new styles every Monday 12PM.
        </div>
        <div className="mt-6 flex gap-2">
          <a href="/catalog" className="border px-4 py-2 text-sm">BACK TO SHOP</a>
          <a href="/cart" className="bg-black text-white px-4 py-2 text-sm">GO TO CART</a>
        </div>
      </div>
    </div>
  );
}
