// API Response Types for OSRS Price Tracker Frontend

export interface Item {
  id: number;
  name: string;
  examine?: string;
  members: boolean;
  lowalch?: number;
  highalch?: number;
  limit_value?: number;
  value?: number;
  icon?: string;
  high_price?: number;
  low_price?: number;
  high_time?: number;
  low_time?: number;
  price_last_updated?: string;
}

export interface ItemsResponse {
  items: Item[];
  count: number;
  timestamp: string;
  source: string;
}

export interface SocketMessage {
  type: string;
  updated_items: string[];
  count: number;
  timestamp: string;
}

export interface ConnectionStatus {
  connected: boolean;
  message?: string;
  timestamp?: string;
}

export interface HealthResponse {
  status: string;
  database: string;
  redis: string;
  connected_clients: number;
  timestamp: string;
}

// Hook return types
export interface UseItemsReturn {
  items: Item[];
  isLoading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  refetch: () => Promise<void>;
  getItemsWithPrices: () => Item[];
  getExpensiveItems: () => Item[];
  searchItems: (query: string) => Item[];
  getStats: () => {
    totalItems: number;
    itemsWithPrices: number;
    expensiveItems: number;
    membersItems: number;
    freeToPlayItems: number;
  };
  isSocketConnected: boolean;
}

export interface UseSocketReturn {
  isConnected: boolean;
  connectionStatus: ConnectionStatus;
  lastUpdate: SocketMessage | null;
  sendPing: () => void;
  getConnectionStatusText: () => string;
} 