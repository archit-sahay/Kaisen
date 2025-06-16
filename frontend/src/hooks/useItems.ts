// Items Hook for OSRS Price Tracker Frontend
// Implements cache-driven architecture:
// 1. Fetch from API on start
// 2. Listen to Socket.IO updates
// 3. Refetch when backend notifies about price changes

import { useState, useEffect, useCallback } from 'react';
import { Item, UseItemsReturn } from '../types/api';
import { apiService } from '../services/api';
import { useSocket } from './useSocket';

export const useItems = (): UseItemsReturn => {
  const [items, setItems] = useState<Item[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // Socket connection for live updates
  const { isConnected, lastUpdate } = useSocket();

  // Fetch items from API
  const fetchItems = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      console.log('🔄 Fetching items from API...');
      const response = await apiService.fetchItems();
      
      setItems(response.items);
      setLastUpdated(new Date());
      
      console.log(`✓ Loaded ${response.items.length} items from ${response.source}`);
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch items';
      console.error('✗ Failed to fetch items:', errorMessage);
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial fetch on component mount
  useEffect(() => {
    console.log('🚀 Initial items fetch on startup');
    fetchItems();
  }, [fetchItems]);

  // Listen for socket updates and refetch (cache-driven updates)
  useEffect(() => {
    if (lastUpdate) {
      console.log(`📈 Socket update received: ${lastUpdate.count} items changed`);
      console.log('🔄 Refetching items due to price updates...');
      
      // Refetch items when backend notifies about updates
      fetchItems();
    }
  }, [lastUpdate, fetchItems]);

  // Connection status logging
  useEffect(() => {
    if (isConnected) {
      console.log('🟢 Socket connected - live updates active');
    } else {
      console.log('🔴 Socket disconnected - no live updates');
    }
  }, [isConnected]);

  // Manual refetch function
  const refetch = useCallback(async () => {
    console.log('🔄 Manual refetch requested');
    await fetchItems();
  }, [fetchItems]);

  // Get items with prices only
  const getItemsWithPrices = useCallback(() => {
    return items.filter(item => 
      item.high_price !== null || item.low_price !== null
    );
  }, [items]);

  // Get expensive items (> 1M gp)
  const getExpensiveItems = useCallback(() => {
    return items.filter(item => {
      const price = item.high_price || item.low_price || 0;
      return price > 1000000;
    });
  }, [items]);

  // Search items by name
  const searchItems = useCallback((query: string) => {
    if (!query.trim()) {
      return items;
    }
    
    const lowerQuery = query.toLowerCase();
    return items.filter(item => 
      item.name.toLowerCase().includes(lowerQuery)
    );
  }, [items]);

  // Get statistics
  const getStats = useCallback(() => {
    const totalItems = items.length;
    const itemsWithPrices = getItemsWithPrices().length;
    const expensiveItems = getExpensiveItems().length;
    const membersItems = items.filter(item => item.members).length;
    
    return {
      totalItems,
      itemsWithPrices,
      expensiveItems,
      membersItems,
      freeToPlayItems: totalItems - membersItems
    };
  }, [items, getItemsWithPrices, getExpensiveItems]);

  return {
    items,
    isLoading,
    error,
    lastUpdated,
    refetch,
    // Additional utility functions
    getItemsWithPrices,
    getExpensiveItems,
    searchItems,
    getStats,
    // Connection status
    isSocketConnected: isConnected
  };
}; 