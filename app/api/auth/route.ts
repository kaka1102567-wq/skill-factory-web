import { NextResponse } from "next/server";
import { isAuthenticated, getAuthCookieConfig } from "@/lib/auth";

export async function GET() {
  const authed = await isAuthenticated();
  return NextResponse.json({ authenticated: authed });
}

export async function POST(req: Request) {
  const { password } = await req.json();
  const correctPassword = process.env.FACTORY_PASSWORD || "skillfactory2025";

  if (password !== correctPassword) {
    return NextResponse.json({ error: "Mật khẩu không đúng" }, { status: 401 });
  }

  const response = NextResponse.json({ success: true });
  const cookieConfig = getAuthCookieConfig();
  response.cookies.set(cookieConfig);
  return response;
}
