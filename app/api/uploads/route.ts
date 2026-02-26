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
 * Supports files up to 200MB each, unlimited total request size.
 */
export async function POST(req: Request) {
  const contentType = req.headers.get("content-type") || "";

  if (!contentType.includes("multipart/form-data")) {
    return NextResponse.json({ error: "Expected multipart/form-data" }, { status: 400 });
  }

  return new Promise<NextResponse>((resolve) => {
    const fields: Record<string, string> = {};
    const uploadedFiles: { name: string; path: string; size: number; type: string }[] = [];
    const pendingWrites: Promise<void>[] = [];
    let uploadDir: string | null = null;
    let validationError: string | null = null;

    const bb = busboy({
      headers: { "content-type": contentType },
      limits: { fileSize: MAX_FILE_SIZE, files: 50 },
    });

    // Fields arrive before files (frontend sends upload_dir first)
    bb.on("field", (name, val) => {
      fields[name] = val;
    });

    bb.on("file", (_fieldname, fileStream, info) => {
      const filename = info.filename;
      const ext = path.extname(filename).toLowerCase();

      // Validate extension
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        validationError = `File type not allowed: ${ext}. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`;
        fileStream.resume(); // drain stream
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
      const ws = createWriteStream(filePath);
      let fileSize = 0;
      let truncated = false;

      fileStream.on("data", (chunk: Buffer) => {
        fileSize += chunk.length;
      });

      fileStream.on("limit", () => {
        truncated = true;
      });

      const writePromise = new Promise<void>((resolveWrite) => {
        ws.on("close", () => {
          if (truncated) {
            // File exceeded MAX_FILE_SIZE — busboy truncated it
            validationError = `File too large: ${filename} (>${(MAX_FILE_SIZE / 1024 / 1024).toFixed(0)}MB limit)`;
            // Clean up partial file
            try { unlinkSync(filePath); } catch { /* ignore */ }
          } else {
            const type = ext === ".pdf" ? "pdf" : ext === ".md" ? "markdown" : "text";
            uploadedFiles.push({ name: filename, path: filePath, size: fileSize, type });
          }
          resolveWrite();
        });
      });
      pendingWrites.push(writePromise);

      fileStream.pipe(ws);
    });

    bb.on("close", async () => {
      // Wait for all file writes to finish
      await Promise.all(pendingWrites);

      if (validationError) {
        resolve(NextResponse.json({ error: validationError }, { status: 400 }));
        return;
      }

      if (uploadedFiles.length === 0) {
        resolve(NextResponse.json({ error: "No valid files uploaded" }, { status: 400 }));
        return;
      }

      resolve(
        NextResponse.json({
          upload_dir: uploadDir,
          files: uploadedFiles,
          total_size: uploadedFiles.reduce((sum, f) => sum + f.size, 0),
        }),
      );
    });

    bb.on("error", (err) => {
      console.error("[UPLOAD] Stream parse error:", err);
      const msg = err instanceof Error ? err.message : String(err);
      resolve(NextResponse.json({ error: `Upload failed: ${msg}` }, { status: 500 }));
    });

    // Pipe Web ReadableStream → Node.js Readable → busboy
    if (!req.body) {
      resolve(NextResponse.json({ error: "No request body" }, { status: 400 }));
      return;
    }

    try {
      const nodeStream = Readable.fromWeb(req.body as import("stream/web").ReadableStream);
      nodeStream.on("error", (err) => {
        console.error("[UPLOAD] Stream read error:", err);
        resolve(NextResponse.json({ error: `Stream error: ${err.message}` }, { status: 500 }));
      });
      nodeStream.pipe(bb);
    } catch (err) {
      console.error("[UPLOAD] Failed to create stream:", err);
      resolve(NextResponse.json({ error: "Failed to process upload" }, { status: 500 }));
    }
  });
}
