import { NextRequest, NextResponse } from "next/server";

// Demo persistence: in-memory + logs to console/file. Replace with DB (Supabase/PlanetScale) for prod.
type Order = { orderId: string; at: string; name: string; phone: string; address: string; pincode: string; pay: string; items: unknown[]; total: number };
const orders: Order[] = [];

export async function POST(req: NextRequest) {
  const body = await req.json();
  const orderId = "DRIFT-" + Math.random().toString(36).slice(2, 8).toUpperCase() + "-" + Date.now().toString(36).toUpperCase();
  const order: Order = {
    orderId, at: new Date().toISOString(),
    name: body.name || "", phone: body.phone || "", address: body.address || "",
    pincode: body.pincode || "", pay: body.pay || "COD",
    items: body.items || [], total: body.total || 0
  };
  orders.push(order);
  console.log("[DRIFT ORDER]", orderId, order.phone, order.total);
  // In prod: write to DB + send WhatsApp via provider
  return NextResponse.json({ ok: true, orderId });
}

export async function GET() {
  return NextResponse.json({ count: orders.length, orders: orders.slice(-20).reverse() });
}
