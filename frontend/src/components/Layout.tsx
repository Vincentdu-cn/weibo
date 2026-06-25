import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Menu, Monitor, LogIn, BarChart3, Play, Circle } from "lucide-react";
import { useCompetitionStore } from "@/stores/competitionStore";

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const { status } = useCompetitionStore();

  const navItems = [
    { path: "/", label: "Setup", icon: Monitor },
    { path: "/login", label: "Login", icon: LogIn },
    { path: "/dashboard", label: "Dashboard", icon: BarChart3 },
    { path: "/replay", label: "Replay", icon: Play },
  ];

  const statusColor =
    status === "running"
      ? "bg-success"
      : status === "idle"
      ? "bg-muted-foreground"
      : "bg-warning";

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Nav Header */}
      <header className="sticky top-0 z-sticky border-b border-border bg-card/80 backdrop-blur px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Mobile Menu */}
          <Sheet>
            <SheetTrigger asChild className="md:hidden">
              <Button variant="ghost" size="icon" aria-label="Open menu">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[280px]">
              <nav className="flex flex-col gap-2 mt-8">
                {navItems.map((item) => (
                  <Link key={item.path} to={item.path}>
                    <Button
                      variant={location.pathname === item.path ? "secondary" : "ghost"}
                      className="w-full justify-start"
                    >
                      <item.icon className="mr-2 h-4 w-4" />
                      {item.label}
                    </Button>
                  </Link>
                ))}
              </nav>
            </SheetContent>
          </Sheet>

          {/* Logo */}
          <Link to="/" className="font-bold text-lg tracking-tight">
            Weibo Monitor
          </Link>
        </div>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-1">
          {navItems.map((item) => (
            <Link key={item.path} to={item.path}>
              <Button
                variant={location.pathname === item.path ? "secondary" : "ghost"}
                size="sm"
              >
                <item.icon className="mr-2 h-4 w-4" />
                {item.label}
              </Button>
            </Link>
          ))}
        </nav>

        {/* Status Badge */}
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="gap-1.5 font-normal">
            <Circle className={`h-2 w-2 rounded-full ${statusColor} animate-pulse`} />
            <span className="capitalize">{status}</span>
          </Badge>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 p-4 md:p-6 overflow-auto">
        {children}
      </main>
    </div>
  );
}
