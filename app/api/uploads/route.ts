import { NextResponse } from "next/server";
import { mkdirSync, existsSync, createWriteStream, unlinkSync } from "fs";
import path from "path";
import { v4 as uuidv4 } from "uuid";
import { Readable } from "stream";
import busboy from "busboy";

export const runtime = "nodejs";
export const maxDuration = 300;

const ALLOWED_EXTENSIONS = [".txt", ".md", ".pdf", ".json", ".yaml", ".yml", ".csv"];
const MAX_FILE_SIZE = 200 * 1024 * 1024; // 200MB per file

/**
 * Upload files via streaming multipart parsing (busboy).
 * Bypasses Next.js default body size limit for req.formData().
 * Supports files up to 200MB each. Frontend sends 1 file per request.
 */
export async function POST(req: Request) {
  const contentType = req.headers.get("content-type") || "";

  if (!contentType.includes("multipart/form-data")) {
    return NextResponse.json({ error: "Expected multipart/form-data" }, { status: 400 });
  }

  return new Promise<NextResponse>((resolve) => {
    // Guard against double-resolve from concurrent error/close events
    let resolved = false;
    const safeResolve = (res: NextResponse) => {
      if (!resolved) { resolved = true; resolve(res); }
    };

    const fields: Record<string, string> = {};
    const uploadedFiles: { name: string; path: string; size: number; type: string }[] = [];
    const pendingWrites: Promise<void>[] = [];
    let uploadDir: string | null = null;
    let validationError: string | null = null;
    // Track file path for cleanup on stream errors
    let currentFilePath: string | null = null;

    const bb = busboy({
      headers: { "content-type": contentType },
      limits: { fileSize: MAX_FILE_SIZE, files: 1 }, // 1 file per request
    });

    bb.on("field", (name, val) => {
      fields[name] = val;
    });

    bb.on("file", (_fieldname, fileStream, info) => {
      const filename = info.filename;
      const ext = path.extname(filename).toLowerCase();

      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        validationError = `File type not allowed: ${ext}. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`;
        fileStream.resume();
        return;
      }

      // Lazily create upload dir on first file
      if (!uploadDir) {
        const existing = fields["upload_dir"];
        if (existing && existsSync(existing)) {
          uploadDir = existing;
        } else {
          uploadDir = path.join(process.cwd(), "data", "uploads", uuidv4());
          mkdirSync(uploadDir, { recursive: true });
        }
      }

      const filePath = path.join(uploadDir, filename);
      currentFilePath = filePath;
      const ws = createWriteStream(filePath);
      let fileSize = 0;
      let truncated = false;

      fileStream.on("data", (chunk: Buffer) => {
        fileSize += chunk.length;
      });

      fileStream.on("limit", () => {
        truncated = true;
      });

      // Handle file stream errors (e.g. client disconnect mid-upload)
      fileStream.on("error", (err) => {
        console.error(`[UPLOAD] File stream error for ${filename}:`, err);
        ws.destroy();
        try { unlinkSync(filePath); } catch { /* ignore */ }
      });

      const writePromise = new Promise<void>((resolveWrite) => {
        ws.on("close", () => {
          if (truncated) {
            validationError = `File too large: ${filename} (>${(MAX_FILE_SIZE / 1024 / 1024).toFixed(0)}MB limit)`;
            try { unlinkSync(filePath); } catch { /* ignore */ }
          } else if (fileSize > 0) {
            const type = ext === ".pdf" ? "pdf" : ext === ".md" ? "markdown" : "text";
            uploadedFiles.push({ name: filename, path: filePath, size: fileSize, type });
          }
          resolveWrite();
        });
        ws.on("error", (err) => {
          console.error(`[UPLOAD] Write stream error for ${filename}:`, err);
          try { unlinkSync(filePath); } catch { /* ignore */ }
          resolveWrite();
        });
      });
      pendingWrites.push(writePromise);

      fileStream.pipe(ws);
    });

    bb.on("close", async () => {
      await Promise.all(pendingWrites);

      if (validationError) {
        safeResolve(NextResponse.json({ error: validationError }, { status: 400 }));
        return;
      }

      if (uploadedFiles.length === 0) {
        safeResolve(NextResponse.json({ error: "No valid files uploaded" }, { status: 400 }));
        return;
      }

      safeResolve(
        NextResponse.json({
          upload_dir: uploadDir,
          files: uploadedFiles,
          total_size: uploadedFiles.reduce((sum, f) => sum + f.size, 0),
        }),
      );
    });

    bb.on("error", (err) => {
      const msg = err instanceof Error ? err.message : String(err);
      console.error("[UPLOAD] Busboy error:", msg);
      // Clean up partial file on stream cut
      if (currentFilePath) {
        try { unlinkSync(currentFilePath); } catch { /* ignore */ }
      }
      // "Unexpected end of form" = client disconnected or proxy cut the stream
      const userMsg = msg.includes("Unexpected end of form")
        ? "Upload stream interrupted — file transfer was cut off (client timeout or network issue)"
        : `Upload failed: ${msg}`;
      safeResolve(NextResponse.json({ error: userMsg }, { status: 400 }));
    });

    // Pipe Web ReadableStream → Node.js Readable → busboy
    if (!req.body) {
      safeResolve(NextResponse.json({ error: "No request body" }, { status: 400 }));
      return;
    }

    try {
      const nodeStream = Readable.fromWeb(req.body as import("stream/web").ReadableStream);
      nodeStream.on("error", (err) => {
        console.error("[UPLOAD] Stream read error:", err);
        if (currentFilePath) {
          try { unlinkSync(currentFilePath); } catch { /* ignore */ }
        }
        safeResolve(NextResponse.json(
          { error: `Stream interrupted: ${err.message}` },
          { status: 400 },
        ));
      });
      nodeStream.pipe(bb);
    } catch (err) {
      console.error("[UPLOAD] Failed to create stream:", err);
      safeResolve(NextResponse.json({ error: "Failed to process upload" }, { status: 500 }));
    }
  });
}
