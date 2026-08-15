/**
 * MindForge REST API Client
 * -------------------------
 * Thin HTTP wrapper around MindForge v5.4.6's REST API.
 * All calls go to localhost — no external network dependency.
 */

export interface MindForgeConfig {
  host: string
  port: number
  autoStart: boolean
  mindforgePath?: string
  pythonPath?: string
  dbPath?: string
}

export interface MemoryEntry {
  id: string
  content: string
  category: string
  tags: string[]
  importance: string
  layer: string
  created_at: number
  updated_at: number
  access_count: number
  starred: boolean
  [key: string]: unknown
}

export interface SearchResult {
  id: string
  content: string
  category: string
  relevance_score: number
  tags: string[]
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
  total: number
}

export interface StatsResponse {
  total: number
  db_size_bytes: number
  by_importance: Record<string, number>
  by_layer: Record<string, number>
  top_categories: Record<string, number>
  top_tags: Record<string, number>
  starred_count: number
}

export interface HealthResponse {
  status: string
  integrity_check: string
  total_memories: number
  db_size_bytes: number
  recommendations: string[]
}

export class MindForgeClient {
  private baseUrl: string
  private config: MindForgeConfig

  constructor(config: MindForgeConfig) {
    this.config = config
    this.baseUrl = `http://${config.host}:${config.port}`
  }

  private async request<T>(
    path: string,
    options: { method?: string; body?: unknown } = {}
  ): Promise<T> {
    const { method = 'GET', body } = options
    const url = `${this.baseUrl}${path}`

    const init: RequestInit = {
      method,
      headers: { 'Content-Type': 'application/json' },
    }

    if (body !== undefined) {
      init.body = JSON.stringify(body)
    }

    const res = await fetch(url, init)

    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      throw new Error(`MindForge API ${res.status}: ${text}`)
    }

    return res.json() as Promise<T>
  }

  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/api/health')
  }

  async isRunning(): Promise<boolean> {
    try {
      await this.health()
      return true
    } catch {
      return false
    }
  }

  async addMemory(params: {
    content: string
    category?: string
    tags?: string[]
    importance?: string
  }): Promise<MemoryEntry> {
    return this.request<MemoryEntry>('/api/memories', {
      method: 'POST',
      body: params,
    })
  }

  async getMemory(id: string): Promise<MemoryEntry> {
    return this.request<MemoryEntry>(`/api/memories/${id}`)
  }

  async updateMemory(
    id: string,
    params: { content?: string; importance?: string; tags?: string[] }
  ): Promise<{ status: string; id: string }> {
    return this.request(`/api/memories/${id}`, {
      method: 'PUT',
      body: params,
    })
  }

  async deleteMemory(id: string): Promise<{ status: string; id: string }> {
    return this.request(`/api/memories/${id}`, {
      method: 'DELETE',
    })
  }

  async listMemories(params: {
    limit?: number
    offset?: number
    category?: string
  } = {}): Promise<{ memories: MemoryEntry[]; total: number }> {
    const qs = new URLSearchParams()
    if (params.limit) qs.set('limit', String(params.limit))
    if (params.offset) qs.set('offset', String(params.offset))
    if (params.category) qs.set('category', params.category)
    const query = qs.toString()
    return this.request(`/api/memories${query ? `?${query}` : ''}`)
  }

  async search(params: {
    q: string
    limit?: number
    min_relevance?: number
  }): Promise<SearchResponse> {
    const qs = new URLSearchParams({ q: params.q })
    if (params.limit) qs.set('limit', String(params.limit))
    if (params.min_relevance) qs.set('min_relevance', String(params.min_relevance))
    return this.request<SearchResponse>(`/api/search?${qs.toString()}`)
  }

  async stats(): Promise<StatsResponse> {
    return this.request<StatsResponse>('/api/stats')
  }

  async tags(): Promise<{ tags: [string, number][] }> {
    return this.request('/api/tags')
  }

  async export(): Promise<{ version: string; total: number; memories: MemoryEntry[] }> {
    return this.request('/api/export')
  }

  /**
   * Auto-start the MindForge REST API server as a child process.
   * Only called when autoStart is true and the server is not already running.
   */
  async ensureRunning(): Promise<boolean> {
    if (await this.isRunning()) {
      return true
    }

    if (!this.config.autoStart) {
      throw new Error(
        `MindForge API not running at ${this.baseUrl} and autoStart is disabled. ` +
        `Start it manually: mindforge --db-path <path> serve --api --port ${this.config.port}`
      )
    }

    const { spawn } = await import('child_process')
    const pythonPath = this.config.pythonPath || 'python3'
    const mfPath = this.config.mindforgePath

    if (!mfPath) {
      throw new Error(
        'mindforgePath not configured. Set it in cordis.patch.yml or start MindForge manually.'
      )
    }

    const dbPath = this.config.dbPath || 'mindforge_agent.db'
    const args = [
      '-m', 'cli.main',
      '--db-path', dbPath,
      'serve',
      '--api',
      '--host', this.config.host,
      '--port', String(this.config.port),
    ]

    const child = spawn(pythonPath, args, {
      cwd: mfPath,
      stdio: 'pipe',
      detached: false,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
    })

    child.stdout?.on('data', (data: Buffer) => {
      console.log(`[mindforge] ${data.toString().trim()}`)
    })
    child.stderr?.on('data', (data: Buffer) => {
      console.error(`[mindforge] ${data.toString().trim()}`)
    })
    child.on('error', (err: Error) => {
      console.error(`[mindforge] process error: ${err.message}`)
    })

    // Wait for the server to be ready (max 10 seconds)
    for (let i = 0; i < 20; i++) {
      await new Promise(resolve => setTimeout(resolve, 500))
      if (await this.isRunning()) {
        console.log(`[mindforge] REST API started at ${this.baseUrl}`)
        return true
      }
    }

    throw new Error(`MindForge API failed to start within 10 seconds at ${this.baseUrl}`)
  }
}
