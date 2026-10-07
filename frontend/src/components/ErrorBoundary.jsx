import { Component } from 'react';
import { Button } from './ui/button';

// Catches render errors and shows a recoverable fallback screen.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  // Capture any thrown error into component state.
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  // Render fallback UI on error, children otherwise.
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center min-h-screen bg-background">
          <div className="max-w-md mx-auto px-6 text-center">
            <div className="w-16 h-16 rounded-2xl bg-destructive/10 flex items-center justify-center mx-auto mb-6">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-destructive">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <h1 className="font-display text-2xl text-foreground mb-2">Something went wrong</h1>
            <p className="text-sm text-muted mb-8 leading-relaxed">
              {this.props.fallback || 'An unexpected error occurred. Please try again.'}
            </p>
            <div className="flex items-center justify-center gap-3">
              <Button onClick={() => window.location.reload()} className="rounded-xl">
                Reload page
              </Button>
              <Button variant="outline" onClick={() => window.location.href = '/'} className="rounded-xl">
                Go home
              </Button>
            </div>
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <pre className="mt-8 text-xs text-left text-muted bg-muted/50 rounded-xl p-4 overflow-auto max-h-40">
                {this.state.error.message}
                {this.state.error.stack}
              </pre>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
