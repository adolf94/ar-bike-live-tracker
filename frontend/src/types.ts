export interface LocationData {
  lat: number;
  lng: number;
  course: number;
  position_time?: string;
}

export interface StatusData {
  speed: number;
  isIgnitionOn: boolean;
  batteryLevel: number;
  isOnline: boolean;
}

export interface TelemetryDocument {
  id: string;
  deviceId: string;
  status_updated_at: string;
  last_checked_at?: string;
  location: LocationData;
  status: StatusData;
  eventTriggered: string | null;
  ttl: number;
}
