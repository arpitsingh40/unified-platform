import Link from "next/link";
import { Product, formatINR } from "@/lib/catalog";

export default function ProductCard({ p }: { p: Product }) {
  return (
    <Link href={`/product/${p.id}`} className="group block">
      <div className="relative aspect-[3/4] overflow-hidden bg-white border border-black/10">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={p.image} alt={p.name} className="h-full w-full object-cover group-hover:scale-[1.03] transition" />
        {p.badge && <span className="absolute left-2 top-2 bg-black text-white text-[10px] tracking-widest px-2 py-1">{p.badge}</span>}
        {p.compareAt && <span className="absolute right-2 top-2 bg-white text-black text-[10px] px-2 py-1 border">SALE</span>}
      </div>
      <div className="mt-2">
        <div className="text-sm leading-tight line-clamp-1">{p.name}</div>
        <div className="text-xs text-black/60">{p.color} • {p.drop}</div>
        <div className="mt-1 flex gap-2 items-baseline">
          <span className="font-semibold text-sm">{formatINR(p.price)}</span>
          {p.compareAt && <span className="text-xs line-through text-black/40">{formatINR(p.compareAt)}</span>}
        </div>
      </div>
    </Link>
  );
}
