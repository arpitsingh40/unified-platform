// Site footer with brand, section links, and copyright.
export default function Footer() {
  return (
    <footer className="py-12 bg-background border-t border-hairline">
      <div className="max-w-6xl mx-auto px-6 sm:px-10 lg:px-14 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm text-muted">
          <span className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-text text-background font-display text-xs">S</span>
          <span>SmartDecigen</span>
        </div>
        <div className="flex items-center gap-6 text-xs text-muted">
          <a href="#how-it-works" className="hover:text-text transition-colors">How it works</a>
          <a href="#features" className="hover:text-text transition-colors">Features</a>
          <a href="#pricing" className="hover:text-text transition-colors">Pricing</a>
          <a href="/auth" className="hover:text-text transition-colors">Sign in</a>
        </div>
        <p className="text-xs text-muted">© {new Date().getFullYear()} SmartDecigen</p>
      </div>
    </footer>
  );
}
