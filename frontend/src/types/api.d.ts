export interface GaugingData {
  site_id: string;
  timeseries: Array<{
    timestamp: string;
    waterLevel: number | null;
    flowRate: number | null;
  }>;
  total_records: number;
}

export interface Api {
  fetchTilesList(isSteedMode?: boolean, simulation?: string): Promise<string[]>;
  fetchGaugingData(startDate: string, endDate: string): Promise<GaugingData>;
  fetchHistoricalSimulations(): Promise<string[]>;
  runInference(): Promise<void>;
}
