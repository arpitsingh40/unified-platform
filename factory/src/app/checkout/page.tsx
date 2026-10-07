"use client";
import { useState } from "react";
import { cartTotal, loadCart, saveCart } from "@/lib/cart";
import { formatINR } from "@/lib/catalog";

export default function CheckoutPage() {
  const [done, setDone] = useState(false);
  const [orderId, setOrderId] = useState("");
  const [pay, setPay] = useState<"COD" | "UPI" | "CARD">("COD");
  const items = typeof window !== "undefined" ? loadCart() : [];
  const total = cartTotal(items);
  const shipping = total > 0 && total < 1999 ? 99 : 0;
  const grand = total + shipping;

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const res = await fetch("/api/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: fd.get("name"), phone: fd.get("phone"), address: fd.get("address"),
        pincode: fd.get("pincode"), pay, items, total: grand
      })
    });
    const data = await res.json();
    setOrderId(data.orderId || "DRIFT-" + Math.random().toString(36).slice(2, 8).toUpperCase());
    setDone(true);
    saveCart([]);
  };

  if (done) {
    return (
      <div className="mx-auto max-w-[640px] px-4 py-10 text-center">
        <div className="bg-white border p-8">
          <div className="text-2xl font-black">ORDER CONFIRMED ✓</div>
          <div className="mt-2 text-sm text-black/60">Order {orderId} • {formatINR(grand)} • Pay: {pay}</div>
          <div className="mt-4 text-sm">We will confirm on WhatsApp in 30 mins. 48h dispatch. 14-day returns.</div>
          <a href="/catalog" className="mt-6 inline-block bg-black text-white px-6 py-2 text-sm">CONTINUE SHOPPING</a>
          <div className="mt-6 text-xs text-black/40">Owner: check /admin for Worth dashboard (orders, revenue, AOV).</div>
        </div>
      </div>
    );
  }

  if (items.length === 0) return <div className="mx-auto max-w-[640px] px-4 py-10">No items. <a className="underline" href="/catalog">Shop</a></div>;

  return (
    <div className="mx-auto max-w-[640px] px-4 py-6">
      <h1 className="text-xl font-black">CHECKOUT</h1>
      <div className="mt-2 text-sm text-black/60">Free shipping over ₹1,999 • COD • UPI • Cards</div>
      <form onSubmit={submit} className="mt-6 bg-white border p-4 space-y-3">
        <input name="name" required placeholder="Full name" className="w-full border px-3 py-2 text-sm" />
        <input name="phone" required placeholder="Phone (WhatsApp)" className="w-full border px-3 py-2 text-sm" />
        <textarea name="address" required placeholder="Address, landmark, city, state" rows={3} className="w-full border px-3 py-2 text-sm" />
        <input name="pincode" required placeholder="Pincode" className="w-full border px-3 py-2 text-sm" />
        <div className="flex gap-2 text-sm">
          {(["COD", "UPI", "CARD"] as const).map(m => (
            <button key={m} type="button" onClick={() => setPay(m)} className={`flex-1 border py-2 ${pay === m ? "bg-black text-white" : "bg-white"}`}>{m}</button>
          ))}
        </div>
        <div className="flex justify-between font-bold border-t pt-3"><span>Total</span><span>{formatINR(grand)}</span></div>
        <button className="w-full bg-black text-white py-3 font-semibold">PLACE ORDER — {formatINR(grand)}</button>
        <div className="text-xs text-black/40 text-center">By ordering you agree to 14-day returns and COD verification call.</div>
      </form>
    </div>
  );
}
