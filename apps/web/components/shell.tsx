"use client";

import {
  Bot,
  Boxes,
  FileText,
  LayoutDashboard,
  ScanEye,
  Search,
  ShieldCheck,
  TrendingUp,
  Upload,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { ApiStatus } from "@/components/api-status";
import { cn } from "@/lib/utils";

const NAV: { href: string; label: string; icon: LucideIcon; group: string }[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard, group: "Workspace" },
  { href: "/search", label: "Catalog", icon: Search, group: "Workspace" },
  { href: "/identify", label: "Identify", icon: ScanEye, group: "Workspace" },
  { href: "/chat", label: "Assistant", icon: Bot, group: "Workspace" },
  { href: "/forecast", label: "Forecast", icon: TrendingUp, group: "Workspace" },
  { href: "/documents", label: "Documents", icon: FileText, group: "Data" },
  { href: "/admin/models", label: "Models", icon: Boxes, group: "Admin" },
  { href: "/admin/imports", label: "Imports", icon: Upload, group: "Admin" },
  { href: "/admin/audit", label: "Audit", icon: ShieldCheck, group: "Admin" },
];

function NavItem({ item, active }: { item: (typeof NAV)[number]; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={cn(
        "group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
        active
          ? "bg-white/10 text-white"
          : "text-ink-300 hover:bg-white/5 hover:text-white",
      )}
    >
      <Icon className={cn("h-4 w-4", active ? "text-accent-400" : "text-ink-400 group-hover:text-ink-200")} />
      {item.label}
      {active ? <span className="ml-auto h-1.5 w-1.5 rounded-full bg-accent-400" /> : null}
    </Link>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const groups = ["Workspace", "Data", "Admin"];

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[256px_1fr]">
      <aside className="hidden flex-col bg-ink-950 lg:flex">
        <Link href="/" className="flex items-center gap-3 px-5 py-5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-500 font-mono text-sm font-bold text-white">
            PS
          </span>
          <span>
            <span className="block text-sm font-semibold text-white">PartScope</span>
            <span className="block text-[11px] text-ink-400">Industrial intelligence</span>
          </span>
        </Link>

        <nav className="flex-1 space-y-6 px-3 py-2">
          {groups.map((group) => (
            <div key={group}>
              <p className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-500">
                {group}
              </p>
              <div className="space-y-0.5">
                {NAV.filter((item) => item.group === group).map((item) => (
                  <NavItem
                    key={item.href}
                    item={item}
                    active={item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)}
                  />
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="space-y-3 border-t border-white/10 px-5 py-4">
          <ApiStatus />
          <p className="text-[11px] leading-relaxed text-ink-500">
            Bundled demo dataset is generated and labelled synthetic. Point DATABASE_URL at
            your catalog to run production data.
          </p>
        </div>
      </aside>

      <div className="flex min-h-screen flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-ink-200 bg-white px-4 py-3 lg:hidden">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-500 font-mono text-xs font-bold text-white">
              PS
            </span>
            <span className="text-sm font-semibold">PartScope</span>
          </Link>
          <ApiStatus />
        </header>
        <nav className="scrollbar-thin flex gap-1 overflow-x-auto border-b border-ink-200 bg-white px-3 py-2 lg:hidden">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium",
                pathname === item.href
                  ? "bg-ink-950 text-white"
                  : "text-ink-500 hover:bg-ink-100",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>

        <footer className="border-t border-ink-200 px-6 py-4 text-[11px] text-ink-400">
          PartScope · Industrial parts intelligence · Evidence-first recommendations · Demo data
          is synthetic
        </footer>
      </div>
    </div>
  );
}
