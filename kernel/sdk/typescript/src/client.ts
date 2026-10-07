/**
 * ARI Client - Interact with the ARI runtime, registry, and control plane
 */

import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import { v4 as uuidv4 } from 'uuid';
import {
  AriClientConfig,
  defaultConfig,
  AgentInput,
  AgentResult,
  AgentDecision,
  ToolCall,
  ToolResult,
  InvocationRequest,
  InvocationResult,
  ToolExecution,
  VerificationResult,
  RegistryManifest,
  DeploymentRequest,
  DeploymentResponse,
  ResourceRequirements,
  AriError,
  NotFoundError,
  AuthorizationError,
  RuntimeError,
} from './types';

export interface AriClientConfig {
  runtimeUrl?: string;
  registryUrl?: string;
  controlPlaneUrl?: string;
  apiKey?: string;
  timeout?: number;
}

export class AriClient {
  private config: Required<AriClientConfig>;
  private runtime: AxiosInstance;
  private registry: AxiosInstance;
  private controlPlane: AxiosInstance;

  constructor(config: AriClientConfig = {}) {
    this.config = {
      runtimeUrl: config.runtimeUrl || defaultConfig.runtimeUrl,
      registryUrl: config.registryUrl || defaultConfig.registryUrl,
      controlPlaneUrl: config.controlPlaneUrl || defaultConfig.controlPlaneUrl,
      apiKey: config.apiKey || '',
      timeout: config.timeout || defaultConfig.timeout,
    };

    const commonConfig: AxiosRequestConfig = {
      timeout: this.config.timeout,
      headers: {
        'Content-Type': 'application/json',
        ...(this.config.apiKey && { 'Authorization': `Bearer ${this.config.apiKey}` }),
      },
    };

    this.runtime = axios.create({
      ...commonConfig,
      baseURL: this.config.runtimeUrl,
    });

    this.registry = axios.create({
      ...commonConfig,
      baseURL: this.config.registryUrl,
    });

    this.controlPlane = axios.create({
      ...commonConfig,
      baseURL: this.config.controlPlaneUrl,
    });

    // Add request interceptors for logging
    this.addInterceptors();
  }

  private addInterceptors(): void {
    const logRequest = (config: AxiosRequestConfig) => {
      console.debug(`[ARI] ${config.method?.toUpperCase()} ${config.url}`);
      return config;
    };

    const logError = (error: any) => {
      console.error(`[ARI] Request failed:`, error.response?.data || error.message);
      return Promise.reject(error);
    };

    [this.runtime, this.registry, this.controlPlane].forEach(client => {
      client.interceptors.request.use(logRequest);
      client.interceptors.response.use(
        response => response,
        logError
      );
    });
  }

  // ============================================================================
  // Runtime API
  // ============================================================================

  /**
   * Invoke an agent
   */
  async invoke(request: InvocationRequest): Promise<InvocationResult> {
    try {
      const response = await this.runtime.post<InvocationResult>('/api/v1/invoke', request);
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        throw new NotFoundError('Agent or endpoint');
      }
      if (error.response?.status === 401) {
        throw new AuthorizationError();
      }
      throw new RuntimeError(error.response?.data?.message || error.message);
    }
  }

  /**
   * Run an agent with simple context (convenience method)
   */
  async run(agentId: string, context: Record<string, unknown>, options?: {
    orgId?: string;
    invocationId?: string;
    traceParent?: string;
    dryRun?: boolean;
  }): Promise<InvocationResult> {
    const invocationRequest: InvocationRequest = {
      invocation_id: options?.invocationId || uuidv4(),
      agent_id: agentId,
      org_id: options?.orgId || 'default',
      context,
      trace_parent: options?.traceParent,
    };

    return this.invoke(invocationRequest);
  }

  /**
   * Get invocation status
   */
  async getInvocation(invocationId: string): Promise<InvocationResult> {
    const response = await this.runtime.get<InvocationResult>(`/api/v1/invocations/${invocationId}`);
    return response.data;
  }

  /**
   * List invocations for an agent
   */
  async listInvocations(agentId: string, options?: {
    limit?: number;
    offset?: number;
    status?: string;
  }): Promise<InvocationResult[]> {
    const params = new URLSearchParams();
    if (options?.limit) params.append('limit', options.limit.toString());
    if (options?.offset) params.append('offset', options.offset.toString());
    if (options?.status) params.append('status', options.status);

    const response = await this.runtime.get<InvocationResult[]>(
      `/api/v1/agents/${agentId}/invocations?${params.toString()}`
    );
    return response.data;
  }

  // ============================================================================
  // Tool Execution (for custom capability providers)
  // ============================================================================

  /**
   * Execute a tool call directly
   */
  async executeTool(toolCall: ToolCall): Promise<ToolResult> {
    const response = await this.runtime.post<ToolResult>('/api/v1/tools/execute', toolCall);
    return response.data;
  }

  // ============================================================================
  // Registry API
  // ============================================================================

  /**
   * Get agent manifest from registry
   */
  async getManifest(name: string, version: string): Promise<RegistryManifest> {
    try {
      const response = await this.registry.get<RegistryManifest>(
        `/api/v1/manifests/${name}/${version}`
      );
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        throw new NotFoundError(`Agent ${name}:${version}`);
      }
      throw error;
    }
  }

  /**
   * Search agents in registry
   */
  async searchAgents(query: string, options?: {
    capability?: string;
    authority?: string;
    limit?: number;
  }): Promise<RegistryManifest[]> {
    const params = new URLSearchParams({ q: query });
    if (options?.capability) params.append('capability', options.capability);
    if (options?.authority) params.append('authority', options.authority);
    if (options?.limit) params.append('limit', options.limit.toString());

    const response = await this.registry.get<RegistryManifest[]>(
      `/api/v1/search?${params.toString()}`
    );
    return response.data;
  }

  /**
   * List all versions of an agent
   */
  async listVersions(name: string): Promise<string[]> {
    const response = await this.registry.get<string[]>(`/api/v1/agents/${name}/versions`);
    return response.data;
  }

  // ============================================================================
  // Control Plane API
  // ============================================================================

  /**
   * Deploy an agent
   */
  async deploy(request: DeploymentRequest): Promise<DeploymentResponse> {
    const response = await this.controlPlane.post<DeploymentResponse>('/api/v1/deployments', request);
    return response.data;
  }

  /**
   * Get deployment status
   */
  async getDeployment(deploymentId: string): Promise<DeploymentResponse> {
    const response = await this.controlPlane.get<DeploymentResponse>(
      `/api/v1/deployments/${deploymentId}`
    );
    return response.data;
  }

  /**
   * Scale a deployment
   */
  async scaleDeployment(deploymentId: string, replicas: number): Promise<DeploymentResponse> {
    const response = await this.controlPlane.patch<DeploymentResponse>(
      `/api/v1/deployments/${deploymentId}/scale`,
      { replicas }
    );
    return response.data;
  }

  /**
   * Delete a deployment
   */
  async deleteDeployment(deploymentId: string): Promise<void> {
    await this.controlPlane.delete(`/api/v1/deployments/${deploymentId}`);
  }

  /**
   * List deployments
   */
  async listDeployments(options?: {
    environment?: string;
    agentName?: string;
    status?: string;
  }): Promise<DeploymentResponse[]> {
    const params = new URLSearchParams();
    if (options?.environment) params.append('environment', options.environment);
    if (options?.agentName) params.append('agent_name', options.agentName);
    if (options?.status) params.append('status', options.status);

    const response = await this.controlPlane.get<DeploymentResponse[]>(
      `/api/v1/deployments?${params.toString()}`
    );
    return response.data;
  }

  /**
   * Get deployment logs
   */
  async getDeploymentLogs(deploymentId: string, options?: {
    tail?: number;
    since?: string;
  }): Promise<string> {
    const params = new URLSearchParams();
    if (options?.tail) params.append('tail', options.tail.toString());
    if (options?.since) params.append('since', options.since);

    const response = await this.controlPlane.get<string>(
      `/api/v1/deployments/${deploymentId}/logs?${params.toString()}`,
      { responseType: 'text' as const }
    );
    return response.data;
  }

  // ============================================================================
  // Health & Metrics
  // ============================================================================

  /**
   * Check runtime health
   */
  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await this.runtime.get('/health');
    return response.data;
  }

  /**
   * Get runtime metrics
   */
  async getMetrics(): Promise<Record<string, unknown>> {
    const response = await this.runtime.get('/metrics');
    return response.data;
  }

  // ============================================================================
  // Utility Methods
  // ============================================================================

  /**
   * Create a default agent decision (for testing)
   */
  static createDecision(
    action: string,
    reasoning: string,
    toolCalls: ToolCall[],
    confidence: number = 0.8,
    reviewAfterDays: number = 1
  ): AgentDecision {
    return {
      action,
      reasoning,
      tool_calls: toolCalls,
      confidence,
      review_after_days: reviewAfterDays,
    };
  }

  /**
   * Create a tool call
   */
  static createToolCall(
    capability: string,
    tool: string,
    args: Record<string, unknown>,
    reason: string
  ): ToolCall {
    return {
      capability,
      tool,
      args,
      reason,
    };
  }

  /**
   * Create an invocation request
   */
  static createInvocation(
    agentId: string,
    orgId: string,
    context: Record<string, unknown>
  ): InvocationRequest {
    return {
      invocation_id: uuidv4(),
      agent_id: agentId,
      org_id: orgId,
      context,
    };
  }
}