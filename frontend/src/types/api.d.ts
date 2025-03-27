export interface GaugingData {
  site_id: string;
  timeseries: Array<{
    timestamp: string;
    waterLevel: number | null;
    flowRate: number | null;
  }>;
  total_records: number;
}
