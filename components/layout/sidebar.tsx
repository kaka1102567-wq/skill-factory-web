"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, PlusCircle, FolderOpen,
  Package, Database, Settings, Factory, ChevronLeft, ChevronRight
} from "lucide-react";
import { useState, useEffect } from "react";
import { cn, getStatusColor } from "@/lib/utils";
import type { Build } from "@/types/build";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/build/new", label: "New Build", icon: PlusCircle },
  { href: "/templates", label: "Templates", icon: FolderOpen },
  { href: "/library", label: "Skills Library", icon: Package },
  { href: "/baselines", label: "Baselines", icon: Database },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [recentBuilds, setRecentBuilds] = useState<Build[]>([]);

  useEffect(() => {
    fetch("/api/builds?limit=5")
      .then((res) => res.json())
      .then((data) => setRecentBuilds(Array.isArray(data) ? data.slice(0, 5) : []))
      .catch(() => {});
  }, [pathname]);

  return (
    <aside
      className={cn(
        "h-screen sticky top-0 flex flex-col border-r border-border bg-card transition-all duration-300",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0">
          <Factory className="w-4 h-4 text-white" />
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <h1 className="text-sm font-bold text-foreground truncate">Skill Factory</h1>
            <p className="text-xs text-muted-foreground">v1.0</p>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="ml-auto p-1 rounded-md hover:bg-accent text-muted-foreground"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-indigo-600/10 text-indigo-400 border-l-2 border-indigo-500"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground border-l-2 border-transparent"
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}

        {/* Recent Builds */}
        {!collapsed && recentBuilds.length > 0 && (
          <div className="pt-6">
            <p className="px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              Recent Builds
            </p>
            {recentBuilds.map((build) => (
              <Link
                key={build.id}
                href={`/build/${build.id}`}
                className="flex items-center justify-between px-3 py-2 rounded-lg text-xs hover:bg-accent transition-colors group"
              >
                <span className="text-muted-foreground group-hover:text-foreground truncate">
                  {build.name}
                </span>
                <span className={cn("font-mono text-xs", getStatusColor(build.status))}>
                  {build.status === "completed" && build.quality_score
                    ? `${Math.round(build.quality_score)}%`
                    : build.status === "running"
                    ? `${build.phase_progress}%`
                    : build.status.charAt(0).toUpperCase()}
                </span>
              </Link>
            ))}
          </div>
        )}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="px-4 py-3 border-t border-border">
          <p className="text-xs text-muted-foreground">XS10K Team</p>
        </div>
      )}
    </aside>
  );
}
