// Must match COMMON_FIELDS in panopticon/config/types.py
export type HoneypotEvent = {
  id: string;
  event_type: string;
  session_id: string;
  src_ip: string;
  src_port: number;
  timestamp: string;
  success?: boolean;
  input?: string;
  raw_command?: string;
};
