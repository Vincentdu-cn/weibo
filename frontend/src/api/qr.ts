import { apiGet, apiDelete } from "./client";
import { AccountDTO } from "@/types/account";

interface QrGenerateResponse {
  qr_url: string;
  session_id: string;
}

interface QrStatusResponse {
  status: string;
  account?: AccountDTO;
}

export async function generateQr(): Promise<QrGenerateResponse> {
  return apiGet<QrGenerateResponse>("/qr/generate");
}

export async function getQrStatus(sessionId: string): Promise<QrStatusResponse> {
  return apiGet<QrStatusResponse>(`/qr/status/${sessionId}`);
}

export async function getAccounts(): Promise<AccountDTO[]> {
  return apiGet<AccountDTO[]>("/accounts");
}

export async function logoutAccount(id: number): Promise<void> {
  await apiDelete<void>(`/accounts/${id}`);
}
