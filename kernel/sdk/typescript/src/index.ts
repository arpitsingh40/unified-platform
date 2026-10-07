/**
 * ARI TypeScript SDK
 * 
 * Build, deploy, and run agents on the Agent Runtime Infrastructure.
 * A trillion-dollar platform for autonomous agents with:
 * - WASM-based isolation
 * - Capability registry with governance
 * - Built-in verification & approval workflows
 * - Cryptographic identity & signing
 */

// Core types
export * from './types';

// Client for interacting with ARI runtime
export * from './client';

// Agent specification builder
export * from './spec';

// Utilities
export * from './utils';

import { AriClient } from './client';
import { AgentSpec, createAgentSpec } from './spec';

/**
 * Create a new ARI client
 */
export function createClient(config?: Partial<AriClientConfig>): AriClient {
  return new AriClient(config);
}

/**
 * Create a new agent specification
 */
export function createAgent(spec: Partial<AgentSpec>): AgentSpec {
  return createAgentSpec(spec);
}

/**
 * Configuration for ARI client
 */
export interface AriClientConfig {
  /** Runtime endpoint */
  runtimeUrl: string;
  /** Registry endpoint */
  registryUrl: string;
  /** Control plane endpoint */
  controlPlaneUrl: string;
  /** API key for authentication */
  apiKey?: string;
  /** Default timeout in ms */
  timeout?: number;
}

/**
 * Default configuration
 */
export const defaultConfig: AriClientConfig = {
  runtimeUrl: 'http://localhost:8080',
  registryUrl: 'https://registry.ari.io',
  controlPlaneUrl: 'https://api.ari.io',
  timeout: 30000,
};

// Version
export const VERSION = '0.1.0';