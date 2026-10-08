import { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { Monitor, ExternalLink, Globe, Play, Copy, Terminal, FolderOpen, ArrowRight, Eye, EyeOff, Image as ImageIcon } from 'lucide-react';
import { isDesktop, browserNavigate, browserEval, shellRun, openPath, ensureForgeRoot, onDesktopEvent } from '../lib/desktop';
import { api } from '../lib/api';

export default function BrowserPage() {
  const [url, setUrl] = useState('https://www.google.com');
  const [history, setHistory] = useState([]);
  const [forgeRoot, setForgeRoot] = useState('');
  const [js, setJs] = useState("document.title");
  const [shellCmd, setShellCmd] = useState('dir');
  const [shellOut, setShellOut] = useState('');
  const [showRunner, setShowRunner] = useState(false);

  useEffect(() => {
    if (!isDesktop) return;
    ensureForgeRoot().then(setForgeRoot).catch(() => {});
    const off1 = onDesktopEvent('forge:browser-navigate', (e) => setUrl(String(e.payload))).then((fn) => fn);
    return () => { off1.then((fn) => fn && fn()); };
  }, []);

  const go = async () => {
    if (!isDesktop) { window.open(url, '_blank'); return; }
    try {
      await browserNavigate(url);
      toast.success('Agent browser → ' + url);
      // emit for Rust side to show window
      try { const { emit } = await import('@tauri-apps/api/event'); await emit('forge:show-browser', url); } catch {}
      setHistory((h) => [url, ...h].slice(0, 20));
    } catch (e) { toast.error(String(e)); }
  };

  const toggleBrowser = async () => {
    if (!isDesktop) return;
    try {
      const { emit } = await import('@tauri-apps/api/event');
      // show if hidden, the Rust handler will show agent-browser
      await emit('forge:show-browser', url);
    } catch (e) { toast.error(String(e)); }
  };

  const hideBrowser = async () => {
    if (!isDesktop) return;
    try { const { emit } = await import('@tauri-apps/api/event'); await emit('forge:hide-browser', ''); } catch {}
  };

  const evalJs = async () => {
    if (!isDesktop) return toast.error('Desktop only');
    try {
      await browserEval(js);
      toast.success('JS dispatched to agent browser');
    } catch (e) { toast.error(String(e)); }
  };

  const runShell = async () => {
    if (!isDesktop) return toast.error('Desktop only');
    setShellOut('Running…');
    try {
      const out = await shellRun(shellCmd);
      setShellOut(String(out).slice(0, 8000));
      toast.success('Done');
    } catch (e) { setShellOut(String(e)); toast.error('Shell failed'); }
  };

  if (!isDesktop) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10">
        <div className="rounded-2xl border border-hairline p-6 bg-surface">
          <p className="text-sm text-muted">Agent Browser + Desktop execution are available in the <b>FORGE desktop app</b> (Tauri). This web build has no local access. Download the .exe to use them.</p>
          <a href="/api/health" className="text-xs text-accent mt-3 inline-block">API health OK? → /api/health</a>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-xl flex items-center gap-2"><Monitor size={18} /> Agent Browser & Desktop</h1>
        <span className="text-[11px] px-2 py-1 rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">Local execution</span>
      </div>
      <p className="text-xs text-muted -mt-3">Browser & shell run <b>on this machine only</b>. Agents drive the Agent Browser WebView locally. Only LLM API (DeepSeek/Tavily) leaves the device. Sandbox: <code className="px-1.5 py-0.5 rounded bg-black/5 text-[11px]">{forgeRoot || '~/Documents/FORGE'}</code></p>

      {/* Browser controls */}
      <div className="rounded-2xl border border-hairline bg-surface p-4 space-y-3">
        <div className="flex items-center gap-2 text-xs font-medium"><Globe size={14} /> Agent Browser (second WebView — agents control it, you can pop it)</div>
        <div className="flex gap-2">
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." className="flex-1 h-9 rounded-xl border border-hairline bg-background px-3 text-sm" />
          <button onClick={go} className="h-9 px-4 rounded-xl bg-accent text-white text-sm inline-flex items-center gap-1.5"><Play size={14} /> Go</button>
        </div>
        <div className="flex gap-2">
          <button onClick={toggleBrowser} className="h-8 px-3 rounded-xl border border-hairline text-xs inline-flex items-center gap-1.5"><Eye size={13} /> Show browser window</button>
          <button onClick={hideBrowser} className="h-8 px-3 rounded-xl border border-hairline text-xs inline-flex items-center gap-1.5"><EyeOff size={13} /> Hide</button>
          <button onClick={() => { if (history[0]) setUrl(history[0]); }} className="h-8 px-3 rounded-xl border border-hairline text-xs">↩ Last</button>
        </div>
        <details className="text-xs">
          <summary className="cursor-pointer text-muted">History</summary>
          <ul className="mt-2 space-y-1">
            {history.map((u, i) => <li key={i} className="flex items-center gap-2"><button onClick={() => setUrl(u)} className="text-accent hover:underline truncate">{u}</button><button onClick={() => { setUrl(u); go(); }} className="text-[11px] border rounded px-1.5 py-0.5">Go</button></li>)}
          </ul>
        </details>
        <div className="space-y-2">
          <div className="text-[11px] text-muted">Eval JS in agent browser (agents use this; you can test):</div>
          <div className="flex gap-2">
            <input value={js} onChange={(e) => setJs(e.target.value)} placeholder="document.title or any JS" className="flex-1 h-8 rounded-xl border border-hairline bg-background px-3 text-xs font-mono" />
            <button onClick={evalJs} className="h-8 px-3 rounded-xl bg-surface-2 border border-hairline text-xs">Eval</button>
          </div>
          <p className="text-[11px] text-muted">Examples: <code>document.title</code> · <code>document.documentElement.outerHTML.slice(0,2000)</code> · <code>window.scrollTo(0, 500)</code></p>
        </div>
      </div>

      {/* Shell + FS */}
      <div className="rounded-2xl border border-hairline bg-surface p-4 space-y-3">
        <div className="flex items-center gap-2 text-xs font-medium"><Terminal size={14} /> Shell (sandboxed to FORGE) + Open file</div>
        <div className="flex gap-2">
          <input value={shellCmd} onChange={(e) => setShellCmd(e.target.value)} placeholder="dir / dir /B, type file.txt, python --version" className="flex-1 h-9 rounded-xl border border-hairline bg-background px-3 text-sm font-mono" />
          <button onClick={runShell} className="h-9 px-4 rounded-xl bg-accent text-white text-sm inline-flex items-center gap-1.5"><ArrowRight size={14} /> Run</button>
        </div>
        <div className="flex gap-2">
          <button onClick={async () => { const r = await ensureForgeRoot(); setForgeRoot(r); toast.success(r); }} className="h-8 px-3 rounded-xl border border-hairline text-xs inline-flex items-center gap-1"><FolderOpen size={13} /> Reveal FORGE folder</button>
          <button onClick={async () => { try { await openPath(forgeRoot); } catch (e) { toast.error(String(e)); } }} className="h-8 px-3 rounded-xl border border-hairline text-xs">Open in Explorer</button>
          <button onClick={() => setShowRunner((v) => !v)} className="h-8 px-3 rounded-xl border border-hairline text-xs">{showRunner ? 'Hide output' : 'Show output'}</button>
        </div>
        {showRunner && <pre className="max-h-64 overflow-auto rounded-xl bg-black text-white p-3 text-xs font-mono whitespace-pre-wrap">{shellOut || '(no output yet)'}</pre>}
        <p className="text-[11px] text-muted">Agents call these via <code>POST /api/desktop/*</code> which tunnels to Tauri invoke. Only <code>~/Documents/FORGE</code>, <code>%APPDATA%/forge</code>, <code>%TEMP%</code> are writable. <code>Ctrl+Shift+F</code> summons FORGE from anywhere.</p>
      </div>

      <div className="rounded-2xl border border-hairline bg-accent/5 p-4 text-xs leading-relaxed">
        <b>Execution model:</b> Agents run locally (FS, shell, browser). Only <code>DEEPSEEK_API_KEY</code> / Tavily / Parallel calls leave the device. No cloud browser, no cloud FS. If backend is unreachable, check that <code>business-os</code> is on <code>:8000</code> — desktop spawns it automatically in dev.
      </div>
    </div>
  );
}
