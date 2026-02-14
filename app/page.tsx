import Link from "next/link";
import { PlusCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatsBar } from "@/components/dashboard/stats-bar";
import { RecentBuilds } from "@/components/dashboard/recent-builds";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Tổng quan về tất cả AI skills đã build
          </p>
        </div>
        <Link href="/build/new">
          <Button className="gap-2">
            <PlusCircle className="w-4 h-4" />
            New Build
          </Button>
        </Link>
      </div>

      {/* Stats */}
      <StatsBar />

      {/* Builds list */}
      <div>
        <h2 className="text-lg font-semibold text-foreground mb-4">Builds</h2>
        <RecentBuilds />
      </div>
    </div>
  );
}
