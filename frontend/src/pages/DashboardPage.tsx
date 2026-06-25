import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function DashboardPage() {
  return (
    <div data-testid="dashboard-root" className="h-full">
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
      <div className="grid grid-cols-[2fr_1fr_1fr] grid-rows-2 gap-6 h-[calc(100vh-8rem)]">
        {/* Left-top: Hot Comments Leaderboard */}
        <Card data-testid="hot-comments-zone" className="row-start-1 col-start-1">
          <CardHeader>
            <CardTitle className="text-lg">Hot Comments Leaderboard</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-[90%]" />
            <Skeleton className="h-8 w-[95%]" />
            <Skeleton className="h-8 w-[85%]" />
            <Skeleton className="h-8 w-[80%]" />
          </CardContent>
        </Card>

        {/* Right-top: Statistics */}
        <Card data-testid="stats-zone" className="row-start-1 col-start-2">
          <CardHeader>
            <CardTitle className="text-lg">Statistics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-4 w-[60%]" />
            <Skeleton className="h-4 w-[80%]" />
          </CardContent>
        </Card>

        {/* Left-bottom: Team Member Status */}
        <Card data-testid="member-status-zone" className="row-start-2 col-start-1">
          <CardHeader>
            <CardTitle className="text-lg">Team Member Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="grid grid-cols-5 gap-2">
              {Array.from({ length: 20 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Right-bottom: Alert Stream */}
        <Card data-testid="alert-stream-zone" className="row-start-2 col-start-2">
          <CardHeader>
            <CardTitle className="text-lg">Alert Stream</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </CardContent>
        </Card>

        {/* Middle: Operation Area */}
        <Card className="col-start-2 row-span-2 col-start-3">
          <CardHeader>
            <CardTitle className="text-lg">Operation Area</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default DashboardPage;
