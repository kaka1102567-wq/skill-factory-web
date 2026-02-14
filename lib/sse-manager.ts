type SSEClient = (event: string, data: unknown) => void;

class SSEManager {
  private clients: Map<string, Set<SSEClient>> = new Map();

  addClient(buildId: string, client: SSEClient): void {
    if (!this.clients.has(buildId)) {
      this.clients.set(buildId, new Set());
    }
    this.clients.get(buildId)!.add(client);
    console.log(`[SSE] Client connected to build ${buildId}. Total: ${this.clients.get(buildId)!.size}`);
  }

  removeClient(buildId: string, client: SSEClient): void {
    const clients = this.clients.get(buildId);
    if (clients) {
      clients.delete(client);
      console.log(`[SSE] Client disconnected from build ${buildId}. Remaining: ${clients.size}`);
      if (clients.size === 0) {
        this.clients.delete(buildId);
      }
    }
  }

  broadcast(buildId: string, event: string, data: unknown): void {
    const clients = this.clients.get(buildId);
    if (!clients || clients.size === 0) return;

    const deadClients: SSEClient[] = [];
    for (const client of clients) {
      try {
        client(event, data);
      } catch {
        deadClients.push(client);
      }
    }
    for (const dead of deadClients) {
      clients.delete(dead);
    }
  }

  getClientCount(buildId: string): number {
    return this.clients.get(buildId)?.size || 0;
  }

  hasClients(buildId: string): boolean {
    return (this.clients.get(buildId)?.size || 0) > 0;
  }
}

// Singleton — survives hot reload in dev
const globalForSSE = globalThis as unknown as { sseManager: SSEManager };
export const sseManager = globalForSSE.sseManager || new SSEManager();
if (process.env.NODE_ENV !== "production") {
  globalForSSE.sseManager = sseManager;
}
