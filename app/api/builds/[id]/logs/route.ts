import { getBuild, getBuildLogs } from "@/lib/db";
import { sseManager } from "@/lib/sse-manager";

// Required for SSE streaming
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const build = getBuild(id);
  if (!build) {
    return new Response("Build not found", { status: 404 });
  }

  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      const send = (event: string, data: unknown) => {
        try {
          const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
          controller.enqueue(encoder.encode(payload));
        } catch {
          // Controller closed
        }
      };

      // Send initial build state
      send("state", {
        status: build.status,
        current_phase: build.current_phase,
        phase_progress: build.phase_progress,
        quality_score: build.quality_score,
      });

      // Send existing logs (catch up)
      const existingLogs = getBuildLogs(id, 500);
      for (const log of existingLogs) {
        send("log", {
          level: log.level,
          phase: log.phase,
          message: log.message,
          timestamp: log.timestamp,
        });
      }

      // If build already finished, send complete and close
      if (["completed", "failed"].includes(build.status)) {
        send("complete", {
          status: build.status,
          quality_score: build.quality_score,
          package_path: build.package_path,
          completed_at: build.completed_at,
        });
        controller.close();
        return;
      }

      // Register for live updates
      sseManager.addClient(id, send);

      // Keep-alive ping every 15 seconds
      const keepAlive = setInterval(() => {
        try {
          controller.enqueue(encoder.encode(": keep-alive\n\n"));
        } catch {
          clearInterval(keepAlive);
        }
      }, 15000);

      // Cleanup on disconnect
      req.signal.addEventListener("abort", () => {
        clearInterval(keepAlive);
        sseManager.removeClient(id, send);
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "Connection": "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
