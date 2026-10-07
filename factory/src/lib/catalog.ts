// DRIFT — Fast Fashion catalog. New drops weekly. Gone forever.
// Pricing: fast-fashion India sweet spot ₹599-₹1,999 (avg ₹1,199) → 65% gross margin at scale.

export type Product = {
  id: string;
  name: string;
  price: number; // INR
  compareAt?: number;
  category: "New In" | "Tops" | "Bottoms" | "Dresses" | "Outerwear" | "Accessories";
  color: string;
  sizes: string[];
  image: string;
  badge?: "NEW" | "LOW STOCK" | "BESTSELLER";
  drop: string; // e.g. "Drop 01 — Monsoon"
};

export const DROPS = ["Drop 01 — Monsoon", "Drop 02 — Afterhours", "Drop 03 — Off-Duty"];

export const PRODUCTS: Product[] = [
  // New In / Drop 01
  { id: "p01", name: "Cropped Linen Shirt", price: 1299, compareAt: 1899, category: "Tops", color: "Ecru", sizes: ["XS","S","M","L"], image: "https://picsum.photos/seed/drift01/600/800", badge: "NEW", drop: DROPS[0] },
  { id: "p02", name: "High-Waist Cargo Pants", price: 1799, compareAt: 2499, category: "Bottoms", color: "Stone", sizes: ["XS","S","M","L","XL"], image: "https://picsum.photos/seed/drift02/600/800", badge: "BESTSELLER", drop: DROPS[0] },
  { id: "p03", name: "Racer Mini Dress", price: 1499, category: "Dresses", color: "Black", sizes: ["XS","S","M","L"], image: "https://picsum.photos/seed/drift03/600/800", badge: "NEW", drop: DROPS[0] },
  { id: "p04", name: "Oversized Tee — Washed", price: 799, compareAt: 999, category: "Tops", color: "Faded Black", sizes: ["S","M","L","XL"], image: "https://picsum.photos/seed/drift04/600/800", drop: DROPS[0] },
  { id: "p05", name: "Pleated Midi Skirt", price: 1599, category: "Bottoms", color: "Cocoa", sizes: ["XS","S","M","L"], image: "https://picsum.photos/seed/drift05/600/800", badge: "LOW STOCK", drop: DROPS[0] },
  { id: "p06", name: "Utility Shacket", price: 1999, compareAt: 2799, category: "Outerwear", color: "Olive", sizes: ["S","M","L","XL"], image: "https://picsum.photos/seed/drift06/600/800", drop: DROPS[0] },
  { id: "p07", name: "Ribbed Tank 3-Pack", price: 999, category: "Tops", color: "White/Black/Grey", sizes: ["XS","S","M","L"], image: "https://picsum.photos/seed/drift07/600/800", badge: "BESTSELLER", drop: DROPS[0] },
  { id: "p08", name: "Wide-Leg Denim", price: 1699, category: "Bottoms", color: "Light Wash", sizes: ["XS","S","M","L","XL"], image: "https://picsum.photos/seed/drift08/600/800", drop: DROPS[0] },
  // Drop 02
  { id: "p09", name: "Satin Slip Dress", price: 1899, category: "Dresses", color: "Moss", sizes: ["XS","S","M","L"], image: "https://picsum.photos/seed/drift09/600/800", badge: "NEW", drop: DROPS[1] },
  { id: "p10", name: "Cropped Bomber", price: 2199, category: "Outerwear", color: "Cream", sizes: ["S","M","L"], image: "https://picsum.photos/seed/drift10/600/800", drop: DROPS[1] },
  { id: "p11", name: "Halter Top — Mesh", price: 899, category: "Tops", color: "Black", sizes: ["XS","S","M","L"], image: "https://picsum.photos/seed/drift11/600/800", badge: "LOW STOCK", drop: DROPS[1] },
  { id: "p12", name: "Parachute Pants", price: 1599, category: "Bottoms", color: "Khaki", sizes: ["XS","S","M","L","XL"], image: "https://picsum.photos/seed/drift12/600/800", drop: DROPS[1] },
  { id: "p13", name: "Knit Polo Dress", price: 1699, category: "Dresses", color: "Navy", sizes: ["XS","S","M","L"], image: "https://picsum.photos/seed/drift13/600/800", drop: DROPS[1] },
  { id: "p14", name: "Boxy Hoodie", price: 1499, compareAt: 1999, category: "Outerwear", color: "Heather Grey", sizes: ["S","M","L","XL"], image: "https://picsum.photos/seed/drift14/600/800", drop: DROPS[1] },
  { id: "p15", name: "Corset Top", price: 1199, category: "Tops", color: "Chocolate", sizes: ["XS","S","M","L"], image: "https://picsum.photos/seed/drift15/600/800", badge: "BESTSELLER", drop: DROPS[1] },
  { id: "p16", name: "Mini Crossbody Bag", price: 899, category: "Accessories", color: "Black", sizes: ["One Size"], image: "https://picsum.photos/seed/drift16/600/800", drop: DROPS[1] },
  // Drop 03
  { id: "p17", name: "Linen Blend Trousers", price: 1399, category: "Bottoms", color: "Sand", sizes: ["XS","S","M","L","XL"], image: "https://picsum.photos/seed/drift17/600/800", badge: "NEW", drop: DROPS[2] },
  { id: "p18", name: "Ruched Midi Dress", price: 1799, category: "Dresses", color: "Berry", sizes: ["XS","S","M","L"], image: "https://picsum.photos/seed/drift18/600/800", drop: DROPS[2] },
  { id: "p19", name: "Bandeau + Shirt Set", price: 1999, compareAt: 2699, category: "Tops", color: "White", sizes: ["XS","S","M","L"], image: "https://picsum.photos/seed/drift19/600/800", drop: DROPS[2] },
  { id: "p20", name: "Faux Leather Shorts", price: 1099, category: "Bottoms", color: "Black", sizes: ["XS","S","M","L"], image: "https://picsum.photos/seed/drift20/600/800", badge: "LOW STOCK", drop: DROPS[2] },
  { id: "p21", name: "Overshirt — Flannel", price: 1699, category: "Outerwear", color: "Check", sizes: ["S","M","L","XL"], image: "https://picsum.photos/seed/drift21/600/800", drop: DROPS[2] },
  { id: "p22", name: "Beaded Shoulder Bag", price: 1299, category: "Accessories", color: "Silver", sizes: ["One Size"], image: "https://picsum.photos/seed/drift22/600/800", drop: DROPS[2] },
  { id: "p23", name: "Asymmetric Top", price: 999, category: "Tops", color: "Red", sizes: ["XS","S","M","L"], image: "https://picsum.photos/seed/drift23/600/800", drop: DROPS[2] },
  { id: "p24", name: "Cut-Out Maxi Dress", price: 1999, category: "Dresses", color: "Black", sizes: ["XS","S","M","L"], image: "https://picsum.photos/seed/drift24/600/800", badge: "NEW", drop: DROPS[2] },
];

export const CATEGORIES = ["New In", "Tops", "Bottoms", "Dresses", "Outerwear", "Accessories"] as const;

export function formatINR(n: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);
}
