"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { cartCount, loadCart } from "@/lib/cart";

export default function Header() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const sync = () => setCount(cartCount(loadCart()));
    sync();
    window.addEventListener("drift:cart", sync);
    window.addEventListener("storage", sync);
    return () => { window.removeEventListener("drift:cart", sync); window.removeEventListener("storage", sync); };
  }, []);
  return (
    <header className="sticky top-0 z-40 bg-[#FFF8F0]/80 backdrop-blur border-b border-black/10">
      <div className="mx-auto max-w-[1280px] px-4 h-[56px] flex items-center justify-between">
        <Link href="/" className="font-black tracking-[0.28em] text-xl">DRIFT</Link>
        <nav className="hidden md:flex gap-6 text-sm tracking-wide">
          <Link href="/catalog?cat=New In">NEW IN</Link>
          <Link href="/catalog?cat=Dresses">DRESSES</Link>
          <Link href="/catalog?cat=Tops">TOPS</Link>
          <Link href="/catalog?cat=Bottoms">BOTTOMS</Link>
          <Link href="/catalog">SHOP ALL</Link>
        </nav>
        <div className="flex items-center gap-3">
          <Link href="/admin" className="hidden md:inline text-xs border border-black px-3 py-1.5">ADMIN</Link>
          <Link href="/cart" className="text-sm border border-black bg-black text-white px-4 py-1.5">CART ({count})</Link>
        </div>
      </div>
    </header>
  );
}
