/**
 * MindForge DSH Plugin
 * ====================
 *
 * Native Cordis plugin for DeepSeek Harness that gives your agent
 * a persistent, 4-layer memory engine powered by MindForge.
 *
 * What it does:
 *   1. Registers memory tools (memory_add, memory_search, memory_get, memory_stats)
 *      that the agent can call during conversations.
 *   2. Hooks into turn/start to automatically recall relevant memories
 *      and inject them into the agent's context.
 *   3. Hooks into turn/end to auto-capture session summaries as new memories.
 *
 * Architecture:
 *   This plugin (TypeScript) → HTTP localhost → MindForge REST API (Python) → SQLite
 *
 * Install:
 *   dsh plugin --profile web add mindforge-dsh-plugin
 *
 * License: MIT
 */
export interface MindForgePluginConfig {
    host?: string;
    port?: number;
    autoStart?: boolean;
    mindforgePath?: string;
    pythonPath?: string;
    dbPath?: string;
    autoCapture?: boolean;
    autoInject?: boolean;
    maxInjectMemories?: number;
    minRelevance?: number;
    captureTags?: string[];
    captureImportance?: string;
}
export declare const name = "mindforge-memory";
export declare const inject: string[];
interface CordisContext {
    tools: {
        register: (tool: ToolDefinition) => () => void;
    };
    agentLoop?: {
        on?: (event: string, handler: (...args: unknown[]) => unknown) => () => void;
    };
    on: (event: string, handler: (...args: unknown[]) => unknown) => () => void;
    effect: (fn: () => (() => void) | Promise<(() => void) | void>) => void;
    config?: Record<string, unknown>;
}
interface ToolDefinition {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
    execute: (args: Record<string, unknown>) => Promise<unknown>;
}
export declare function apply(ctx: CordisContext, config?: MindForgePluginConfig): void;
export {};
//# sourceMappingURL=index.d.ts.map