// brain.js — static-portable Decision + Brain core for GH Pages (no business-os).
// Runs entirely in browser + Supabase (Edge Function) + localStorage的知识庫.
// Keeps Supabase-backed persist when configured, offline localStorage fallback, no Render.
// Important free reasoning models are listed from Opencode Zen (https://opencode.ai/docs/zen).
// Web external: Supabase Edge Function `chat` (cdhuqnwxprtergdavglx) via OPENCODE/HF.
// Desktop FORGE stays local-first.

import { supabase } from './supabase';

// ——— All Zen models + important free reasoning (from opencode.ai/docs/zen 2026-10-08) ———
export const IMPORTANT_FREE_REASONING = [
  'mimo-v2.6-flash-free', // Xiaomi MiMo — best free reasoning
  'mimo-v2.5-free',
  'nemotron-3-ultra-free', // NVIDIA 550B reasoning
  'nemotron-3.5-lightning-free',
  'ling-3.1-flash-free',
  'ling-3.0-flash-fin-free',
  'exo-free',
  'fledge-alpha-free',
  'space-bunny-free', // zero-retention stealth
  'longcat-2.5-preview-free', // zero-retention
  'big-pickle',
];

// Full list (90+) is in Edge Function ADVERTISED_MODELS / supabase/functions/chat; this is the short list for UI.
export const FREE_REASONING_LABELS = {
  'mimo-v2.6-flash-free': 'MiMo V2.6 Flash Free — best free reasoning ★',
  'mimo-v2.5-free': 'MiMo V2.5 Free',
  'nemotron-3-ultra-free': 'Nemotron 3 Ultra Free — long ★',
  'nemotron-3.5-lightning-free': 'Nemotron 3.5 Lightning Free',
  'ling-3.1-flash-free': 'Ling 3.1 Flash Free — code/reasoning ★',
  'ling-3.0-flash-fin-free': 'Ling 3.0 Flash Fin Free',
  'exo-free': 'Exo Free',
  'fledge-alpha-free': 'Fledge Alpha Free',
  'space-bunny-free': 'Space Bunny Free — zero-retention',
  'longcat-2.5-preview-free': 'LongCat 2.5 Preview Free — zero-retention',
  'big-pickle': 'Big Pickle — stealth free',
};

// ——— Local knowledge (offline brain) — tiny, no embeddings needed for static ———
const LS_KNOWLEDGE = 'forge_brain_knowledge_v1'; // {docs:[{id,filename,text,snippet,addedAt}], decisions:[...]}
function lsGet() {
  try { return JSON.parse(localStorage.getItem(LS_KNOWLEDGE) || '{"docs":[],"decisions":[]}'); } catch { return { docs: [], decisions: [] }; }
}
function lsSet(v) { try { localStorage.setItem(LS_KNOWLEDGE, JSON.stringify(v)); } catch {} }

// Very small keyword retrieval over locally stored snippets (static fallback when no Supabase)
function scoreDoc(query, text) {
  const q = new Set(query.toLowerCase().split(/\W+/).filter(Boolean));
  const t = text.toLowerCase();
  let s = 0; for (const w of q) if (t.includes(w)) s += w.length > 3 ? 2 : 1;
  return s;
}

function localRetrieve(query, limitChapters = 3, limitPassages = 6, snippetChars = 1000) {
  const store = lsGet();
  if (!store.docs.length) return { passages: [], citations: [] };
  const ranked = store.docs.map((d) => ({ d, score: scoreDoc(query, d.text || d.snippet || d.filename || '') }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limitChapters);
  const passages = [];
  for (const { d } of ranked.slice(0, limitPassages)) {
    const snippet = (d.text || d.snippet || '').slice(0, snippetChars);
    if (snippet) passages.push({ source: d.filename || d.id, text: snippet });
  }
  const citations = ranked.slice(0, limitChapters).map((x) => x.d.filename || x.d.id);
  return { passages, citations };
}

// ——— Supabase-backed knowledge helpers (GH Pages free) ———
// Uses conversations/messages already on cdhuqnwxprtergdavglx when VITE_SUPABASE_* present; brain_docs is optional.
export async function fetchBrainDocuments() {
  if (!supabase) return { docs: [], can_train: true };
  try {
    const { data: docs } = await supabase.from('brain_docs').select('id, filename, status, created_at').order('created_at', { ascending: false }).limit(50);
    return { docs: docs || [], can_train: true };
  } catch { return { docs: (lsGet().docs || []).map((d, i) => ({ id: d.id || `ls-${i}`, filename: d.filename, status: 'ready' })), can_train: true }; }
}

export async function uploadBrainDocument(file) {
  if (!supabase) {
    // static fallback: store text locally
    const text = file.type?.startsWith('text/') ? await file.text().catch(() => '') : '';
    const store = lsGet();
    store.docs.unshift({ id: `ls-${Date.now()}`, filename: file.name || 'document', text: text.slice(0, 8000) || `Uploaded ${file.name} (${file.size} bytes). Add more text for better grounding.`, snippet: text.slice(0, 1200), addedAt: Date.now() });
    lsSet(store);
    return { ok: true, stored: 'local' };
  }
  // Supabase path: need a bucket `brain-docs` — if missing, fallback to local
  try {
    const ext = (file.name || 'file').split('.').pop() || 'bin';
    const path = `${Date.now()}-${Math.random().toString(36).slice(2)}.${ext}`;
    const { error } = await supabase.storage.from('brain-docs').upload(path, file, { contentType: file.type || 'application/octet-stream' });
    if (error) throw new Error(error.message);
    // Edge Function ingest would chunk+store in brain_docs/brain_nodes — for now also mirror locally for zero-latency
    const text = file.type?.startsWith('text/') ? await file.text().catch(() => '') : '';
    const store = lsGet();
    store.docs.unshift({ id: path, filename: file.name, text: text.slice(0, 8000) || `Uploaded ${file.name}. Indexing via Edge Function…`, snippet: text.slice(0, 1200), addedAt: Date.now() });
    lsSet(store);
    return { ok: true, path };
  } catch (e) {
    const text = file.type?.startsWith('text/') ? await file.text().catch(() => '') : '';
    const store = lsGet();
    store.docs.unshift({ id: `ls-${Date.now()}`, filename: file.name, text: text.slice(0, 8000) || e.message, snippet: text.slice(0, 1200), addedAt: Date.now() });
    lsSet(store);
    return { ok: true, fallback: 'local', error: e.message };
  }
}

export async function deleteBrainDocument(id) {
  if (!supabase || id.startsWith('ls-')) {
    const store = lsGet(); store.docs = store.docs.filter((d) => d.id !== id); lsSet(store); return { ok: true };
  }
  try { await supabase.storage.from('brain-docs').remove([id]); } catch {}
  // Also drop local mirror
  const store = lsGet(); store.docs = store.docs.filter((d) => d.id !== id); lsSet(store); return { ok: true };
}

export async function listDecisions() {
  if (!supabase) {
    const store = lsGet();
    return { decisions: (store.decisions || []).slice(0, 50) };
  }
  try {
    const { data } = await supabase.from('brain_decisions').select('*').order('created_at', { ascending: false }).limit(50);
    return { decisions: data || [] };
  } catch { const s = lsGet(); return { decisions: s.decisions || [] }; }
}

// ——— Core: ask with auto-route ANSWER/DECIDE/PLAN + citations + next_action ———
// Pure client-side builder for static page; actual LLM is Supabase Edge Function `chat` (Zen/HF).
// This JS orchestrates retrieval + prompt + post-processing so GH Pages has real brain behavior without Python.
export function buildBrainPrompt({ question, passages, modeHint }) {
  const kb = passages.length
    ? `KNOWLEDGE (your documents — cite sources like [1], [2]):\n${passages.map((p, i) => `[${i + 1}] ${p.source}: ${p.text.slice(0, 1000)}`).join('\n---\n')}`
    : 'KNOWLEDGE: (no documents yet — upload PDFs/slides to ground answers. If not found, say so.)';

  const router = modeHint
    ? `You must respond as ${modeHint.toUpperCase()}.`
    : `Route the question automatically: ANSWER if factual lookup, DECIDE if a judgment call (pick one option with tradeoffs + recommendation + don't-follow-if + predicted_outcome), PLAN if multi-step execution (3-6 steps, Step 01 = 24-48h). Never invent facts not in KNOWLEDGE.`;

  return `You are FORGE Decision Brain. ${router}\n\n${kb}\n\nQuestion: ${question}\n\nReturn JSON only:\n{ "mode": "answer"|"decide"|"plan", "found_in_docs": boolean, "key_takeaway": string, "situation_read": string|null, "answer": string, "recommendation": string|null, "plan": string[]|null, "next_action": string, "hook": string|null, "citations": string[], "predicted_outcome": {"claim": string, "confidence": number}|null, "dont_follow_if": string|null, "signals": string[] }`;
}

// Call Edge Function `chat` via supabase-js (GH Pages free). Falls back to Zen->HF chain inside function.
export async function askBrain({ question, mode, sessionId, conversationId }) {
  const hint = String(mode || '').toLowerCase();
  const store = lsGet();
  const { passages } = localRetrieve(question);
  // Supabase GH Pages path (cdhuqnwxprtergdavglx)
  if (supabase) {
    const promptMode = hint ? ` ${hint}` : '';
    const prompt = buildBrainPrompt({ question: `${question}${hint ? ` [hint: ${hint}]` : ''}`, passages, modeHint: '' });
    const { data, error } = await supabase.functions.invoke('chat', {
      body: { message: prompt + promptMode, model: hint && IMPORTANT_FREE_REASONING.includes(hint) ? hint : undefined, conversation_id: conversationId || undefined, objective: question.slice(0, 200) },
    });
    if (error) throw new Error(error.message || 'Edge Function error');
    const raw = data?.reply ?? String(data ?? '');
    // Try structured JSON parse (brain expects JSON)
    let parsed;
    try {
      const j = JSON.parse(raw.replace(/^```(json)?|```$/g, '').trim());
      // Normalize to Decision/Brain shape expected by BrainSection/DecisionsPage
      const modeOut = (j.mode || (j.found_in_docs === false ? 'answer' : hint || 'answer')).toLowerCase();
      const key_takeaway = j.key_takeaway || j.situation_read || raw.slice(0, 180);
      const answer = j.answer || raw;
      const next_action = j.next_action || j.first_step || '';
      const citations = Array.isArray(j.citations) ? j.citations : passages.map((p) => p.source);
      // Persist to Supabase brain_decisions for history + reviews (best-effort)
      try { await supabase.from('brain_decisions').insert({ question, mode: modeOut, answer, next_action, citations, result: j }).then(() => {}); } catch {}
      const s = lsGet(); s.decisions.unshift({ id: `d-${Date.now()}`, question, mode: modeOut, answer, next_action, citations, key_takeaway, created_at: new Date().toISOString(), due: j.predicted_outcome || null }); lsSet(s);
      return {
        mode: modeOut,
        found_in_docs: !!j.found_in_docs,
        key_takeaway,
        situation_read: j.situation_read || null,
        answer,
        recommendation: j.recommendation || null,
        plan: Array.isArray(j.plan) ? j.plan : null,
        next_action,
        hook: j.hook || null,
        citations,
        predicted_outcome: j.predicted_outcome || null,
        dont_follow_if: j.dont_follow_if || null,
        credits: data?.usage?.total_tokens ?? data?.usage,
        raw,
      };
    } catch {
      // Non-JSON reply — wrap as answer
      const s2 = lsGet(); s2.decisions.unshift({ id: `d-${Date.now()}`, question, mode: 'answer', answer: raw, citations: passages.map((p) => p.source), created_at: new Date().toISOString() }); lsSet(s2);
      return { mode: 'answer', found_in_docs: passages.length > 0, key_takeaway: raw.slice(0, 180), answer: raw, citations: passages.map((p) => p.source), raw };
    }
  }
  // Offline local (no Supabase configured) — still build brain structure deterministically
  const answer = passages.length
    ? `Grounded in ${passages.length} doc(s): ${passages.map((p) => p.source).join(', ')}. ${question.slice(0, 400)}`
    : `No documents yet — upload grounding docs for cited answers. ${question.slice(0, 400)} — Download FORGE for Windows for full Decision Brain + local execution.`;
  store.decisions.unshift({ id: `d-${Date.now()}`, question, mode: hint || 'answer', answer, citations: passages.map((p) => p.source), created_at: new Date().toISOString() });
  lsSet(store);
  return { mode: hint || 'answer', found_in_docs: passages.length > 0, answer, key_takeaway: answer.slice(0, 180), citations: passages.map((p) => p.source), offline: true };
}

// Convenience: commit + log-result + reviews/due wrappers that work in GH Pages without business-os
export async function commitDecision({ decisionId, action, dueAt }) {
  if (!supabase) { const s = lsGet(); const d = s.decisions.find((x) => x.id === decisionId); if (d) d.committed = { action, due_at: dueAt }; lsSet(s); return { ok: true, offline: true }; }
  try { const r = await supabase.functions.invoke('chat', { body: { message: JSON.stringify({ commit: { decisionId, action, dueAt } }), model: 'mimo-v2.6-flash-free' } }); if (r.error) throw r.error; return r.data; } catch (e) { throw new Error(e.message); }
}

export async function logBrainResult({ decisionId, outcome, actual }) {
  if (!supabase) return { ok: true, offline: true };
  try { const r = await supabase.functions.invoke('chat', { body: { message: JSON.stringify({ logResult: { decisionId, outcome, actual } }) } }); if (r.error) throw r.error; return r.data; } catch (e) { throw new Error(e.message); }
}

export async function getReviewsDue() {
  if (!supabase) return { due: [] };
  try { const { data } = await supabase.from('brain_decisions').select('*').eq('due', true).order('created_at', { ascending: false }).limit(10); return { due: data || [] }; } catch { return { due: [] }; }
}
