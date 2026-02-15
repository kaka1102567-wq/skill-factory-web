import { NextResponse } from "next/server";
import { getBaselineForDomain } from "@/lib/baseline-registry";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ domain: string }> },
) {
  const { domain } = await params;
  const info = getBaselineForDomain(domain);

  // Never expose internal file paths to the client
  const { path: _path, ...safe } = info;
  return NextResponse.json(safe);
}
