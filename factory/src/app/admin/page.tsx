"use client";
import { useEffect, useState } from "react";
import { PRODUCTS, formatINR } from "@/lib/catalog";

export default function AdminPage() {
  const [orders, setOrders] = useState<{ count: number; orders: { orderId: string; at: string; total: number; pay: string; phone: string }[] }>({ count: 0, orders: [] });
  useEffect(() => { fetch("/api/checkout").then(r => r.json()).then(setOrders).catch(() => {}); }, []);
  const revenue = orders.orders.reduce((s, o) => s + (o.total || 0), 0);
  const aov = orders.count ? Math.round(revenue / orders.count) : 0;
  const valuation = Math.round(revenue * 2.5); // 2.5x fast fashion DTC
  const skus = PRODUCTS.length;
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-6">
      <h1 className="text-xl font-black">ADMIN — WORTH DASHBOARD</h1>
      <div className="text-sm text-black/60">Orders, Revenue, AOV, Valuation. Replace with real DB for prod. Admin auth: add password/env before public launch.</div>
      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-black text-white p-4"><div className="text-xs tracking-widest text-white/60">ORDERS</div><div className="text-2xl font-black mt-1">{orders.count}</div></div>
        <div className="bg-white border p-4"><div className="text-xs tracking-widest text-black/40">REVENUE</div><div className="text-2xl font-black mt-1">{formatINR(revenue)}</div></div>
        <div className="bg-white border p-4"><div className="text-xs tracking-widest text-black/40">AOV</div><div className="text-2xl font-black mt-1">{aov ? formatINR(aov) : "—"}</div></div>
        <div className="bg-white border p-4"><div className="text-xs tracking-widest text-black/40">VALUATION (2.5×)</div><div className="text-2xl font-black mt-1">{formatINR(valuation)}</div></div>
      </div>
      <div className="mt-4 grid md:grid-cols-3 gap-4 text-sm">
        <div className="bg-white border p-4"><div className="font-semibold">Catalog</div><div className="text-black/60 mt-1">{skus} SKUs • 3 drops • Avg ₹1,399 • No restock model</div></div>
        <div className="bg-white border p-4"><div className="font-semibold">Margins</div><div className="text-black/60 mt-1">COGS ~35% • Margin 65% • Shipping ₹99 under ₹1,999 • COD verification reduces RTO</div></div>
        <div className="bg-white border p-4"><div className="font-semibold">Next</div><div className="text-black/60 mt-1">Connect Razorpay/UPI, add Supabase orders, add admin password, deploy to Vercel.</div></div>
      </div>
      <div className="mt-6 bg-white border">
        <div className="p-3 font-semibold border-b text-sm">RECENT ORDERS (last 20)</div>
        {orders.orders.length === 0 ? (
          <div className="p-6 text-sm text-black/60">No orders yet. Place a test order via checkout to see it here.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-black/40"><tr><th className="text-left p-2">Order</th><th className="text-left p-2">Time</th><th className="text-left p-2">Phone</th><th className="text-left p-2">Pay</th><th className="text-right p-2">Total</th></tr></thead>
              <tbody>
                {orders.orders.map(o => (
                  <tr key={o.orderId} className="border-t"><td className="p-2 font-mono text-xs">{o.orderId}</td><td className="p-2 text-xs">{new Date(o.at).toLocaleString()}</td><td className="p-2">{o.phone}</td><td className="p-2">{o.pay}</td><td className="p-2 text-right font-semibold">{formatINR(o.total)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <div className="mt-6 border bg-[#0a0a0a] text-white p-4 text-sm">
        <div className="font-semibold">LAUNCH KIT (ship today)</div>
        <ol className="mt-2 list-decimal list-inside space-y-1 text-white/70">
          <li>Deploy to Vercel: <span className="font-mono">vercel --prod</span> (or connect GitHub).</li>
          <li>Payments: Razorpay checkout link or UPI QR — replace COD-only if desired.</li>
          <li>Content: 7 reels (hook: "₹799 steal / ₹1,999 fit") + 50 micro influencers (gifting, 5k-20k followers).</li>
          <li>WhatsApp: broadcast drop link to 500 contacts + verify COD orders in 30 mins.</li>
          <li>Ads: ₹1,000/day meta reels retargeting from day 3.</li>
        </ol>
      </div>
    </div>
  );
}
