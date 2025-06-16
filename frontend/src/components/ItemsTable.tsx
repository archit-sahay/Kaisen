// Items Table Component for OSRS Price Tracker
// Displays items with live price updates

import React, { useState, useMemo } from 'react';
import { Item } from '../types/api';
import { apiService } from '../services/api';
import './ItemsTable.css';

interface ItemsTableProps {
  items: Item[];
  isLoading: boolean;
  lastUpdated: Date | null;
  isSocketConnected: boolean;
}

const ItemsTable: React.FC<ItemsTableProps> = ({ 
  items, 
  isLoading, 
  lastUpdated,
  isSocketConnected 
}) => {
  const [sortField, setSortField] = useState<keyof Item>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [filterText, setFilterText] = useState('');
  const [showMembersOnly, setShowMembersOnly] = useState(false);
  const [showPricedOnly, setShowPricedOnly] = useState(false);

  // Filter and sort items
  const filteredAndSortedItems = useMemo(() => {
    let filtered = items;

    // Apply text filter
    if (filterText.trim()) {
      const lowerFilter = filterText.toLowerCase();
      filtered = filtered.filter(item => 
        item.name.toLowerCase().includes(lowerFilter)
      );
    }

    // Apply members filter
    if (showMembersOnly) {
      filtered = filtered.filter(item => item.members);
    }

    // Apply priced items filter
    if (showPricedOnly) {
      filtered = filtered.filter(item => 
        item.high_price !== null || item.low_price !== null
      );
    }

    // Sort items
    const sorted = filtered.sort((a, b) => {
      const aValue = a[sortField];
      const bValue = b[sortField];

      if (aValue === null || aValue === undefined) return 1;
      if (bValue === null || bValue === undefined) return -1;

      let comparison = 0;
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        comparison = aValue.localeCompare(bValue);
      } else if (typeof aValue === 'number' && typeof bValue === 'number') {
        comparison = aValue - bValue;
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });

    return sorted;
  }, [items, filterText, showMembersOnly, showPricedOnly, sortField, sortDirection]);

  const handleSort = (field: keyof Item) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const getSortIcon = (field: keyof Item) => {
    if (sortField !== field) return '↕️';
    return sortDirection === 'asc' ? '↑' : '↓';
  };

  const getPriceChangeIndicator = (item: Item) => {
    const highPrice = item.high_price || 0;
    const lowPrice = item.low_price || 0;
    
    if (highPrice > lowPrice) return '📈';
    if (lowPrice > highPrice) return '📉';
    return '➖';
  };

  if (isLoading && items.length === 0) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading OSRS items...</p>
      </div>
    );
  }

  return (
    <div className="items-table-container">
      {/* Header with status and controls */}
      <div className="table-header">
        <div className="status-info">
          <div className="connection-status">
            <span className={`status-indicator ${isSocketConnected ? 'connected' : 'disconnected'}`}>
              {isSocketConnected ? '🟢 Live Updates' : '🔴 Offline'}
            </span>
            {lastUpdated && (
              <span className="last-updated">
                Last updated: {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>
          <div className="items-count">
            Showing {filteredAndSortedItems.length} of {items.length} items
          </div>
        </div>

        {/* Filters */}
        <div className="filters">
          <input
            type="text"
            placeholder="Search items..."
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            className="search-input"
          />
          <label className="filter-checkbox">
            <input
              type="checkbox"
              checked={showMembersOnly}
              onChange={(e) => setShowMembersOnly(e.target.checked)}
            />
            Members only
          </label>
          <label className="filter-checkbox">
            <input
              type="checkbox"
              checked={showPricedOnly}
              onChange={(e) => setShowPricedOnly(e.target.checked)}
            />
            With prices only
          </label>
        </div>
      </div>

      {/* Table */}
      <div className="table-wrapper">
        <table className="items-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('name')} className="sortable">
                Item Name {getSortIcon('name')}
              </th>
              <th onClick={() => handleSort('high_price')} className="sortable">
                High Price {getSortIcon('high_price')}
              </th>
              <th onClick={() => handleSort('low_price')} className="sortable">
                Low Price {getSortIcon('low_price')}
              </th>
              <th>Trend</th>
              <th onClick={() => handleSort('members')} className="sortable">
                Members {getSortIcon('members')}
              </th>
              <th onClick={() => handleSort('highalch')} className="sortable">
                High Alch {getSortIcon('highalch')}
              </th>
              <th>Last Updated</th>
            </tr>
          </thead>
          <tbody>
            {filteredAndSortedItems.map((item) => (
              <tr key={item.id} className={`item-row ${item.members ? 'members-item' : 'f2p-item'}`}>
                <td className="item-name">
                  <div className="item-info">
                    <strong>{item.name}</strong>
                    {item.examine && (
                      <div className="item-examine" title={item.examine}>
                        {item.examine.substring(0, 50)}
                        {item.examine.length > 50 ? '...' : ''}
                      </div>
                    )}
                  </div>
                </td>
                <td className="price-cell">
                  {item.high_price ? (
                    <span className="price high-price">
                      {apiService.formatPrice(item.high_price)} gp
                    </span>
                  ) : (
                    <span className="no-price">N/A</span>
                  )}
                </td>
                <td className="price-cell">
                  {item.low_price ? (
                    <span className="price low-price">
                      {apiService.formatPrice(item.low_price)} gp
                    </span>
                  ) : (
                    <span className="no-price">N/A</span>
                  )}
                </td>
                <td className="trend-cell">
                  {getPriceChangeIndicator(item)}
                </td>
                <td className="members-cell">
                  {item.members ? '👑' : '🆓'}
                </td>
                <td className="alch-cell">
                  {item.highalch ? `${item.highalch.toLocaleString()} gp` : 'N/A'}
                </td>
                <td className="timestamp-cell">
                  {item.high_time ? 
                    apiService.formatTimestamp(item.high_time) : 
                    'N/A'
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {filteredAndSortedItems.length === 0 && !isLoading && (
        <div className="no-results">
          <p>No items found matching your criteria.</p>
        </div>
      )}

      {isLoading && (
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <p>Updating prices...</p>
        </div>
      )}
    </div>
  );
};

export default ItemsTable; 