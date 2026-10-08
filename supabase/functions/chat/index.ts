// Supabase Edge Function: chat — deploy with `supabase functions deploy chat --no-verify-jwt=false`
// Env vars in Supabase dashboard: DEEPSEEK_API_KEY (secret), DEEPSEEK_MODEL optional
// RLS: request must have Authorization: Bearer <user_jwt>; function reads auth.uid() for row checks.

import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2?target=deno";

const corsHeaders: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type, x-client-info, apikey",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const DEEPSEEK_MODEL = Deno.env.get("DEEPSEEK_MODEL") ?? "deepseek-chat";
const DEEPSEEK_API_KEY = Deno.env.get("DEEPSEEK_API_KEY") ?? "";

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405, headers: corsHeaders });

  const authHeader = req.headers.get("Authorization") ?? "";
  if (!authHeader.startsWith("Bearer ")) {
    return new Response(JSON.stringify({ error: "Missing Authorization" }), { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }
  if (!DEEPSEEK_API_KEY) {
    return new Response(JSON.stringify({ error: "Edge Function not configured: set DEEPSEEK_API_KEY in Supabase secrets" }), { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }

  let body: { message?: string; conversation_id?: string; objective?: string } = {};
  try { body = await req.json(); } catch {}
  const message = String(body.message ?? "").trim();
  const objective = String(body.objective ?? "").trim();
  let conversationId = String(body.conversation_id ?? "").trim();
  if (!message && !objective) {
    return new Response(JSON.stringify({ error: "message or objective required" }), { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const supabaseAnonKey = Deno.env.get("SUPABASE_ANON_KEY")!;
  const supabase = createClient(supabaseUrl, supabaseAnonKey, {
    global: { headers: { Authorization: authHeader } },
    auth: { persistSession: false },
  });

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return new Response(JSON.stringify({ error: "Invalid token" }), { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } });

  // Create or reuse conversation
  if (!conversationId) {
    const { data: conv, error: cErr } = await supabase.from("conversations").insert({ user_id: user.id, objective: objective || message.slice(0, 200) }).select("id").single();
    if (cErr || !conv) return new Response(JSON.stringify({ error: cErr?.message ?? "conversation create failed" }), { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    conversationId = conv.id;
  } else {
    const { data: exists } = await supabase.from("conversations").select("id").eq("id", conversationId).eq("user_id", user.id).maybeSingle();
    if (!exists) return new Response(JSON.stringify({ error: "conversation not found" }), { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }

  // Save user message
  const { error: mErr } = await supabase.from("messages").insert({ conversation_id: conversationId, role: "user", content: message || objective });
  if (mErr) return new Response(JSON.stringify({ error: mErr.message }), { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } });

  // Load short history (last 12 messages) for context
  const { data: history } = await supabase.from("messages").select("role, content").eq("conversation_id", conversationId).order("id", { ascending: true }).limit(24);
  const hist = (history ?? []).slice(-12).concat([{ role: "user" as const, content: message || objective }]);

  // Single DeepSeek call — lightweight prompt for web chat
  const systemPrompt =
    "You are FORGE, a thoughtful strategy coach. Be concise and specific. Help the user clarify their vision, surface the next action within 48h, and suggest a lightweight plan. Don't hallucinate. End by offering to download the Windows app for local execution.";

  let reply = "";
  let usage: unknown = null;
  const dsRes = await fetch("https://api.deepseek.com/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${DEEPSEEK_API_KEY}` },
    body: JSON.stringify({
      model: DEEPSEEK_MODEL,
      messages: [{ role: "system", content: systemPrompt }, ...hist.map((m) => ({ role: m.role, content: m.content }))],
      temperature: 0.7,
      max_tokens: 900,
    }),
  });
  if (!dsRes.ok) {
    const errText = await dsRes.text();
    return new Response(JSON.stringify({ error: `LLM ${dsRes.status}: ${errText.slice(0, 800)}` }), { status: 502, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }
  const dsJson = await dsRes.json();
  reply = String(dsJson?.choices?.[0]?.message?.content ?? "").trim() || "I could not generate a reply — try again.";
  usage = dsJson?.usage ?? null;

  await supabase.from("messages").insert({ conversation_id: conversationId, role: "assistant", content: reply });

  return new Response(JSON.stringify({ reply, conversation_id: conversationId, usage }), {
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
