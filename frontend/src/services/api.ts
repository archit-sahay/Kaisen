// API Service for OSRS Price Tracker Frontend

import { ItemsResponse, Item, HealthResponse } from '../types/api';

// API base URL - will be configured via Docker environment
const API_BASE_URL = 'http://localhost:8000';

class ApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  async fetchItems(): Promise<ItemsResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/api/items`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data: ItemsResponse = await response.json();
      return data;
    } catch (error) {
      console.error('Failed to fetch items:', error);
      throw error;
    }
  }

  async fetchItem(itemId: number): Promise<Item> {
    try {
      const response = await fetch(`${this.baseUrl}/api/items/${itemId}`);
      
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Item not found');
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data: Item = await response.json();
      return data;
    } catch (error) {
      console.error(`Failed to fetch item ${itemId}:`, error);
      throw error;
    }
  }

  async checkHealth(): Promise<HealthResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/api/health`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data: HealthResponse = await response.json();
      return data;
    } catch (error) {
      console.error('Failed to check health:', error);
      throw error;
    }
  }

  // Utility method to format prices
  formatPrice(price: number | null | undefined): string {
    if (price === null || price === undefined) {
      return 'N/A';
    }
    return price.toLocaleString();
  }

  // Utility method to format timestamps
  formatTimestamp(timestamp: number | null | undefined): string {
    if (!timestamp) {
      return 'N/A';
    }
    return new Date(timestamp * 1000).toLocaleString();
  }

  // Utility method to determine if an item is expensive
  isExpensiveItem(item: Item): boolean {
    const price = item.high_price || item.low_price || 0;
    return price > 1000000; // 1M+ gold pieces
  }

  // Utility method to get price change indicator
  getPriceChangeIndicator(item: Item): 'up' | 'down' | 'neutral' {
    const highPrice = item.high_price || 0;
    const lowPrice = item.low_price || 0;
    
    if (highPrice > lowPrice) {
      return 'up';
    } else if (lowPrice > highPrice) {
      return 'down';
    }
    return 'neutral';
  }
}

// Export singleton instance
export const apiService = new ApiService();
export default apiService; 