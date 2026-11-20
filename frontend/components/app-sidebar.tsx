"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  BellRing,
  ChartLine,
  ChevronDown,
  Columns3Cog,
  FileChartPie,
  FileWarning,
  Files,
  Grid2x2Check,
  Loader2,
  MonitorCog,
  Settings,
  UserCog,
  UserRoundPlus,
} from "lucide-react";

import { api } from "@/lib/api";
import { useSelection } from "@/lib/store";
import type { Job, JobKind } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ScopeSwitcher } from "@/components/dashboard/scope-switcher";

type MenuItem = {
  title: string;
  url: string;
  icon: React.ElementType;
  /** The job whose state drives this item's indicator. */
  kind?: JobKind;
  children?: { title: string; url: string }[];
  /** True when the link needs a selected instance to be meaningful. */
  needsInstance?: boolean;
  /**
   * Only highlight on an exact path match, not on any nested route.
   *
   * "Project Setup" links to `/dashboard/use-cases`, which is the prefix of
   * every other dashboard route , without this it would stay highlighted
   * everywhere.
   */
  exact?: boolean;
};

const ACCOUNT_ITEMS: MenuItem[] = [
  { title: "Profile", url: "/profile", icon: UserCog },
  { title: "Settings", url: "/settings", icon: Settings },
  { title: "User Files", url: "/user-files", icon: Files },
];

const OTHER_ITEMS: MenuItem[] = [
  { title: "Membership", url: "/membership", icon: UserRoundPlus },
  { title: "Notifications", url: "/notifications", icon: BellRing },
];

export function AppSidebar() {
  const { open } = useSidebar();
  const pathname = usePathname();
  const useCaseId = useSelection((s) => s.selectedUseCaseId);
  const instanceId = useSelection((s) => s.selectedInstanceId);
  const hasHydrated = useSelection((s) => s.hasHydrated);

  const base = `/dashboard/use-cases/${useCaseId}/instances/${instanceId}`;

  const dashboardItems: MenuItem[] = useMemo(
    () => [
      { title: "Project Setup", url: "/dashboard/use-cases", icon: MonitorCog, exact: true },
      {
        title: "Data Governance",
        url: `${base}/data-gov`,
        icon: Columns3Cog,
        kind: "data_governance",
        needsInstance: true,
      },
      {
        title: "Data Quality",
        url: `${base}/data-quality`,
        icon: Grid2x2Check,
        kind: "data_quality",
        needsInstance: true,
      },
      {
        title: "Bias Analysis",
        url: `${base}/bias-analysis/setup`,
        icon: FileChartPie,
        kind: "bias_assessment",
        needsInstance: true,
        children: [
          { title: "Setup", url: `${base}/bias-analysis/setup` },
          { title: "Report", url: `${base}/bias-analysis/report` },
        ],
      },
      {
        title: "Bias Drift",
        url: `${base}/bias-drift`,
        icon: ChartLine,
        kind: "drift",
        needsInstance: true,
      },
      {
        title: "Risk Assessment",
        url: `${base}/risk-assessment`,
        icon: FileWarning,
        kind: "risk_assessment",
        needsInstance: true,
      },
    ],
    [base]
  );

  // Job state for the selected instance drives the per-item indicators.
  const { data: jobs } = useQuery({
    queryKey: ["jobs", "instances", instanceId],
    enabled: Boolean(instanceId),
    queryFn: () => api.get<Job[]>(`/instances/${instanceId}/jobs`),
    refetchInterval: (query) =>
      query.state.data?.some((j) => j.status === "queued" || j.status === "running")
        ? 4000
        : false,
    refetchIntervalInBackground: true,
  });

  const stateByKind = useMemo(() => {
    const latest: Partial<Record<JobKind, Job>> = {};
    for (const job of jobs ?? []) if (!latest[job.kind]) latest[job.kind] = job;
    return latest;
  }, [jobs]);

  const [openMenu, setOpenMenu] = useState<string | null>(null);
  useEffect(() => {
    const current = dashboardItems.find((item) =>
      item.children?.some((child) => pathname === child.url)
    );
    setOpenMenu(current?.title ?? null);
  }, [pathname, dashboardItems]);

  const isActive = (url: string, exact?: boolean) =>
    pathname === url || (!exact && pathname.startsWith(`${url}/`));

  // Until the persisted selection is read, contextual links would point at
  // "/instances/null". Treat that as unselected rather than rendering a
  // link that 404s the moment someone clicks it.
  const instanceReady = hasHydrated && Boolean(useCaseId && instanceId);

  const withTooltip = (node: React.ReactNode, label: string) =>
    open ? (
      <>{node}</>
    ) : (
      <Tooltip>
        <TooltipTrigger asChild>{node}</TooltipTrigger>
        <TooltipContent side="right">{label}</TooltipContent>
      </Tooltip>
    );

  function StatusDot({ item }: { item: MenuItem }) {
    if (!item.kind || !instanceReady) return null;
    const job = stateByKind[item.kind];
    if (!job) return null;
    if (job.status === "queued" || job.status === "running") {
      return <Loader2 className="ml-auto size-3.5 shrink-0 animate-spin text-sidebar-foreground/60" />;
    }
    if (job.status === "done") {
      return (
        <span
          className="ml-auto size-2 shrink-0 rounded-full bg-emerald-500"
          aria-label="Ready"
        />
      );
    }
    return (
      <span
        className="ml-auto size-2 shrink-0 rounded-full bg-destructive"
        aria-label="Failed"
      />
    );
  }

  function renderItem(item: MenuItem) {
    const disabled = item.needsInstance && !instanceReady;

    if (item.children) {
      return (
        <Collapsible
          key={item.title}
          open={openMenu === item.title}
          onOpenChange={(next) => setOpenMenu(next ? item.title : null)}
        >
          <SidebarMenuItem>
            <CollapsibleTrigger asChild>
              <SidebarMenuButton
                className={cn(disabled && "pointer-events-none opacity-50")}
                isActive={isActive(item.url, item.exact)}
              >
                <item.icon />
                <span>{item.title}</span>
                <StatusDot item={item} />
                <ChevronDown
                  className={cn(
                    "size-4 shrink-0 transition-transform",
                    openMenu === item.title && "rotate-180"
                  )}
                />
              </SidebarMenuButton>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <SidebarMenuSub>
                {item.children.map((child) => (
                  <SidebarMenuSubItem key={child.title}>
                    <SidebarMenuSubButton asChild isActive={pathname === child.url}>
                      <Link href={disabled ? "/dashboard/use-cases" : child.url}>
                        {child.title}
                      </Link>
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                ))}
              </SidebarMenuSub>
            </CollapsibleContent>
          </SidebarMenuItem>
        </Collapsible>
      );
    }

    const button = (
      <SidebarMenuButton
        asChild
        isActive={isActive(item.url, item.exact)}
        className={cn(disabled && "pointer-events-none opacity-50")}
      >
        <Link href={disabled ? "/dashboard/use-cases" : item.url} aria-disabled={disabled}>
          <item.icon />
          <span>{item.title}</span>
          <StatusDot item={item} />
        </Link>
      </SidebarMenuButton>
    );

    return (
      <SidebarMenuItem key={item.title}>
        {withTooltip(
          button,
          disabled ? `${item.title} , select an instance first` : item.title
        )}
      </SidebarMenuItem>
    );
  }

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <Link href="/dashboard/use-cases" className="flex items-center gap-2 px-2 py-1.5">
          <Image
            src="/biashawk_logo_icon.svg"
            alt=""
            width={26}
            height={26}
            className="shrink-0"
            priority
          />
          {open ? (
            <span className="truncate text-base font-semibold tracking-tight">BiasHawk</span>
          ) : null}
        </Link>
        {open ? <ScopeSwitcher /> : null}
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Dashboard</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{dashboardItems.map(renderItem)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Account</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{ACCOUNT_ITEMS.map(renderItem)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Other</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{OTHER_ITEMS.map(renderItem)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

    </Sidebar>
  );
}
