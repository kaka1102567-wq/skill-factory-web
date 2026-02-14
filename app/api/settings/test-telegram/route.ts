import { NextResponse } from "next/server";
import { testTelegramConnection } from "@/lib/notifications";

export async function POST(req: Request) {
  const { token, chat_id } = await req.json();
  if (!token || !chat_id) {
    return NextResponse.json({ ok: false, error: "Token và Chat ID là bắt buộc" });
  }
  const ok = await testTelegramConnection(token, chat_id);
  return NextResponse.json({ ok });
}
