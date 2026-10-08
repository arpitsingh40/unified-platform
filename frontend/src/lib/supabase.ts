// Supabase client for GH Pages free tier — only used when VITE_TARGET=web.
// Uses Vite env VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY.
// If those are empty, web build falls back to demo-mode (no DB) + download CTA.
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const isSupabaseConfigured: boolean = !!(url && anonKey);

// Lazy singleton — null in desktop/dev or if not configured
export let supabase: SupabaseClient | null = null;
if (isSupabaseConfigured) {
  supabase = createClient(url!, anonKey!);
}

// Types for our free-tier schema
export type Conversation = {
  id: string;
  user_id: string;
  objective: string;
  title?: string | null;
  created_at: string;
  updated_at: string;
};
export type MessageRow = {
  id: number;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
};

// Edge Function response
export type ChatInvokeResult = {
  reply: string;
  conversation_id: string;
  usage?: { prompt_tokens?: number; completion_tokens?: number };
};
