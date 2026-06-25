export interface WSMessage {
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}
