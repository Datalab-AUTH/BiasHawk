import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { TopNav } from "@/components/top-nav";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <main className="flex min-h-dvh w-full flex-1 flex-col">
        <div className="flex h-16 shrink-0 items-center border-b">
          <SidebarTrigger className="ml-2" />
          <TopNav />
        </div>
        <div className="flex-1 p-6 lg:p-10">{children}</div>
      </main>
    </SidebarProvider>
  );
}
