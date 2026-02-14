import { NextResponse } from "next/server";
import { getBuild } from "@/lib/db";
import { enqueueBuild } from "@/lib/build-queue";

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const build = getBuild(id);
  if (!build)
    return NextResponse.json({ error: "Build not found" }, { status: 404 });

  const { buildId, position } = enqueueBuild({
    name: `${build.name} (retry)`,
    domain: build.domain,
    config_yaml: build.config_yaml,
    template_id: build.template_id,
    created_by: "web",
  });

  return NextResponse.json(
    {
      id: buildId,
      status: position === 0 ? "running" : "queued",
      queue_position: position,
    },
    { status: 201 }
  );
}
