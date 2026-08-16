/**
 * MindForge REST API Client
 * -------------------------
 * Thin HTTP wrapper around MindForge v5.4.6's REST API.
 * All calls go to localhost — no external network dependency.
 */
export class MindForgeClient {
    baseUrl;
    config;
    constructor(config) {
        this.config = config;
        this.baseUrl = `http://${config.host}:${config.port}`;
    }
    async request(path, options = {}) {
        const { method = 'GET', body } = options;
        const url = `${this.baseUrl}${path}`;
        const init = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body !== undefined) {
            init.body = JSON.stringify(body);
        }
        const res = await fetch(url, init);
        if (!res.ok) {
            const text = await res.text().catch(() => res.statusText);
            throw new Error(`MindForge API ${res.status}: ${text}`);
        }
        return res.json();
    }
    async health() {
        return this.request('/api/health');
    }
    async isRunning() {
        try {
            await this.health();
            return true;
        }
        catch {
            return false;
        }
    }
    async addMemory(params) {
        return this.request('/api/memories', {
            method: 'POST',
            body: params,
        });
    }
    async getMemory(id) {
        return this.request(`/api/memories/${id}`);
    }
    async updateMemory(id, params) {
        return this.request(`/api/memories/${id}`, {
            method: 'PUT',
            body: params,
        });
    }
    async deleteMemory(id) {
        return this.request(`/api/memories/${id}`, {
            method: 'DELETE',
        });
    }
    async listMemories(params = {}) {
        const qs = new URLSearchParams();
        if (params.limit)
            qs.set('limit', String(params.limit));
        if (params.offset)
            qs.set('offset', String(params.offset));
        if (params.category)
            qs.set('category', params.category);
        const query = qs.toString();
        return this.request(`/api/memories${query ? `?${query}` : ''}`);
    }
    async search(params) {
        const qs = new URLSearchParams({ q: params.q });
        if (params.limit)
            qs.set('limit', String(params.limit));
        if (params.min_relevance)
            qs.set('min_relevance', String(params.min_relevance));
        return this.request(`/api/search?${qs.toString()}`);
    }
    async stats() {
        return this.request('/api/stats');
    }
    async tags() {
        return this.request('/api/tags');
    }
    async export() {
        return this.request('/api/export');
    }
    /**
     * Auto-start the MindForge REST API server as a child process.
     * Only called when autoStart is true and the server is not already running.
     */
    async ensureRunning() {
        if (await this.isRunning()) {
            return true;
        }
        if (!this.config.autoStart) {
            throw new Error(`MindForge API not running at ${this.baseUrl} and autoStart is disabled. ` +
                `Start it manually: mindforge --db-path <path> serve --api --port ${this.config.port}`);
        }
        const { spawn } = await import('child_process');
        const pythonPath = this.config.pythonPath || 'python3';
        const mfPath = this.config.mindforgePath;
        if (!mfPath) {
            throw new Error('mindforgePath not configured. Set it in cordis.patch.yml or start MindForge manually.');
        }
        const dbPath = this.config.dbPath || 'mindforge_agent.db';
        const args = [
            '-m', 'cli.main',
            '--db-path', dbPath,
            'serve',
            '--api',
            '--host', this.config.host,
            '--port', String(this.config.port),
        ];
        const child = spawn(pythonPath, args, {
            cwd: mfPath,
            stdio: 'pipe',
            detached: false,
            env: { ...process.env, PYTHONUNBUFFERED: '1' },
        });
        child.stdout?.on('data', (data) => {
            console.log(`[mindforge] ${data.toString().trim()}`);
        });
        child.stderr?.on('data', (data) => {
            console.error(`[mindforge] ${data.toString().trim()}`);
        });
        child.on('error', (err) => {
            console.error(`[mindforge] process error: ${err.message}`);
        });
        // Wait for the server to be ready (max 10 seconds)
        for (let i = 0; i < 20; i++) {
            await new Promise(resolve => setTimeout(resolve, 500));
            if (await this.isRunning()) {
                console.log(`[mindforge] REST API started at ${this.baseUrl}`);
                return true;
            }
        }
        throw new Error(`MindForge API failed to start within 10 seconds at ${this.baseUrl}`);
    }
}
//# sourceMappingURL=mindforge-client.js.map