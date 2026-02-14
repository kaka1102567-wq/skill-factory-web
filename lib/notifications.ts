import { getSetting } from "./db";
import { formatCost, formatDuration } from "./utils";
import type { Build } from "@/types/build";

export async function notifyBuildComplete(build: Build): Promise<void> {
  const token = getSetting("notification_telegram_token");
  const chatId = getSetting("notification_telegram_chat_id");
  if (!token || !chatId) return;

  const emoji = build.status === "completed" ? "✅" : "❌";
  const quality = build.quality_score ? `${Math.round(build.quality_score)}/100` : "N/A";
  const atoms = build.atoms_verified || build.atoms_extracted || 0;

  const text =
    `${emoji} *Skill Factory*\n\n` +
    `📦 *${build.name}*\n` +
    `Status: ${build.status}\n` +
    `Quality: ${quality}\n` +
    `Atoms: ${atoms}\n` +
    `Cost: ${formatCost(build.api_cost_usd)}\n` +
    `Time: ${formatDuration(build.started_at, build.completed_at)}`;

  try {
    await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text,
        parse_mode: "Markdown",
      }),
    });
    console.log(`[NOTIFY] Telegram sent for build ${build.id}`);
  } catch (err) {
    console.error(`[NOTIFY] Telegram failed:`, err);
  }
}

export async function testTelegramConnection(token: string, chatId: string): Promise<boolean> {
  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text: "🏭 Skill Factory — Test notification thành công!",
      }),
    });
    return res.ok;
  } catch {
    return false;
  }
}
