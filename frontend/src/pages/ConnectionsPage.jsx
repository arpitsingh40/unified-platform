import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { toast } from 'sonner';
import { TopBar } from '../components/TopBar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import {
  Loader2, Lock, Plug, Unplug, Search, ExternalLink,
  CheckCircle2, Link2, Wifi, ArrowLeft, Zap
} from 'lucide-react';

// Group business functions by category
const functionGroups = {
  'Sales & Revenue': ['sales', 'customer_success'],
  'Marketing & Growth': ['marketing', 'growth', 'brand'],
  'Product & Engineering': ['product', 'technology', 'data'],
  'Finance & Operations': ['finance', 'operations'],
  'People': ['hr', 'leadership'],
  'Strategy': ['strategy', 'vision', 'partnerships'],
};

// Display labels for function keys
const functionLabels = {
  sales: 'Sales', marketing: 'Marketing', product: 'Product',
  technology: 'Technology', finance: 'Finance', operations: 'Operations',
  hr: 'HR', customer_success: 'Customer Success', data: 'Data & Analytics',
  growth: 'Growth', brand: 'Brand', partnerships: 'Partnerships',
  vision: 'Vision', strategy: 'Strategy', leadership: 'Leadership',
};

// Tool connection management page
export default function ConnectionsPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [denied, setDenied] = useState(false);
  const [integrations, setIntegrations] = useState([]);
  const [search, setSearch] = useState('');
  const [connecting, setConnecting] = useState(null);
  const [authUrl, setAuthUrl] = useState(null);

  // Load current tool connections
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/execution/connections');
      setIntegrations(r.data?.connected_list || []);
    } catch (e) {
      if (e?.response?.status === 403) setDenied(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Start OAuth for a toolkit
  const connectTool = async (toolkit) => {
    setConnecting(toolkit);
    try {
      const r = await api.post('/execution/connections/connect', {
        toolkit,
        redirect_uri: window.location.origin + '/app/connections',
      });
      if (r.data?.auth_url) {
        setAuthUrl({ toolkit, url: r.data.auth_url });
      } else if (r.data?.status === 'already_connected') {
        await load();
      }
    } catch (e) { /* api interceptor handles */ }
    finally { setConnecting(null); }
  };

  // Poll until the OAuth connection lands
  const completeConnection = async (toolkit) => {
    try {
      // Poll until the connection is confirmed
      for (let i = 0; i < 6; i++) {
        await new Promise(r => setTimeout(r, 3000));
        const check = await api.get('/execution/connections');
        const found = (check.data?.connected_list || []).find(c => c.toolkit === toolkit && c.connected);
        if (found) {
          await load();
          return;
        }
      }
      toast.warning(`${toolkit} may still be connecting. Try refreshing.`);
      await load();
    } catch (e) { /* handled */ }
  };

  // Disconnect a connected toolkit
  const disconnectTool = async (toolkit) => {
    setConnecting(toolkit);
    try {
      await api.post('/execution/connections/disconnect', { toolkit });
      await load();
    } catch (e) { /* handled */ }
    finally { setConnecting(null); }
  };

  const filtered = search
    ? integrations.filter(i =>
        i.toolkit?.toLowerCase().includes(search.toLowerCase()) ||
        i.name?.toLowerCase().includes(search.toLowerCase()) ||
        i.category?.toLowerCase().includes(search.toLowerCase()))
    : integrations;

  if (loading) {
    return (
      <div className="min-h-screen">
        <TopBar title="Connections" backTo="/app" />
        <div className="max-w-4xl mx-auto px-4 py-10 space-y-4">
          <div className="h-8 w-48 animate-pulse rounded-md bg-primary/10" />
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded-2xl bg-primary/10" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (denied) {
    return (
      <div className="min-h-screen">
        <TopBar title="Connections" backTo="/app" />
        <div data-testid="connections-denied" className="max-w-md mx-auto text-center py-24 px-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl border mb-4 text-muted">
            <Lock size={20} />
          </div>
          <h2 className="font-display text-xl">Workspace owner only</h2>
          <p className="text-sm text-muted mt-2">
            Only the workspace owner can connect tools.
          </p>
          <Button variant="secondary" className="rounded-xl mt-6" onClick={() => navigate('/app')}>
            Go back
          </Button>
        </div>
      </div>
    );
  }

  const connected = integrations.filter(i => i.connected);

  return (
    <div className="min-h-screen">
      <TopBar title="Connections" backTo="/app/business-os" />
      <main data-testid="connections-page" className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

        {/* OAuth popup */}
        {authUrl && (
          <div className="rounded-2xl border border-blue-200 bg-blue-50/50 p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-sm font-medium flex items-center gap-1.5">
                  <Link2 size={14} /> Connect {authUrl.toolkit}
                </h3>
                <p className="text-xs text-muted mt-1.5">
                  A new window opened for OAuth. After authorizing, click "I've connected it" below.
                </p>
              </div>
              <Button
                size="sm"
                variant="secondary"
                className="rounded-lg shrink-0"
                onClick={() => { setAuthUrl(null); }}
              >
                Cancel
              </Button>
            </div>
            <div className="flex items-center gap-2 mt-3">
              <Button size="sm" className="rounded-lg" onClick={() => window.open(authUrl.url, '_blank')}>
                Open OAuth <ExternalLink size={12} className="ml-1" />
              </Button>
              <Button size="sm" variant="secondary" className="rounded-lg"
                onClick={() => { completeConnection(authUrl.toolkit); setAuthUrl(null); }}>
                <CheckCircle2 size={13} className="mr-1" /> I've connected it
              </Button>
            </div>
          </div>
        )}

        {/* Header */}
        <div>
          <h1 className="font-display text-2xl">Tool Connections</h1>
          <p className="text-sm text-muted mt-1.5">
            Connect tools your business uses. Once connected, agents can execute actions through them automatically.
          </p>
        </div>

        {/* Connected tools */}
        {connected.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Wifi size={15} strokeWidth={1.75} className="text-emerald-600" />
              <h2 className="text-sm font-medium">Connected ({connected.length})</h2>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {connected.map((t) => (
                <div key={t.toolkit} data-testid={`connection-${t.toolkit}`}
                  className="rounded-2xl border border-emerald-200 bg-emerald-50/30 p-4 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 size={14} className="text-emerald-600 shrink-0" />
                      <span className="text-sm font-medium truncate capitalize">{t.name || t.toolkit}</span>
                    </div>
                    <p className="text-[11px] text-muted mt-1">{t.tool_count || 0} tools available</p>
                  </div>
                  <Button
                    data-testid={`disconnect-${t.toolkit}`}
                    variant="ghost"
                    size="sm"
                    className="rounded-lg mt-2 text-red-600 hover:text-red-700 hover:bg-red-50 text-xs"
                    onClick={() => disconnectTool(t.toolkit)}
                    disabled={connecting === t.toolkit}
                  >
                    {connecting === t.toolkit ? <Loader2 size={12} className="animate-spin mr-1" /> : <Unplug size={12} className="mr-1" />}
                    Disconnect
                  </Button>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Quick-connect essentials */}
        {connected.length === 0 && (
          <section className="rounded-2xl border bg-surface p-5">
            <div className="flex items-center gap-2 mb-3">
              <Zap size={15} strokeWidth={1.75} />
              <h2 className="text-sm font-medium">Quick start — connect essentials</h2>
            </div>
            <p className="text-xs text-muted mb-4">
              These are the most common tools founders connect first. Click to start OAuth.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { tk: 'gmail', name: 'Gmail', desc: 'Send emails, follow-ups' },
                { tk: 'notion', name: 'Notion', desc: 'Create docs, specs' },
                { tk: 'slack', name: 'Slack', desc: 'Team notifications' },
                { tk: 'google_calendar', name: 'Calendar', desc: 'Schedule meetings' },
                { tk: 'stripe', name: 'Stripe', desc: 'Payments, invoices' },
                { tk: 'hubspot', name: 'HubSpot', desc: 'CRM, deal tracking' },
                { tk: 'github', name: 'GitHub', desc: 'Code, issues, PRs' },
                { tk: 'linkedin', name: 'LinkedIn', desc: 'Outreach, posts' },
              ].map(({ tk, name, desc }) => (
                <div key={tk} data-testid={`quick-connect-${tk}`}
                  className="rounded-xl border bg-background p-4 flex flex-col items-center text-center gap-2 hover:border-emerald-300 transition-colors">
                  <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-sm font-medium">
                    {name[0]}
                  </div>
                  <span className="text-sm font-medium">{name}</span>
                  <p className="text-[11px] text-muted leading-tight">{desc}</p>
                  <Button
                    size="sm"
                    variant="secondary"
                    className="rounded-lg mt-auto text-xs"
                    onClick={() => connectTool(tk)}
                    disabled={connecting === tk}
                  >
                    {connecting === tk ? <Loader2 size={12} className="animate-spin mr-1" /> : <Plug size={12} className="mr-1" />}
                    Connect
                  </Button>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Search */}
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <Input
            data-testid="connections-search"
            placeholder="Search 1,403 integrations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 rounded-xl"
          />
        </div>

        {/* Search results */}
        {search && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {filtered.length === 0 && (
              <p className="text-sm text-muted col-span-full py-8 text-center">
                No integrations match "{search}"
              </p>
            )}
            {filtered.map((t) => (
              <div key={t.toolkit} data-testid={`integration-${t.toolkit}`}
                className={`rounded-2xl border p-4 flex flex-col justify-between ${
                  t.connected ? 'border-emerald-200 bg-emerald-50/30' : 'bg-surface'
                }`}>
                <div>
                  <div className="flex items-center gap-2">
                    {t.connected && <CheckCircle2 size={13} className="text-emerald-600 shrink-0" />}
                    <span className="text-sm font-medium truncate capitalize">{t.name || t.toolkit}</span>
                  </div>
                  <p className="text-[11px] text-muted mt-1 line-clamp-2">{t.description || ''}</p>
                  <p className="text-[10px] text-muted/70 mt-1">{t.tool_count || 0} tools · {t.category || ''}</p>
                </div>
                <Button
                  data-testid={`connect-btn-${t.toolkit}`}
                  size="sm"
                  variant={t.connected ? 'secondary' : 'default'}
                  className="rounded-lg mt-2 text-xs"
                  onClick={() => t.connected ? disconnectTool(t.toolkit) : connectTool(t.toolkit)}
                  disabled={connecting === t.toolkit}
                >
                  {connecting === t.toolkit
                    ? <Loader2 size={12} className="animate-spin mr-1" />
                    : t.connected ? <Unplug size={12} className="mr-1" /> : <Plug size={12} className="mr-1" />}
                  {t.connected ? 'Disconnect' : 'Connect'}
                </Button>
              </div>
            ))}
          </div>
        )}

        {/* All connected tools summary when not searching */}
        {!search && connected.length > 0 && (
          <section>
            <h2 className="text-sm font-medium mb-3 flex items-center gap-2">
              <Search size={15} strokeWidth={1.75} />
              Browse &amp; search 1,403 integrations
            </h2>
            <p className="text-xs text-muted mb-3">
              Use search above to find any tool. Connect to enable autonomous execution.
            </p>
          </section>
        )}

        {/* Back to Business OS */}
        <div className="pt-4 border-t">
          <Button variant="secondary" className="rounded-xl" onClick={() => navigate('/app/business-os')}>
            <ArrowLeft size={14} className="mr-1.5" /> Back to Business OS
          </Button>
        </div>

      </main>
    </div>
  );
}
