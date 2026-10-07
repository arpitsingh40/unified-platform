import { useState, useEffect } from 'react';
import { ShieldCheck, AlertTriangle, CheckCircle2, Users, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { api } from '../lib/api';

// Collapsible bar showing SALAAR threats and pending actions.
export function SalaarBrief() {
  const [brief, setBrief] = useState(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.get('/salaar/brief').then(r => {
      setBrief(r.data);
    }).catch(() => {
      // Not in an org or SALAAR not available — silently hide
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return null;
  if (!brief || (!brief.threats_active && !brief.actions_pending)) return null;

  return (
    <div className="border-b border-hairline/60 bg-secondary/30">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2 text-sm"
      >
        <div className="flex items-center gap-2">
          <ShieldCheck size={14} className="text-accent" />
          <span className="font-medium text-foreground/90">SALAAR</span>
          {brief.threats_critical > 0 && (
            <span className="text-[11px] rounded-full bg-destructive/10 text-destructive px-2 py-0.5 font-medium">
              {brief.threats_critical} critical
            </span>
          )}
          {brief.actions_pending > 0 && (
            <span className="text-[11px] rounded-full bg-amber-100 text-amber-700 px-2 py-0.5 font-medium">
              {brief.actions_pending} pending
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-muted">
          <span>{brief.shadow_summary}</span>
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-3">
          {/* Top alerts */}
          {brief.top_alerts && brief.top_alerts.length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-wide text-muted mb-2">Alerts</div>
              <div className="space-y-1.5">
                {brief.top_alerts.map((a, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs rounded-lg bg-background/80 border border-hairline/50 px-3 py-2">
                    <AlertTriangle size={12} className={`mt-0.5 shrink-0 ${a.severity === 'critical' ? 'text-destructive' : a.severity === 'high' ? 'text-amber-500' : 'text-muted'}`} />
                    <div>
                      <span className="font-medium text-foreground/90">{a.threat_key.replace(/_/g, ' ')}</span>
                      <span className="text-muted ml-1">{a.diagnosis}</span>
                      {a.repeat && <span className="text-[10px] text-destructive ml-1">(repeating)</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* People of concern */}
          {brief.people_of_concern && brief.people_of_concern.length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-wide text-muted mb-2">People</div>
              <div className="space-y-1.5">
                {brief.people_of_concern.map((p, i) => (
                  <div key={i} className="flex items-center justify-between text-xs rounded-lg bg-background/80 border border-hairline/50 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <Users size={12} className="text-muted" />
                      <span className="font-medium">{p.person_key}</span>
                      {p.red_flags && p.red_flags.length > 0 && (
                        <span className="text-[10px] text-destructive">
                          {p.red_flags.length} flags
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-muted">
                      <span>trust: {p.trust_score?.toFixed(0)}</span>
                      <span>{p.negative_pct}% negative</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Stats */}
          <div className="flex gap-3 text-[10px] text-muted pt-1 border-t border-hairline/40">
            <span>{brief.actions_auto_executed} auto-executed</span>
            <span>{brief.actions_pending} pending approval</span>
            <span>{brief.threats_active} signals tracked</span>
          </div>
        </div>
      )}
    </div>
  );
}
