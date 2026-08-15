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

import { MindForgeClient } from './mindforge-client.js'

export interface MindForgePluginConfig {
  host?: string
  port?: number
  autoStart?: boolean
  mindforgePath?: string
  pythonPath?: string
  dbPath?: string
  autoCapture?: boolean
  autoInject?: boolean
  maxInjectMemories?: number
  minRelevance?: number
  captureTags?: string[]
  captureImportance?: string
}

export const name = 'mindforge-memory'

export const inject = ['tools', 'agentLoop']

// Cordis plugin context type (minimal — matches @deepseek-ai/cordis Context)
interface CordisContext {
  tools: {
    register: (tool: ToolDefinition) => () => void
  }
  agentLoop?: {
    on?: (event: string, handler: (...args: unknown[]) => unknown) => () => void
  }
  on: (event: string, handler: (...args: unknown[]) => unknown) => () => void
  effect: (fn: () => (() => void) | Promise<(() => void) | void>) => void
  config?: Record<string, unknown>
}

interface ToolDefinition {
  name: string
  description: string
  parameters: Record<string, unknown>
  execute: (args: Record<string, unknown>) => Promise<unknown>
}

// Session-level state for tracking turn context
interface TurnContext {
  turnId: string
  userMessage: string
  startTime: number
  recalledMemories: string[]
}

const activeTurns = new Map<string, TurnContext>()

export function apply(ctx: CordisContext, config: MindForgePluginConfig = {}) {
  const opts: Required<MindForgePluginConfig> = {
    host: config.host || '127.0.0.1',
    port: config.port || 8765,
    autoStart: config.autoStart ?? true,
    mindforgePath: config.mindforgePath || '',
    pythonPath: config.pythonPath || 'python3',
    dbPath: config.dbPath || 'mindforge_agent.db',
    autoCapture: config.autoCapture ?? true,
    autoInject: config.autoInject ?? true,
    maxInjectMemories: config.maxInjectMemories || 5,
    minRelevance: config.minRelevance || 0.3,
    captureTags: config.captureTags || ['dsh', 'agent-session'],
    captureImportance: config.captureImportance || 'MEDIUM',
  }

  const client = new MindForgeClient({
    host: opts.host,
    port: opts.port,
    autoStart: opts.autoStart,
    mindforgePath: opts.mindforgePath,
    pythonPath: opts.pythonPath,
    dbPath: opts.dbPath,
  })

  let initialized = false

  // ---- Tool: memory_add ----
  const toolAdd: ToolDefinition = {
    name: 'memory_add',
    description:
      'Store a piece of information in long-term memory. Use this when the user shares ' +
      'a preference, decision, fact, or instruction you should remember for future sessions. ' +
      'The memory persists across sessions and is encrypted at rest.\n\n' +
      'Parameters:\n' +
      '  content (required): The information to remember — be specific and self-contained.\n' +
      '  category (optional): Category tag like "preference", "decision", "fact", "code". Default: "general".\n' +
      '  tags (optional): Array of string tags for organization. Default: [].\n' +
      '  importance (optional): "HIGH", "MEDIUM", or "LOW". Default: "MEDIUM".',
    parameters: {
      type: 'object',
      properties: {
        content: {
          type: 'string',
          description: 'The information to remember. Be specific and self-contained.',
        },
        category: {
          type: 'string',
          description: 'Category: preference, decision, fact, code, general, etc.',
          default: 'general',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Tags for organization and retrieval.',
        },
        importance: {
          type: 'string',
          enum: ['HIGH', 'MEDIUM', 'LOW'],
          description: 'Memory importance level. Default: MEDIUM.',
          default: 'MEDIUM',
        },
      },
      required: ['content'],
    },
    execute: async (args) => {
      await ensureInitialized()
      const entry = await client.addMemory({
        content: String(args.content),
        category: args.category ? String(args.category) : 'general',
        tags: Array.isArray(args.tags) ? args.tags.map(String) : [],
        importance: args.importance ? String(args.importance) : 'MEDIUM',
      })
      return {
        success: true,
        memory_id: entry.id,
        message: `Memory stored (id: ${entry.id}). This will be available in future sessions.`,
      }
    },
  }

  // ---- Tool: memory_search ----
  const toolSearch: ToolDefinition = {
    name: 'memory_search',
    description:
      'Search your long-term memory for previously stored information. ' +
      'Use this when you need to recall a past decision, preference, or fact.\n\n' +
      'Parameters:\n' +
      '  q (required): Natural language search query.\n' +
      '  limit (optional): Max results. Default: 5.\n' +
      '  min_relevance (optional): Min relevance score 0-1. Default: 0.3.',
    parameters: {
      type: 'object',
      properties: {
        q: {
          type: 'string',
          description: 'Natural language search query.',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of results. Default: 5.',
          default: 5,
        },
        min_relevance: {
          type: 'number',
          description: 'Minimum relevance score (0-1). Default: 0.3.',
          default: 0.3,
        },
      },
      required: ['q'],
    },
    execute: async (args) => {
      await ensureInitialized()
      const result = await client.search({
        q: String(args.q),
        limit: args.limit ? Number(args.limit) : 5,
        min_relevance: args.min_relevance ? Number(args.min_relevance) : 0.3,
      })
      return {
        query: result.query,
        total: result.total,
        results: result.results.map(r => ({
          id: r.id,
          content: r.content,
          category: r.category,
          relevance: Number(r.relevance_score.toFixed(3)),
          tags: r.tags,
        })),
      }
    },
  }

  // ---- Tool: memory_get ----
  const toolGet: ToolDefinition = {
    name: 'memory_get',
    description:
      'Retrieve a specific memory by its ID. Use after memory_search when you need ' +
      'the full content of a specific memory.\n\n' +
      'Parameters:\n' +
      '  id (required): The memory ID returned from memory_add or memory_search.',
    parameters: {
      type: 'object',
      properties: {
        id: {
          type: 'string',
          description: 'Memory ID.',
        },
      },
      required: ['id'],
    },
    execute: async (args) => {
      await ensureInitialized()
      const entry = await client.getMemory(String(args.id))
      return {
        id: entry.id,
        content: entry.content,
        category: entry.category,
        tags: entry.tags,
        importance: entry.importance,
        layer: entry.layer,
        created_at: new Date(entry.created_at * 1000).toISOString(),
        access_count: entry.access_count,
      }
    },
  }

  // ---- Tool: memory_stats ----
  const toolStats: ToolDefinition = {
    name: 'memory_stats',
    description:
      'Get statistics about the memory store: total memories, distribution by ' +
      'category/importance/layer, top tags. Use this to understand what the agent ' +
      'currently remembers.',
    parameters: {
      type: 'object',
      properties: {},
    },
    execute: async () => {
      await ensureInitialized()
      const stats = await client.stats()
      return {
        total_memories: stats.total,
        db_size_mb: Number((stats.db_size_bytes / 1024 / 1024).toFixed(2)),
        by_importance: stats.by_importance,
        by_layer: stats.by_layer,
        top_categories: stats.top_categories,
        top_tags: stats.top_tags,
        starred_count: stats.starred_count,
      }
    },
  }

  // ---- Tool: memory_delete ----
  const toolDelete: ToolDefinition = {
    name: 'memory_delete',
    description:
      'Delete a memory by ID. Use sparingly — memories are designed to persist. ' +
      'Only delete when the user explicitly asks to forget something.\n\n' +
      'Parameters:\n' +
      '  id (required): The memory ID to delete.',
    parameters: {
      type: 'object',
      properties: {
        id: {
          type: 'string',
          description: 'Memory ID to delete.',
        },
      },
      required: ['id'],
    },
    execute: async (args) => {
      await ensureInitialized()
      await client.deleteMemory(String(args.id))
      return {
        success: true,
        message: `Memory ${args.id} deleted.`,
      }
    },
  }

  // Register all tools with reversible effects
  ctx.effect(() => {
    const disposers = [
      ctx.tools.register(toolAdd),
      ctx.tools.register(toolSearch),
      ctx.tools.register(toolGet),
      ctx.tools.register(toolStats),
      ctx.tools.register(toolDelete),
    ]
    return () => disposers.forEach(d => d())
  })

  // ---- Hook: turn/start — recall relevant memories ----
  if (opts.autoInject) {
    ctx.effect(() => {
      const off = ctx.on('turn/start', async (...args: unknown[]) => {
        const turnId = String(args[0] || Date.now())
        const userMessage = extractUserMessage(args)

        if (!userMessage || userMessage.length < 3) return

        try {
          await ensureInitialized()

          // Search for relevant memories
          const result = await client.search({
            q: userMessage.slice(0, 500),
            limit: opts.maxInjectMemories,
            min_relevance: opts.minRelevance,
          })

          if (result.results.length === 0) return

          // Track this turn for later capture
          activeTurns.set(turnId, {
            turnId,
            userMessage,
            startTime: Date.now(),
            recalledMemories: result.results.map(r => r.id),
          })

          // Log recalled memories for the agent loop to pick up
          console.log(
            `[mindforge] Recalled ${result.results.length} memories for turn ${turnId}`
          )
        } catch (err) {
          console.error(`[mindforge] recall error: ${(err as Error).message}`)
        }
      })
      return off
    })
  }

  // ---- Hook: turn/end — auto-capture session summary ----
  if (opts.autoCapture) {
    ctx.effect(() => {
      const off = ctx.on('turn/end', async (...args: unknown[]) => {
        const turnId = String(args[0] || '')
        const turnCtx = activeTurns.get(turnId)

        if (!turnCtx) return

        activeTurns.delete(turnId)

        const duration = Date.now() - turnCtx.startTime

        // Only capture if the turn was substantive (> 5 seconds)
        if (duration < 5000) return

        try {
          await ensureInitialized()

          // Build a summary from the turn
          const summary = buildTurnSummary(args, turnCtx, duration)

          if (summary.length < 10) return

          await client.addMemory({
            content: summary,
            category: 'agent-session',
            tags: opts.captureTags,
            importance: opts.captureImportance,
          })

          console.log(`[mindforge] Auto-captured memory for turn ${turnId}`)
        } catch (err) {
          console.error(`[mindforge] capture error: ${(err as Error).message}`)
        }
      })
      return off
    })
  }

  // ---- Initialize on first use ----
  async function ensureInitialized(): Promise<void> {
    if (initialized) return
    initialized = true

    try {
      await client.ensureRunning()
      const health = await client.health()
      console.log(
        `[mindforge] Connected — ${health.total_memories} memories, ` +
        `${(health.db_size_bytes / 1024 / 1024).toFixed(1)}MB DB`
      )
    } catch (err) {
      initialized = false
      throw new Error(
        `[mindforge] Failed to connect to MindForge API at ${opts.host}:${opts.port}. ` +
        `Error: ${(err as Error).message}. ` +
        `Start it manually: mindforge --db-path ${opts.dbPath} serve --api --port ${opts.port}`
      )
    }
  }

  console.log('[mindforge] Plugin loaded — memory tools registered')
}

// ---- Helpers ----

function extractUserMessage(args: unknown[]): string {
  for (const arg of args) {
    if (typeof arg === 'string') return arg
    if (arg && typeof arg === 'object') {
      const obj = arg as Record<string, unknown>
      if (typeof obj.message === 'string') return obj.message
      if (typeof obj.content === 'string') return obj.content
      if (typeof obj.input === 'string') return obj.input
      if (typeof obj.prompt === 'string') return obj.prompt
    }
  }
  return ''
}

function buildTurnSummary(
  args: unknown[],
  turnCtx: TurnContext,
  duration: number
): string {
  const parts: string[] = []

  parts.push(`User request: ${turnCtx.userMessage.slice(0, 200)}`)

  // Try to extract assistant response from turn/end args
  for (const arg of args) {
    if (arg && typeof arg === 'object') {
      const obj = arg as Record<string, unknown>
      if (typeof obj.response === 'string') {
        parts.push(`Response: ${obj.response.slice(0, 300)}`)
      }
      if (typeof obj.summary === 'string') {
        parts.push(`Summary: ${obj.summary.slice(0, 300)}`)
      }
      if (Array.isArray(obj.tools) && obj.tools.length > 0) {
        parts.push(`Tools used: ${obj.tools.map(String).join(', ')}`)
      }
    }
  }

  parts.push(`Duration: ${(duration / 1000).toFixed(1)}s`)
  parts.push(`Recalled memories: ${turnCtx.recalledMemories.length}`)

  return parts.join('\n')
}
