import { NextResponse } from "next/server";
import { v4 as uuidv4 } from "uuid";
import { getBaselines, createBaseline, updateBaseline, deleteBaseline } from "@/lib/db";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const domain = searchParams.get("domain") || undefined;
  const baselines = getBaselines(domain);
  return NextResponse.json(baselines);
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { domain, name, config_path, seekers_output_dir, source_urls } = body;

    if (!domain || !name) {
      return NextResponse.json({ error: "domain and name are required" }, { status: 400 });
    }

    const baseline = createBaseline({
      id: `bl-${uuidv4().slice(0, 8)}`,
      domain,
      name,
      config_path,
      seekers_output_dir,
      source_urls,
    });

    return NextResponse.json(baseline, { status: 201 });
  } catch (error) {
    console.error("[API] Error creating baseline:", error);
    return NextResponse.json({ error: "Failed to create baseline" }, { status: 500 });
  }
}

export async function PUT(req: Request) {
  try {
    const body = await req.json();
    const { id, ...updates } = body;

    if (!id) {
      return NextResponse.json({ error: "id is required" }, { status: 400 });
    }

    updateBaseline(id, updates);
    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("[API] Error updating baseline:", error);
    return NextResponse.json({ error: "Failed to update baseline" }, { status: 500 });
  }
}

export async function DELETE(req: Request) {
  const { searchParams } = new URL(req.url);
  const id = searchParams.get("id");

  if (!id) {
    return NextResponse.json({ error: "id is required" }, { status: 400 });
  }

  deleteBaseline(id);
  return NextResponse.json({ ok: true });
}
