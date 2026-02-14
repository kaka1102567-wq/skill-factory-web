import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
    const { token, chat_id } = await req.json();
    if (!token || !chat_id) {
      return NextResponse.json({ ok: false, error: "Token và Chat ID là bắt buộc" });
    }

    const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chat_id,
        text: "🏭 Skill Factory — Test notification thành công!",
      }),
    });

    const data = await res.json();
    console.log("[TEST-TELEGRAM] Response:", res.status, JSON.stringify(data));

    return NextResponse.json({ ok: data.ok === true });
  } catch (err) {
    console.error("[TEST-TELEGRAM] Error:", err);
    return NextResponse.json({ ok: false, error: String(err) });
  }
}
