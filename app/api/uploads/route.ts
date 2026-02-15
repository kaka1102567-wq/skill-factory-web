import { NextResponse } from "next/server";
import { writeFile, mkdir } from "fs/promises";
import path from "path";
import { v4 as uuidv4 } from "uuid";

const ALLOWED_EXTENSIONS = [".txt", ".md", ".pdf", ".json", ".yaml", ".yml", ".csv"];
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

export async function POST(req: Request) {
  try {
    const formData = await req.formData();
    const files = formData.getAll("files") as File[];

    if (!files || files.length === 0) {
      return NextResponse.json({ error: "No files uploaded" }, { status: 400 });
    }

    const uploadDir = path.join(process.cwd(), "data", "uploads", uuidv4());
    await mkdir(uploadDir, { recursive: true });

    const uploadedFiles: { name: string; path: string; size: number; type: string }[] = [];

    for (const file of files) {
      const ext = path.extname(file.name).toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        return NextResponse.json(
          { error: `File type not allowed: ${ext}. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}` },
          { status: 400 },
        );
      }
      if (file.size > MAX_FILE_SIZE) {
        return NextResponse.json(
          { error: `File too large: ${file.name} (${(file.size / 1024 / 1024).toFixed(1)}MB). Max: 50MB` },
          { status: 400 },
        );
      }

      const bytes = await file.arrayBuffer();
      const buffer = Buffer.from(bytes);
      const filePath = path.join(uploadDir, file.name);
      await writeFile(filePath, buffer);

      const type = ext === ".pdf" ? "pdf" : ext === ".md" ? "markdown" : "text";
      uploadedFiles.push({ name: file.name, path: filePath, size: file.size, type });
    }

    return NextResponse.json({
      upload_dir: uploadDir,
      files: uploadedFiles,
      total_size: uploadedFiles.reduce((sum, f) => sum + f.size, 0),
    });
  } catch (error) {
    console.error("[UPLOAD] Error:", error);
    return NextResponse.json({ error: "Upload failed" }, { status: 500 });
  }
}
