export type HoneypotEvent = {
  // Must match COMMON_FIELDS in backend/config/constants.py
  id: string;
  event_type: string;
  session_id: string;
  src_ip: string;
  src_port: number;
  timestamp: string;

  // All other event data types
  input?: string; // Command
  tool?: string; // FileDownloaded
  url?: string | null; // FileDownloaded
  destination?: string | null; // FileDownloaded
};
