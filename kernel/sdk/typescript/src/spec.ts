/**
 * Agent Specification Builder - Fluent API for creating agent specs
 */

import { AgentSpec, InputSpec, OutputSpec, GovernanceSpec, MemorySpec, AuthorityLevel } from './types';

export interface SpecBuilderOptions {
  name: string;
  version?: string;
  description?: string;
  author?: string;
}

/**
 * Fluent builder for agent specifications
 */
export class SpecBuilder {
  private spec: Partial<AgentSpec>;

  constructor(options: SpecBuilderOptions) {
    this.spec = {
      name: options.name,
      version: options.version || '0.1.0',
      description: options.description || '',
      author: options.author || 'Unknown',
      spec_version: '1.0',
      capabilities: [],
      authority: 'L1',
      schedule: '0 9 * * *',
      inputs: [],
      outputs: [],
      governance: {
        max_tool_calls: 20,
        max_cost_usd: 1.0,
        max_execution_time_ms: 300000,
        requires_approval_above_usd: 0.10,
      },
      memory: {
        backend: 'postgres',
        ttl_days: 30,
      },
    };
  }

  /** Set agent version */
  version(version: string): this {
    this.spec.version = version;
    return this;
  }

  /** Set agent description */
  description(description: string): this {
    this.spec.description = description;
    return this;
  }

  /** Set agent author */
  author(author: string): this {
    this.spec.author = author;
    return this;
  }

  /** Add a capability */
  capability(capability: string): this {
    if (!this.spec.capabilities!.includes(capability)) {
      this.spec.capabilities!.push(capability);
    }
    return this;
  }

  /** Add multiple capabilities */
  capabilities(capabilities: string[]): this {
    capabilities.forEach(c => this.capability(c));
    return this;
  }

  /** Set authority level */
  authority(level: AuthorityLevel): this {
    this.spec.authority = level;
    return this;
  }

  /** Set schedule (cron expression) */
  schedule(cron: string): this {
    this.spec.schedule = cron;
    return this;
  }

  /** Add an input */
  input(input: Omit<InputSpec, 'name'> & { name: string }): this {
    this.spec.inputs!.push(input as InputSpec);
    return this;
  }

  /** Add a required input */
  requiredInput(name: string, type: string, description: string): this {
    return this.input({ name, type, required: true, description });
  }

  /** Add an optional input */
  optionalInput(name: string, type: string, description: string): this {
    return this.input({ name, type, required: false, description });
  }

  /** Add multiple inputs */
  inputs(inputs: InputSpec[]): this {
    inputs.forEach(i => this.spec.inputs!.push(i));
    return this;
  }

  /** Add an output */
  output(output: Omit<OutputSpec, 'name'> & { name: string }): this {
    this.spec.outputs!.push(output as OutputSpec);
    return this;
  }

  /** Add a decision output */
  decisionOutput(type: string = 'object', description: string = 'Agent decision'): this {
    return this.output({ name: 'decision', type, description });
  }

  /** Add multiple outputs */
  outputs(outputs: OutputSpec[]): this {
    outputs.forEach(o => this.spec.outputs!.push(o));
    return this;
  }

  /** Set governance limits */
  governance(gov: Partial<GovernanceSpec>): this {
    this.spec.governance = { ...this.spec.governance!, ...gov };
    return this;
  }

  /** Set max tool calls */
  maxToolCalls(max: number): this {
    this.spec.governance!.max_tool_calls = max;
    return this;
  }

  /** Set max cost in USD */
  maxCostUsd(cost: number): this {
    this.spec.governance!.max_cost_usd = cost;
    return this;
  }

  /** Set max execution time in ms */
  maxExecutionTimeMs(ms: number): this {
    this.spec.governance!.max_execution_time_ms = ms;
    return this;
  }

  /** Set approval threshold */
  requiresApprovalAboveUsd(amount: number): this {
    this.spec.governance!.requires_approval_above_usd = amount;
    return this;
  }

  /** Set memory backend */
  memoryBackend(backend: MemorySpec['backend']): this {
    this.spec.memory!.backend = backend;
    return this;
  }

  /** Set memory TTL in days */
  memoryTtlDays(days: number): this {
    this.spec.memory!.ttl_days = days;
    return this;
  }

  /** Build the final spec */
  build(): AgentSpec {
    // Validate required fields
    if (!this.spec.name) throw new Error('Agent name is required');
    if (!this.spec.version) throw new Error('Agent version is required');
    if (this.spec.capabilities!.length === 0) throw new Error('At least one capability is required');

    return this.spec as AgentSpec;
  }

  /** Export to YAML string */
  toYaml(): string {
    const spec = this.build();
    return this.toYamlString(spec);
  }

  /** Export to JSON string */
  toJson(): string {
    const spec = this.build();
    return JSON.stringify(spec, null, 2);
  }

  private toYamlString(obj: any, indent: number = 0): string {
    const spaces = '  '.repeat(indent);
    let result = '';

    for (const [key, value] of Object.entries(obj)) {
      if (value === null || value === undefined) continue;
      
      if (Array.isArray(value)) {
        if (value.length === 0) continue;
        result += `${spaces}${key}:\n`;
        for (const item of value) {
          if (typeof item === 'object' && item !== null) {
            result += `${spaces}  - `;
            // For objects in arrays, we need special handling
            const itemStr = this.toYamlString(item, indent + 2).trimStart();
            result += itemStr.replace(/\n/g, `\n${spaces}    `) + '\n';
          } else {
            result += `${spaces}  - ${item}\n`;
          }
        }
      } else if (typeof value === 'object') {
        result += `${spaces}${key}:\n`;
        result += this.toYamlString(value, indent + 1);
      } else {
        result += `${spaces}${key}: ${JSON.stringify(value)}\n`;
      }
    }

    return result;
  }
}

/**
 * Create a new agent specification builder
 */
export function createAgentSpec(options: SpecBuilderOptions): SpecBuilder {
  return new SpecBuilder(options);
}

/**
 * Quick create with minimal options
 */
export function createAgent(name: string, options?: Partial<SpecBuilderOptions>): SpecBuilder {
  return new SpecBuilder({ name, ...options });
}

/**
 * Predefined templates
 */
export const templates = {
  /** Data analysis agent template */
  dataAnalyst: (name: string) => createAgent(name)
    .description('Analyzes data and provides insights')
    .capabilities(['http', 'crm'])
    .authority('L2')
    .requiredInput('dataset', 'string', 'Dataset identifier')
    .optionalInput('parameters', 'object', 'Analysis parameters')
    .decisionOutput(),

  /** Notification agent template */
  notifier: (name: string) => createAgent(name)
    .description('Sends notifications based on triggers')
    .capabilities(['email', 'slack'])
    .authority('L1')
    .requiredInput('event', 'object', 'Trigger event')
    .optionalInput('recipients', 'array', 'Notification recipients')
    .decisionOutput(),

  /** CRM automation agent template */
  crmAutomation: (name: string) => createAgent(name)
    .description('Automates CRM workflows')
    .capabilities(['crm', 'email'])
    .authority('L3')
    .requiredInput('context', 'object', 'Execution context')
    .decisionOutput()
    .governance({ max_tool_calls: 50, max_cost_usd: 5.0 }),

  /** Generic template */
  generic: (name: string) => createAgent(name)
    .description('A generic ARI agent')
    .capabilities(['http'])
    .authority('L1')
    .requiredInput('context', 'object', 'Execution context')
    .decisionOutput(),
};

/**
 * Validate an agent spec
 */
export function validateSpec(spec: AgentSpec): { valid: boolean; errors: string[]; warnings: string[] } {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (!spec.name?.trim()) errors.push('name is required');
  if (!spec.version?.trim()) errors.push('version is required');
  if (!spec.description?.trim()) errors.push('description is required');
  if (!spec.author?.trim()) errors.push('author is required');
  if (!spec.spec_version?.trim()) errors.push('spec_version is required');
  if (!spec.capabilities || spec.capabilities.length === 0) errors.push('at least one capability is required');
  if (!spec.authority?.trim()) errors.push('authority is required');
  if (!spec.schedule?.trim()) errors.push('schedule is required');

  const validAuthorities: AuthorityLevel[] = ['L1', 'L2', 'L3', 'L4', 'L5'];
  if (spec.authority && !validAuthorities.includes(spec.authority)) {
    errors.push(`invalid authority: ${spec.authority}`);
  }

  if (spec.governance) {
    if (spec.governance.max_tool_calls === 0) errors.push('max_tool_calls must be > 0');
    if (spec.governance.max_cost_usd <= 0) errors.push('max_cost_usd must be > 0');
    if (spec.governance.max_execution_time_ms === 0) errors.push('max_execution_time_ms must be > 0');
  }

  // Warnings
  if (spec.capabilities && spec.capabilities.length > 20) {
    warnings.push('many capabilities may increase attack surface');
  }
  if (spec.governance && spec.governance.max_tool_calls > 100) {
    warnings.push('max_tool_calls > 100 may cause runaway executions');
  }
  if (spec.governance && spec.governance.max_cost_usd > 100) {
    warnings.push('max_cost_usd > $100 - ensure budget controls');
  }

  return { valid: errors.length === 0, errors, warnings };
}