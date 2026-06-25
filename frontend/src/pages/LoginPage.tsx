import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import { LogOut, RefreshCw } from "lucide-react";
import { useQrLogin } from "@/hooks/useQrLogin";
import { getAccounts, logoutAccount } from "@/api/qr";
import { AccountDTO } from "@/types/account";

function LoginPage() {
  const { qrUrl, status, generate, reset } = useQrLogin();
  const [accounts, setAccounts] = useState<AccountDTO[]>([]);
  const [loading, setLoading] = useState(true);

  const loadAccounts = useCallback(async () => {
    try {
      const data = await getAccounts();
      setAccounts(data);
    } catch {
      // Ignore error — keep empty list
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  const handleLogout = useCallback(async (id: number) => {
    try {
      await logoutAccount(id);
      setAccounts((prev) => prev.filter((a) => a.id !== id));
    } catch {
      // Ignore error
    }
  }, []);

  const handleRefresh = useCallback(() => {
    reset();
    generate();
  }, [reset, generate]);

  const loggedInCount = accounts.length;
  const totalAccounts = 20;
  const progressValue = (loggedInCount / totalAccounts) * 100;

  const getStatusBadge = () => {
    switch (status) {
      case "waiting":
        return <Badge variant="secondary">等待扫码</Badge>;
      case "scanned":
        return (
          <Badge
            variant="outline"
            className="bg-warning text-warning-foreground border-transparent"
          >
            已扫码,等待确认
          </Badge>
        );
      case "success":
        return (
          <Badge
            variant="outline"
            className="bg-success text-success-foreground border-transparent"
          >
            登录成功
          </Badge>
        );
      case "expired":
        return <Badge variant="destructive">二维码已过期</Badge>;
      default:
        return <Badge variant="secondary">等待扫码</Badge>;
    }
  };

  const getCookieStatus = (accountStatus: string) => {
    const isActive = accountStatus === "active";
    return (
      <span className="inline-flex items-center gap-1.5">
        <span
          className={`h-2 w-2 rounded-full ${
            isActive ? "bg-success" : "bg-destructive"
          }`}
        />
        <span>{isActive ? "有效" : "过期"}</span>
      </span>
    );
  };

  return (
    <div data-testid="login-page" className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* LEFT: QR Code Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">扫码登录</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {!qrUrl ? (
            <div className="flex flex-col items-center justify-center p-8">
              <Skeleton
                className="h-48 w-48 rounded-lg"
                data-testid="skeleton"
              />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center p-4">
              <img
                src={qrUrl}
                alt="QR Code"
                className="mx-auto rounded-lg"
                data-testid="qr-image"
              />
            </div>
          )}
          <div className="flex items-center justify-center gap-2">
            {getStatusBadge()}
            {status === "expired" && (
              <Button variant="outline" size="sm" onClick={handleRefresh}>
                <RefreshCw className="h-4 w-4 mr-1" />
                刷新
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* RIGHT: Account List Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">已登录账号</CardTitle>
            <Badge variant="secondary">
              已登录 {loggedInCount}/{totalAccounts}
            </Badge>
          </div>
          <Progress value={progressValue} className="h-2 mt-2" />
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2" data-testid="account-list">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3">
                  <Skeleton
                    className="h-8 w-8 rounded-full"
                    data-testid="skeleton"
                  />
                  <Skeleton className="h-4 w-24" data-testid="skeleton" />
                  <Skeleton className="h-4 w-16" data-testid="skeleton" />
                </div>
              ))}
            </div>
          ) : (
            <div data-testid="account-list">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>头像</TableHead>
                    <TableHead>昵称</TableHead>
                    <TableHead>UID</TableHead>
                    <TableHead>Cookie状态</TableHead>
                    <TableHead>最后活跃</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {accounts.length === 0 ? (
                    <TableRow>
                      <TableCell
                        colSpan={6}
                        className="text-center text-muted-foreground"
                      >
                        暂无已登录账号
                      </TableCell>
                    </TableRow>
                  ) : (
                    accounts.map((account) => (
                      <TableRow
                        key={account.id}
                        data-testid="account-row"
                      >
                        <TableCell>
                          <Avatar className="h-8 w-8">
                            <AvatarImage
                              src={account.avatar_url || undefined}
                            />
                            <AvatarFallback>
                              {account.nickname?.charAt(0) || "?"}
                            </AvatarFallback>
                          </Avatar>
                        </TableCell>
                        <TableCell>{account.nickname}</TableCell>
                        <TableCell className="font-mono text-xs">
                          {account.weibo_uid}
                        </TableCell>
                        <TableCell>
                          {getCookieStatus(account.status)}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          N/A
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleLogout(account.id)}
                          >
                            <LogOut className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default LoginPage;
