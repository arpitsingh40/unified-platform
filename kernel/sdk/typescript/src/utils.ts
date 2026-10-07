/**
 * Utility functions for ARI SDK
 */

import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';
import { AgentSpec, AriError, ValidationError } from './types';

/**
 * Load agent spec from file (YAML or JSON)
 */
export function loadSpec(filePath: string): AgentSpec {
  const ext = path.extname(filePath).toLowerCase();
  const content = fs.readFileSync(filePath, 'utf-8');

  let spec: any;

  if (ext === '.yaml' || ext === '.yml') {
    spec = yaml.load(content);
  } else if (ext === '.json') {
    spec = JSON.parse(content);
  } else {
    throw new ValidationError(`Unsupported file format: ${ext}. Use .yaml, .yml, or .json`);
  }

  // Validate required fields
  if (!spec.name) throw new ValidationError('name is required');
  if (!spec.version) throw new ValidationError('version is required');
  if (!spec.capabilities || spec.capabilities.length === 0) {
    throw new ValidationError('at least one capability is required');
  }

  return spec as AgentSpec;
}

/**
 * Save agent spec to file
 */
export function saveSpec(spec: AgentSpec, filePath: string): void {
  const ext = path.extname(filePath).toLowerCase();
  let content: string;

  if (ext === '.yaml' || ext === '.yml') {
    content = yaml.dump(spec, { indent: 2, lineWidth: 120 });
  } else if (ext === '.json') {
    content = JSON.stringify(spec, null, 2);
  } else {
    throw new ValidationError(`Unsupported file format: ${ext}. Use .yaml, .yml, or .json`);
  }

  fs.writeFileSync(filePath, content, 'utf-8');
}

/**
 * Generate a unique invocation ID
 */
export function generateInvocationId(): string {
  return `inv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Generate a unique agent ID
 */
export function generateAgentId(name: string): string {
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return `${slug}_${Date.now().toString(36)}`;
}

/**
 * Parse cron expression to human readable
 */
export function describeCron(cron: string): string {
  const parts = cron.split(' ');
  if (parts.length < 5) return cron;

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;
  
  const descriptions: string[] = [];
  
  if (minute !== '*') descriptions.push(`at minute ${minute}`);
  if (hour !== '*') descriptions.push(`at hour ${hour}`);
  if (dayOfMonth !== '*') descriptions.push(`on day ${dayOfMonth} of month`);
  if (month !== '*') descriptions.push(`in month ${month}`);
  if (dayOfWeek !== '*') descriptions.push(`on ${dayName(dayOfWeek)}`);

  if (descriptions.length === 0) return 'every minute';
  if (descriptions.length === 5) return cron;

  return descriptions.join(', ');
}

function dayName(day: string): string {
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const num = parseInt(day, 10);
  return days[num] || day;
}

/**
 * Calculate estimated cost for tool calls
 */
export function estimateCost(toolCalls: { capability: string; tool: string }[]): number {
  // Base costs per capability (in USD)
  const baseCosts: Record<string, number> = {
    http: 0.0001,
    email: 0.001,
    crm: 0.01,
    slack: 0.0005,
    github: 0.001,
    aws: 0.005,
    gcp: 0.005,
    azure: 0.005,
  };

  return toolCalls.reduce((total, call) => {
    return total + (baseCosts[call.capability] || 0.001);
  }, 0);
}

/**
 * Format duration in human readable form
 */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 3600000) return `${(ms / 60000).toFixed(1)}m`;
  return `${(ms / 3600000).toFixed(1)}h`;
}

/**
 * Format cost in human readable form
 */
export function formatCost(cost: number): string {
  if (cost < 0.01) return `$${(cost * 1000000).toFixed(0)}μ`;
  if (cost < 1) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

/**
 * Deep clone an object
 */
export function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

/**
 * Merge two objects deeply
 */
export function deepMerge<T extends Record<string, any>>(target: T, source: Partial<T>): T {
  const result = { ...target };
  
  for (const key of Object.keys(source)) {
    const sourceValue = source[key];
    const targetValue = target[key];
    
    if (
      sourceValue &&
      typeof sourceValue === 'object' &&
      !Array.isArray(sourceValue) &&
      targetValue &&
      typeof targetValue === 'object' &&
      !Array.isArray(targetValue)
    ) {
      (result as any)[key] = deepMerge(targetValue, sourceValue);
    } else if (sourceValue !== undefined) {
      (result as any)[key] = sourceValue;
    }
  }
  
  return result;
}

/**
 * Retry a function with exponential backoff
 */
export async function retry<T>(
  fn: () => Promise<T>,
  options: {
    maxRetries?: number;
    baseDelayMs?: number;
    maxDelayMs?: number;
    shouldRetry?: (error: Error) => boolean;
  } = {}
): Promise<T> {
  const {
    maxRetries = 3,
    baseDelayMs = 1000,
    maxDelayMs = 30000,
    shouldRetry = () => true,
  } = options;

  let lastError: Error;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      
      if (attempt === maxRetries || !shouldRetry(lastError)) {
        throw lastError;
      }
      
      const delay = Math.min(baseDelayMs * Math.pow(2, attempt), maxDelayMs);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  throw lastError!;
}

/**
 * Create a debounced function
 */
export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delayMs: number
): (...args: Parameters<T>) => void {
  let timeoutId: NodeJS.Timeout | null = null;
  
  return (...args: Parameters<T>) => {
    if (timeoutId) clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delayMs);
  };
}

/**
 * Create a throttled function
 */
export function throttle<T extends (...args: any[]) => any>(
  fn: T,
  limitMs: number
): (...args: Parameters<T>) => void {
  let inThrottle = false;
  
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      fn(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limitMs);
    }
  };
}

/**
 * Validate environment variables
 */
export function validateEnv(required: string[]): { valid: boolean; missing: string[] } {
  const missing = required.filter(key => !process.env[key]);
  return { valid: missing.length === 0, missing };
}

/**
 * Sleep utility
 */
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}