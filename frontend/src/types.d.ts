// Global window extensions for analytics
interface Window {
  trackPixel?: (event: string, data?: Record<string, unknown>) => void;
}
