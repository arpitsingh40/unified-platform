# LAUNCH KIT — DRIFT Fast Fashion

## Run it (now live on :3001)

```bash
cd "C:\Users\Dell -\Documents\Code\BusinessFactory"
npm run dev   # http://localhost:3001
# prod:
npm run build && npm run start
```

Verified 5/5: `/`, `/catalog`, `/product/p01`, `/cart`, `/admin` + `POST /api/checkout` → `orderId`.

## Business (DRIFT)

- **Brand:** DRIFT — New drops weekly. Gone forever. ₹599–₹1,999, avg ₹1,399.
- **Model:** Limited run (100 units/style), no restock, 48h dispatch, COD 30%, free ship >₹1,999, 14-day returns. 65% margin, AOV ₹1,399, valuation 2.5× revenue (DTC fast fashion).
- **Catalog:** 24 SKUs (8 Tops, 6 Bottoms, 5 Dresses, 3 Outerwear, 2 Accessories) across 3 drops. `src/lib/catalog.ts`.
- **Ops:** POD/Tiruppur micro-factory. Next step: Razorpay + Supabase.

## What you got (worth-creating business)

- Storefront: Home (hero + drops + new-in), Catalog (filter: cat/drop/search), Product (size + ATC), Cart (+/−), Checkout (name/phone/address/pincode + COD/UPI/CARD), Admin (orders/revenue/AOV/valuation + launch checklist).
- Cart: localStorage + `drift:cart` event + header sync. Checkout: `POST /api/checkout` → in-memory orders (swap to DB for prod).
- Worth dashboard: `/admin` — Orders, Revenue, AOV, Valuation. `GET /api/checkout` returns last 20.

## Ship checklist (1 day to paid)

- [ ] Add admin password (env `ADMIN_PASSWORD`, middleware on `/admin` + `/api/checkout` GET).
- [ ] DB: Supabase `orders` table, replace `orders[]` in `src/app/api/checkout/route.ts`.
- [ ] Payments: Razorpay link or UPI QR; keep COD as fallback.
- [ ] Deploy: Vercel — connect repo, set env, `vercel --prod`.
- [ ] Content: 7 reels + 50 micro influencers (gifting, 5k–20k).
- [ ] WhatsApp: broadcast drop link, verify COD in 30 min.

## Factory note

This is the template for "idea → worth business". Same scaffold builds any vertical: swap `catalog.ts`, brand, and checkout copy. Add auth/DB/payments per vertical.
