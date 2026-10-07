"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CartItem, cartTotal, loadCart, saveCart } from "@/lib/cart";
import { formatINR } from "@/lib/catalog";

export default function CartPage() {
  const [items, setItems] = useState<CartItem[]>([]);
  useEffect(() => setItems(loadCart()), []);
  const total = cartTotal(items);
  const shipping = total > 0 && total < 1999 ? 99 : 0;
  const cod = 0;
  const grand = total + shipping + cod;
  const update = (next: CartItem[]) => { setItems(next); saveCart(next); };
  return (
    <div className="mx-auto max-w-[900px] px-4 py-6">
      <h1 className="text-xl font-black">CART</h1>
      {items.length === 0 ? (
        <div className="mt-6 border bg-white p-8 text-center">
          <div className="text-black/60">Your cart is empty.</div>
          <Link href="/catalog" className="mt-4 inline-block bg-black text-white px-6 py-2 text-sm">SHOP NEW IN</Link>
        </div>
      ) : (
        <div className="mt-6 grid md:grid-cols-[1.6fr_0.9fr] gap-6">
          <div className="space-y-3">
            {items.map((it, idx) => (
              <div key={`${it.product.id}-${it.size}`} className="flex gap-3 bg-white border p-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={it.product.image} alt={it.product.name} className="h-24 w-20 object-cover" />
                <div className="flex-1">
                  <div className="text-sm font-medium">{it.product.name}</div>
                  <div className="text-xs text-black/60">{it.product.color} • Size {it.size}</div>
                  <div className="text-sm font-semibold mt-1">{formatINR(it.product.price)}</div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => { const n=[...items]; n[idx].qty=Math.max(1,n[idx].qty-1); update(n); }} className="border px-2 py-1">−</button>
                  <span className="w-6 text-center text-sm">{it.qty}</span>
                  <button onClick={() => { const n=[...items]; n[idx].qty+=1; update(n); }} className="border px-2 py-1">+</button>
                  <button onClick={() => update(items.filter((_,i)=>i!==idx))} className="ml-2 text-xs underline">Remove</button>
                </div>
              </div>
            ))}
          </div>
          <div className="bg-white border p-4 h-fit">
            <div className="font-semibold">ORDER SUMMARY</div>
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between"><span>Subtotal</span><span>{formatINR(total)}</span></div>
              <div className="flex justify-between"><span>Shipping</span><span>{shipping ? formatINR(shipping) : "FREE"}</span></div>
              <div className="flex justify-between text-black/60"><span>COD</span><span>Available</span></div>
              <div className="border-t pt-2 flex justify-between font-bold"><span>Total</span><span>{formatINR(grand)}</span></div>
            </div>
            <Link href="/checkout" className="mt-4 block bg-black text-white text-center py-3 font-semibold">CHECKOUT</Link>
            <div className="mt-2 text-xs text-black/60 text-center">Cash on Delivery • UPI • Cards • 48h dispatch</div>
          </div>
        </div>
      )}
    </div>
  );
}
