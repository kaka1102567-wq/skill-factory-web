import { NextResponse } from "next/server";
import { getBuilds } from "@/lib/db";
import { enqueueBuild, type BuildRequest } from "@/lib/build-queue";
import { generateConfigYaml } from "@/lib/config-generator";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const status = searchParams.get("status") || undefined;
  const builds = getBuilds(status);
  return NextResponse.json(builds);
}

export async function POST(req: Request) {
  try {
    const body = await req.json();

    const {
      name,
      domain,
      config_yaml,
      template_id,
      created_by = "web",
      language,
      quality_tier,
      platforms,
      baseline_urls,
    } = body;

    if (!name) {
      return NextResponse.json({ error: "Build name is required" }, { status: 400 });
    }

    let finalConfigYaml = config_yaml;
    if (!finalConfigYaml) {
      finalConfigYaml = generateConfigYaml({
        name,
        domain: domain || "custom",
        language: language || "vi",
        quality_tier: quality_tier || "standard",
        platforms: platforms || ["claude"],
        baseline_urls: baseline_urls || [],
      });
    }

    const request: BuildRequest = {
      name,
      domain: domain || "custom",
      config_yaml: finalConfigYaml,
      template_id: template_id || null,
      created_by,
      files: body.files || [],
    };

    const { buildId, position } = enqueueBuild(request);

    return NextResponse.json({
      id: buildId,
      status: position === 0 ? "running" : "queued",
      queue_position: position,
      message: position === 0
        ? "Build is running"
        : `Build queued (position #${position})`,
    }, { status: 201 });

  } catch (error) {
    console.error("[API] Error creating build:", error);
    return NextResponse.json(
      { error: "Failed to create build", detail: String(error) },
      { status: 500 }
    );
  }
}
