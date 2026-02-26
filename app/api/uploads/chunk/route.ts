import { NextResponse } from "next/server";
import { mkdirSync, existsSync, readdirSync, unlinkSync, rmdirSync, createWriteStream } from "fs";
import { readFile, appendFile, writeFile, unlink, rm } from "fs/promises";
import path from "path";
import { v4 as uuidv4 } from "uuid";

export const runtime = "nodejs";
export const maxDuration = 300;

const ALLOWED_EXTENSIONS = [".txt", ".md", ".pdf", ".json", ".yaml", ".yml", ".csv"];
const MAX_FILE_SIZE = 200 * 1024 * 1024; // 200MB per file

/**
 * Chunked upload endpoint for large files (>8MB).
 * Each chunk is a raw binary POST with metadata in headers.
 * Chunks are ~5MB each, well under proxy body limits.
 *
 * Headers:
 *   X-File-Name:   original filename
 *   X-Chunk-Index:  0-based chunk index
 *   X-Chunk-Total:  total number of chunks
 *   X-Upload-Dir:   (optional) existing upload dir to append to
 */
export async function POST(req: Request) {
  try {
    const rawFileName = req.headers.get("x-file-name");
    const fileName = rawFileName ? decodeURIComponent(rawFileName) : null;
    const chunkIndex = parseInt(req.headers.get("x-chunk-index") || "", 10);
    const chunkTotal = parseInt(req.headers.get("x-chunk-total") || "", 10);
    const existingDir = req.headers.get("x-upload-dir");

    if (!fileName || isNaN(chunkIndex) || isNaN(chunkTotal) || chunkTotal < 1) {
      return NextResponse.json(
        { error: "Missing required headers: X-File-Name, X-Chunk-Index, X-Chunk-Total" },
        { status: 400 },
      );
    }

    const ext = path.extname(fileName).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return NextResponse.json(
        { error: `File type not allowed: ${ext}` },
        { status: 400 },
      );
    }

    // Determine upload dir
    let uploadDir: string;
    if (existingDir && existsSync(existingDir)) {
      uploadDir = existingDir;
    } else if (chunkIndex === 0 && !existingDir) {
      uploadDir = path.join(process.cwd(), "data", "uploads", uuidv4());
      mkdirSync(uploadDir, { recursive: true });
    } else if (existingDir) {
      // First chunk for this dir — create it
      uploadDir = existingDir;
      mkdirSync(uploadDir, { recursive: true });
    } else {
      return NextResponse.json({ error: "X-Upload-Dir required for non-first chunk" }, { status: 400 });
    }

    // Chunks dir: <uploadDir>/.chunks/<sanitized-filename>/
    const safeName = fileName.replace(/[^a-zA-Z0-9._-]/g, "_");
    const chunksDir = path.join(uploadDir, ".chunks", safeName);
    mkdirSync(chunksDir, { recursive: true });

    // Read chunk body and write to disk
    const body = await req.arrayBuffer();
    const chunkPath = path.join(chunksDir, `part_${String(chunkIndex).padStart(4, "0")}`);
    await writeFile(chunkPath, Buffer.from(body));

    // Not the last chunk — return acknowledgment
    if (chunkIndex < chunkTotal - 1) {
      return NextResponse.json({
        status: "chunk_received",
        index: chunkIndex,
        upload_dir: uploadDir,
      });
    }

    // Last chunk — merge all parts into final file
    const parts = readdirSync(chunksDir)
      .filter((f) => f.startsWith("part_"))
      .sort(); // part_0000, part_0001, ...

    if (parts.length !== chunkTotal) {
      return NextResponse.json(
        { error: `Missing chunks: expected ${chunkTotal}, found ${parts.length}` },
        { status: 400 },
      );
    }

    const finalPath = path.join(uploadDir, fileName);
    // Merge chunks by appending sequentially (memory-efficient)
    // Clear any existing file first
    await writeFile(finalPath, Buffer.alloc(0));
    let totalSize = 0;
    for (const part of parts) {
      const partData = await readFile(path.join(chunksDir, part));
      await appendFile(finalPath, partData);
      totalSize += partData.length;
    }

    // Validate total size
    if (totalSize > MAX_FILE_SIZE) {
      await unlink(finalPath);
      await rm(chunksDir, { recursive: true, force: true });
      return NextResponse.json(
        { error: `File too large: ${fileName} (${(totalSize / 1024 / 1024).toFixed(1)}MB). Max: 200MB` },
        { status: 400 },
      );
    }

    // Clean up chunks dir
    await rm(chunksDir, { recursive: true, force: true });
    // Remove .chunks dir if empty
    const parentChunksDir = path.join(uploadDir, ".chunks");
    try {
      const remaining = readdirSync(parentChunksDir);
      if (remaining.length === 0) rmdirSync(parentChunksDir);
    } catch { /* ignore */ }

    const type = ext === ".pdf" ? "pdf" : ext === ".md" ? "markdown" : "text";

    return NextResponse.json({
      upload_dir: uploadDir,
      files: [{ name: fileName, path: finalPath, size: totalSize, type }],
      total_size: totalSize,
    });
  } catch (error) {
    console.error("[UPLOAD CHUNK] Error:", error);
    const msg = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ error: `Chunk upload failed: ${msg}` }, { status: 500 });
  }
}
