/**
 * MindForge REST API Client
 * -------------------------
 * Thin HTTP wrapper around MindForge v5.4.6's REST API.
 * All calls go to localhost — no external network dependency.
 */
export interface MindForgeConfig {
    host: string;
    port: number;
    autoStart: boolean;
    mindforgePath?: string;
    pythonPath?: string;
    dbPath?: string;
}
export interface MemoryEntry {
    id: string;
    content: string;
    category: string;
    tags: string[];
    importance: string;
    layer: string;
    created_at: number;
    updated_at: number;
    access_count: number;
    starred: boolean;
    [key: string]: unknown;
}
export interface SearchResult {
    id: string;
    content: string;
    category: string;
    relevance_score: number;
    tags: string[];
}
export interface SearchResponse {
    query: string;
    results: SearchResult[];
    total: number;
}
export interface StatsResponse {
    total: number;
    db_size_bytes: number;
    by_importance: Record<string, number>;
    by_layer: Record<string, number>;
    top_categories: Record<string, number>;
    top_tags: Record<string, number>;
    starred_count: number;
}
export interface HealthResponse {
    status: string;
    integrity_check: string;
    total_memories: number;
    db_size_bytes: number;
    recommendations: string[];
}
export declare class MindForgeClient {
    private baseUrl;
    private config;
    constructor(config: MindForgeConfig);
    private request;
    health(): Promise<HealthResponse>;
    isRunning(): Promise<boolean>;
    addMemory(params: {
        content: string;
        category?: string;
        tags?: string[];
        importance?: string;
    }): Promise<MemoryEntry>;
    getMemory(id: string): Promise<MemoryEntry>;
    updateMemory(id: string, params: {
        content?: string;
        importance?: string;
        tags?: string[];
    }): Promise<{
        status: string;
        id: string;
    }>;
    deleteMemory(id: string): Promise<{
        status: string;
        id: string;
    }>;
    listMemories(params?: {
        limit?: number;
        offset?: number;
        category?: string;
    }): Promise<{
        memories: MemoryEntry[];
        total: number;
    }>;
    search(params: {
        q: string;
        limit?: number;
        min_relevance?: number;
    }): Promise<SearchResponse>;
    stats(): Promise<StatsResponse>;
    tags(): Promise<{
        tags: [string, number][];
    }>;
    export(): Promise<{
        version: string;
        total: number;
        memories: MemoryEntry[];
    }>;
    /**
     * Auto-start the MindForge REST API server as a child process.
     * Only called when autoStart is true and the server is not already running.
     */
    ensureRunning(): Promise<boolean>;
}
//# sourceMappingURL=mindforge-client.d.ts.map