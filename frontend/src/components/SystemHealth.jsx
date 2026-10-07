import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';
import {
  Activity, AlertTriangle, TrendingDown, TrendingUp, ChevronDown, ChevronRight,
  Wifi, WifiOff, ExternalLink, ArrowRight, Sparkles,
  Globe, Code, RefreshCw, Monitor, FileText, FileSpreadsheet,
  Mail, Presentation, Workflow, FileCheck, Users, Share2, BarChart3,
  Server, PenLine, Calculator, Target,
} from 'lucide-react';

// ── SystemHealthBar ── always-visible strip at top of Journey
export function SystemHealthBar({ journey }) {
  const health = journey?.system_health;
  if (!health?.has_scan) return null;

  const total = (health.at_risk_count || 0) + (health.warning_count || 0);
  if (total === 0) return null;

  return (
    <div className="mx-2 mt-2 rounded-xl border border-amber-500/20 bg-amber-50/60 px-4 py-2.5 flex items-center gap-3 text-sm animate-in fade-in">
      <AlertTriangle size={16} className="text-amber-600 shrink-0" />
      <span className="text-amber-900 font-medium">
        {health.at_risk_count > 0 && (
          <span className="text-red-600">{health.at_risk_count} at-risk</span>
        )}
        {health.at_risk_count > 0 && health.warning_count > 0 && ', '}
        {health.warning_count > 0 && (
          <span className="text-amber-600">{health.warning_count} warning{health.warning_count>1?'s':''}</span>
        )}
      </span>
      <span className="text-amber-700/70 truncate flex-1 text-xs">
        {health.brief?.split('\n')[1]?.replace(/^\d+\.\s*/, '') || 'Click for details'}
      </span>
      <span className="text-[10px] text-amber-500 font-mono cursor-pointer hover:underline shrink-0"
            onClick={() => document.getElementById('system-health-detail')?.classList.toggle('hidden')}>
        Details
      </span>
    </div>
  );
}

// ── SystemHealthDetail ── expandable panel below the bar
export function SystemHealthDetail({ journey }) {
  const health = journey?.system_health;
  if (!health?.has_scan) return null;

  return (
    <div id="system-health-detail"
         className="hidden mx-2 mb-2 rounded-xl border border-amber-200 bg-white px-4 py-3 text-sm space-y-3">
      <div className="font-medium text-xs uppercase tracking-wide text-muted">Weekly Business Health</div>

      {health.brief && (
        <pre className="text-xs text-muted whitespace-pre-wrap font-mono leading-relaxed bg-muted/50 rounded-lg p-2 max-h-48 overflow-auto">
          {health.brief}
        </pre>
      )}

      {health.at_risk?.length > 0 && (
        <div>
          <div className="text-[11px] uppercase tracking-wide text-red-600 font-medium mb-1.5">At Risk</div>
          <div className="space-y-1">
            {health.at_risk.map(f => (
              <div key={f.function} className="flex items-center justify-between text-xs">
                <span className="capitalize text-muted">{f.function.replace(/_/g, ' ')}</span>
                <span className="font-mono text-red-600">{f.health}/100</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {health.warnings?.length > 0 && (
        <div>
          <div className="text-[11px] uppercase tracking-wide text-amber-600 font-medium mb-1.5">Warnings</div>
          <div className="space-y-1">
            {health.warnings.map(f => (
              <div key={f.function} className="flex items-center justify-between text-xs">
                <span className="capitalize text-muted">{f.function.replace(/_/g, ' ')}</span>
                <span className="font-mono text-amber-600">{f.health}/100</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <RootCauseButton journey={journey} />
        <OpportunityButton journey={journey} />
      </div>
    </div>
  );
}

// ── RootCausePanel ── when a symptom is detected in the conversation
function RootCauseButton({ journey }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  // Request a causal tree analysis for the at-risk function.
  const analyze = useCallback(async () => {
    setLoading(true);
    try {
      const func = journey?.system_health?.at_risk?.[0]?.function || 'sales';
      const r = await api.post('/system/root-cause', { symptom: func, max_depth: 2 });
      setResult(r.data);
      setOpen(true);
    } catch (_) {} finally { setLoading(false); }
  }, [journey]);

  return (
    <div className="flex-1">
      <button onClick={analyze} disabled={loading}
              className="w-full rounded-lg bg-amber-100 hover:bg-amber-200 px-3 py-1.5 text-xs font-medium text-amber-800 flex items-center gap-1 justify-center">
        {loading ? <Sparkles size={12} className="animate-spin" /> : <Activity size={12} />}
        Root Cause
      </button>
      {open && result?.causal_tree && (
        <div className="mt-2 rounded-lg border bg-white p-3 text-xs max-h-64 overflow-auto">
          <TreeView node={result.causal_tree} depth={0} />
        </div>
      )}
    </div>
  );
}

// Recursive expandable node for the causal tree display.
function TreeView({ node, depth }) {
  const [open, setOpen] = useState(depth < 2);
  const color = node.status === 'at_risk' ? 'text-red-600' : node.status === 'warning' ? 'text-amber-600' : 'text-emerald-600';
  const hasChildren = node.children?.length > 0;

  return (
    <div>
      <div className="flex items-center gap-1 cursor-pointer" onClick={() => setOpen(!open)} style={{ paddingLeft: depth * 12 }}>
        {hasChildren && (open ? <ChevronDown size={12} /> : <ChevronRight size={12} />)}
        <span className="capitalize">{node.label || node.function}</span>
        <span className={`font-mono ml-auto ${color}`}>{node.health}/100</span>
      </div>
      {open && node.failure_modes?.slice(0, 2).map((fm, i) => (
        <div key={i} className="text-[10px] text-muted ml-6 mt-0.5">· {fm.slice(0, 80)}</div>
      ))}
      {open && hasChildren && node.children.map((child, i) => (
        <TreeView key={i} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

// Button that fetches adjacent leverage opportunities.
function OpportunityButton({ journey }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  // Fetch the opportunities list from the backend.
  const scan = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/system/opportunities');
      setResult(r.data);
    } catch (_) {} finally { setLoading(false); }
  }, []);

  return (
    <div className="flex-1">
      <button onClick={scan} disabled={loading}
              className="w-full rounded-lg bg-emerald-100 hover:bg-emerald-200 px-3 py-1.5 text-xs font-medium text-emerald-800 flex items-center gap-1 justify-center">
        {loading ? <Sparkles size={12} className="animate-spin" /> : <TrendingUp size={12} />}
        Opportunities
      </button>
      {result?.adjacent_leverage?.length > 0 && (
        <div className="mt-2 rounded-lg border bg-white p-2 text-xs space-y-1">
          {result.adjacent_leverage.slice(0, 3).map((opp, i) => (
            <div key={i} className="text-muted">
              <span className="font-medium text-emerald-700">{opp.source}</span> → {opp.target}: {opp.pattern?.slice(0, 80)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── ConnectionPrompt ── inline suggestion to connect tools
export function ConnectionPrompt({ function: func }) {
  const [tools, setTools] = useState(null);
  const [connecting, setConnecting] = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!func || loaded) return;
    (async () => {
      try {
        const r = await api.get(`/execution/connections/suggest/${func}`);
        setTools(r.data.tools?.filter(t => !t.connected)?.slice(0, 3));
      } catch (_) {} finally { setLoaded(true); }
    })();
  }, [func, loaded]);

  if (!tools?.length) return null;

  const connect = async (toolkit) => {
    setConnecting(toolkit);
    try {
      const r = await api.post('/execution/connections/connect', { toolkit });
      if (r.data.auth_url) window.open(r.data.auth_url, '_blank');
      // Poll for completion
      setTimeout(async () => {
        try {
          await api.post('/execution/connections/complete', { toolkit });
          setTools(prev => prev.filter(t => t.toolkit !== toolkit));
        } catch (_) {}
        setConnecting(null);
      }, 5000);
    } catch (_) { setConnecting(null); }
  };

  return (
    <div className="mx-2 mb-2 rounded-xl border border-blue-200 bg-blue-50/50 px-4 py-2.5 animate-in fade-in">
      <div className="flex items-center gap-2 mb-2">
        <Wifi size={14} className="text-blue-600" />
        <span className="text-xs font-medium text-blue-800">
          Connect tools to auto-diagnose {func.replace(/_/g, ' ')}
        </span>
      </div>
      <div className="flex gap-2 flex-wrap">
        {tools.map(t => (
          <button key={t.toolkit} onClick={() => connect(t.toolkit)} disabled={!!connecting}
                  className="rounded-lg bg-white border px-2.5 py-1 text-[11px] font-medium text-blue-700 hover:bg-blue-100 flex items-center gap-1">
            {connecting === t.toolkit ? (
              <Sparkles size={11} className="animate-spin" />
            ) : (
              <Wifi size={11} />
            )}
            {t.toolkit}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── CapabilityPanel ── universal builder for 15 capability types
const CAPABILITY_ICONS = {
  website: Globe, report: FileText, email_campaign: Mail, investor_deck: Presentation,
  automation: Workflow, contract: FileCheck, job_description: Users,
  social_campaign: Share2, product_spec: Target, onboarding_doc: Users,
  dashboard: BarChart3, api_endpoint: Server, blog_post: PenLine,
  financial_model: Calculator, strategy_doc: Target,
};

// Universal panel for building and iterating on capabilities.
export function CapabilityPanel() {
  const [description, setDescription] = useState('');
  const [capType, setCapType] = useState('');
  const [building, setBuilding] = useState(false);
  const [build, setBuild] = useState(null);
  const [feedback, setFeedback] = useState('');
  const [iterating, setIterating] = useState(false);
  const [open, setOpen] = useState(false);
  const [capabilities, setCapabilities] = useState(null);

  useEffect(() => {
    if (open && !capabilities) {
      api.get('/capabilities').then(r => setCapabilities(r.data.capabilities)).catch(() => {});
    }
  }, [open, capabilities]);

  // Auto-route on description change
  useEffect(() => {
    if (description.length > 20) {
      api.post('/capabilities/route', { message: description })
        .then(r => { if (r.data.routed_to) setCapType(r.data.routed_to); })
        .catch(() => {});
    }
  }, [description]);

  // Kick off a capability build with the description.
  const doBuild = async () => {
    if (!description.trim() || building) return;
    setBuilding(true);
    setBuild(null);
    try {
      const r = await api.post('/capabilities/build', {
        description: description.trim(),
        type: capType || undefined,
      });
      setBuild(r.data);
    } catch (e) {
      setBuild({ error: e?.response?.data?.detail || 'Build failed' });
    } finally { setBuilding(false); }
  };

  // Apply feedback to iterate on an existing build.
  const doIterate = async () => {
    if (!feedback.trim() || !build?.build_id || iterating) return;
    setIterating(true);
    try {
      const r = await api.post('/capabilities/iterate', { build_id: build.build_id, feedback: feedback.trim() });
      setBuild(r.data);
      setFeedback('');
    } catch (e) {
      setBuild(prev => ({ ...prev, error: e?.response?.data?.detail || 'Iteration failed' }));
    } finally { setIterating(false); }
  };

  const CapIcon = CAPABILITY_ICONS[build?.type] || Sparkles;
  const TypeIcon = CAPABILITY_ICONS[capType] || Sparkles;

  return (
    <div className="mx-2 mb-2 rounded-xl border bg-surface px-4 py-3 animate-in fade-in">
      <button onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full text-left">
        <Sparkles size={14} className="text-primary" />
        <span className="text-sm font-medium">Build Anything</span>
        <span className="text-[10px] text-muted ml-2">websites · reports · decks · campaigns · docs</span>
        <span className="ml-auto">{open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</span>
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {!build && (
            <>
              <textarea value={description} onChange={e => setDescription(e.target.value)}
                placeholder="What do you need? e.g. 'A landing page for my D2C brand' or 'An investor deck for Series A' or 'A job description for a senior engineer'..."
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm min-h-[80px] resize-none"
                rows={3} />
              {capType && (
                <div className="flex items-center gap-1.5 text-xs text-muted">
                  <TypeIcon size={12} />
                  <span>Detected: <span className="font-medium text-foreground">{capabilities?.[capType]?.label || capType.replace(/_/g, ' ')}</span></span>
                  {capabilities?.[capType]?.label && <span className="text-muted">— {capabilities[capType].label}</span>}
                </div>
              )}
              <button onClick={doBuild} disabled={building || !description.trim()}
                className="w-full rounded-lg bg-primary text-primary-foreground px-3 py-2 text-sm font-medium flex items-center gap-2 justify-center">
                {building ? <Sparkles size={14} className="animate-spin" /> : <Globe size={14} />}
                {building ? 'Building...' : 'Build & Deploy'}
              </button>
            </>
          )}

          {build?.url && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <CapIcon size={14} className="text-emerald-600" />
                <span className="text-emerald-700 font-medium">{build.label}: </span>
                <a href={build.url} target="_blank" rel="noopener"
                  className="text-primary underline truncate">{build.url}</a>
                <ExternalLink size={12} className="text-muted" />
              </div>
              {build.type === 'website' && (
                <div className="rounded-lg border bg-muted/50 max-h-48 overflow-auto">
                  <iframe src={build.url} className="w-full min-h-[200px] border-0"
                    title="Preview" sandbox="allow-scripts allow-same-origin" />
                </div>
              )}
              <div className="flex gap-2">
                <input value={feedback} onChange={e => setFeedback(e.target.value)}
                  placeholder="Changes? 'Make it blue, add pricing section'"
                  className="flex-1 rounded-lg border bg-background px-2 py-1.5 text-xs" />
                <button onClick={doIterate} disabled={iterating || !feedback.trim()}
                  className="rounded-lg bg-secondary px-3 py-1.5 text-xs font-medium flex items-center gap-1">
                  {iterating ? <RefreshCw size={12} className="animate-spin" /> : <Code size={12} />}
                  Update
                </button>
              </div>
            </div>
          )}

          {build?.status === 'complete' && !build?.url && (
            <div className="text-xs text-emerald-700 bg-emerald-50 rounded-lg p-3">
              <CapIcon size={14} className="mb-1 text-emerald-600" />
              <span className="font-medium">{build.label} ready!</span>
              <span className="text-muted ml-2">{build.deploy_note || 'Deployed to ' + build.deploy_platform}</span>
            </div>
          )}

          {build?.error && (
            <div className="text-xs text-red-600 bg-red-50 rounded-lg p-2">{build.error}</div>
          )}
        </div>
      )}
    </div>
  );
}
