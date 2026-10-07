"use client";
import { Product } from "./catalog";

export type CartItem = { product: Product; size: string; qty: number };

const KEY = "drift_cart_v1";

export function loadCart(): CartItem[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; }
}
export function saveCart(items: CartItem[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(KEY, JSON.stringify(items));
  window.dispatchEvent(new CustomEvent("drift:cart", { detail: items }));
}
export function addToCart(product: Product, size: string) {
  const items = loadCart();
  const idx = items.findIndex(i => i.product.id === product.id && i.size === size);
  if (idx >= 0) items[idx].qty += 1;
  else items.push({ product, size, qty: 1 });
  saveCart(items);
}
export function cartCount(items: CartItem[]) { return items.reduce((s, i) => s + i.qty, 0); }
export function cartTotal(items: CartItem[]) { return items.reduce((s, i) => s + i.product.price * i.qty, 0); }
