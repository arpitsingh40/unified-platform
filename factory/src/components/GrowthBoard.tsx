"use client";
// GrowthBoard — kanban for 10× loops: backlog → running → verify → learned
// Reads /api/growth if business-os is up; falls back to static blueprint loops.

import { useEffect, useState } from "react";

type Loop = { name: string; cadence: string; owner: string; moves: string[]; handler: string; metric: string };
type Board = { headline: string; loops: Loop[]; kpis: string[]; cadence: string };

const FALLBACK: Board = {
  headline: "10× in 12 months — weekly drops + UGC flywheel + COD→repeat",
  loops: [
    { name: "weekly_drop", cadence: "weekly", owner: "Product", moves: ["Ship 6 SKUs every Monday", "Tease on IG 48h before", "Email waitlist at drop"], handler: "GITHUB", metric: "Orders" },
    { name: "ugc_flywheel", cadence: "continuous", owner: "Growth", moves: ["Seed 15 micro influencers / week", "3 best UGC → paid reels", "Retarget with COD offer"], handler: "GMAIL", metric: "Revenue" },
    { name: "retention", cadence: "daily", owner: "Ops", moves: ["Verify COD in 30 min", "Ship in 48h + review ask", "Nudge repeat at day 14"], handler: "manual", metric: "Repeat %" },
    { name: "pricing_test", cadence: "weekly", owner: "Growth", moves: ["Bundle 2 at ₹1,999", "Free-ship A/B", "Raise compareAt on bestsellers"], handler: "manual", metric: "AOV" },
  ],
  kpis: ["Revenue","Orders","AOV","Repeat %","CAC","LTV"],
  cadence: "weekly",
};

export default function GrowthBoard() {
  const [board, setBoard] = useState<Board>(FALLBACK);
  useEffect(() => {
    fetch("/api/growth").then(r => r.json()).then(d => { if (d?.headline && d?.loops) setBoard(d); }).catch(() => {});
  }, []);
  return (
    <div className="border bg-white">
      <div className="border-b px-4 py-3 flex items-center justify-between">
        <div>
          <div className="font-black tracking-tight">GROWTH BOARD — 10× ENGINE</div>
          <div className="text-xs text-black/50">{board.headline} · cadence: {board.cadence}</div>
        </div>
        <div className="text-xs text-black/40">KPIs: {board.kpis.join(" · ")}</div>
      </div>
      <div className="grid md:grid-cols-2 gap-3 p-3">
        {board.loops.map(l => (
          <div key={l.name} className="border p-3">
            <div className="flex items-center justify-between">
              <div className="font-bold text-sm">{l.name}</div>
              <span className="text-[11px] tracking-widest border px-2 py-0.5">{l.cadence} · {l.owner}</span>
            </div>
            <ul className="mt-2 list-disc list-inside text-sm text-black/70 space-y-1">
              {l.moves.map(m => <li key={m}>{m}</li>)}
            </ul>
            <div className="mt-2 text-xs">handler: <span className="font-mono border px-1">{l.handler}</span> · metric: <b>{l.metric}</b></div>
          </div>
        ))}
      </div>
      <div className="px-4 py-2 text-xs text-black/40 border-t">
        Source: <span className="font-mono">business-os/growth_engine.py</span> (LLM) + <span className="font-mono">factory/blueprints/*</span> (registry). Wire to <span className="font-mono">POST /api/v1/invoke</span> for kernel-gated execution.
      </div>
    </div>
  );
}
