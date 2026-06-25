import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import AlertCard from "./AlertCard";
import type { AlertDTO } from "@/types/alert";
import type { AccountDTO } from "@/types/account";

interface AlertStreamProps {
  alerts: AlertDTO[];
  isLoading?: boolean;
  onExecute?: (alertId: number, comment: string, accountIds: number[]) => Promise<void>;
  accounts?: AccountDTO[];
}

function AlertStream({ alerts, isLoading = false, onExecute, accounts = [] }: AlertStreamProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const toggleExpand = (id: number) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <Card data-testid="alert-stream-zone" className="h-full">
      <CardHeader>
        <CardTitle className="text-lg">告警流</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[calc(100%-3rem)]">
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : alerts.length === 0 ? (
            <div className="text-muted-foreground text-center py-8">
              暂无告警, 监控中...
            </div>
          ) : (
            <div className="space-y-2">
              {alerts.map((alert) => (
                <div key={alert.id} className="animate-in slide-in-from-top">
                  <Alert
                    data-testid="alert-item"
                    variant={alert.alert_type === "dropped_out" ? "destructive" : "default"}
                    className="relative"
                  >
                    <AlertTitle>{alert.message}</AlertTitle>
                    <AlertDescription>
                      {alert.alert_type} | ID: {alert.id}
                    </AlertDescription>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="absolute top-1 right-1 h-6 w-6"
                      data-testid={`alert-expand-${alert.id}`}
                      onClick={() => toggleExpand(alert.id)}
                    >
                      {expandedId === alert.id ? "−" : "+"}
                    </Button>
                  </Alert>
                  {expandedId === alert.id && (
                    <AlertCard alert={alert} accounts={accounts} onExecute={onExecute} />
                  )}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

export default AlertStream;
