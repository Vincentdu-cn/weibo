export interface AlertDTO {
  id: number;
  account_uid?: string | null;
  comment_id?: number | null;
  alert_type: string;
  message: string;
  status: string;
  comment_input?: string | null;
  selected_account_ids?: number[];
}
