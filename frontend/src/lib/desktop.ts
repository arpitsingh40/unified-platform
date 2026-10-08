// Tauri desktop bridge — used by frontend; no-ops in browser
export const isDesktop = typeof window !== 'undefined' && '__TAURI__' in window;

// Lazy-load so browser bundle never pulls @tauri/api
async function invoke<T = unknown>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (!isDesktop) throw new Error('Desktop only: ' + cmd);
  const { invoke: inv } = await import('@tauri-apps/api/core');
  return inv(cmd, args as any);
}

export async function desktopInfo(): Promise<{ platform: string; arch: string; forge_root: string }> {
  return invoke('desktop_info');
}
export async function browserNavigate(url: string) {
  return invoke('browser_navigate', { url });
}
export async function browserEval(js: string) {
  return invoke('browser_eval', { js });
}
export async function openPath(path: string) {
  return invoke('open_path', { path });
}
export async function openUrl(url: string) {
  return invoke('open_url', { url });
}
export async function shellRun(cmd: string, cwd?: string) {
  return invoke<string>('shell_run', { cmd, cwd });
}
export async function ensureForgeRoot() {
  return invoke<string>('ensure_forge_root');
}

// Listen helper that works only on desktop
export async function onDesktopEvent<T = unknown>(event: string, handler: (e: { payload: T }) => void) {
  if (!isDesktop) return () => {};
  const { listen } = await import('@tauri-apps/api/event');
  return listen(event, handler as any);
}
