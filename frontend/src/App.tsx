import React from 'react';
import { useItems } from './hooks/useItems';
import ItemsTable from './components/ItemsTable';
import './App.css';

const App: React.FC = () => {
  const { 
    items, 
    isLoading, 
    error, 
    lastUpdated, 
    refetch,
    getStats,
    isSocketConnected 
  } = useItems();

  const stats = getStats();

  const handleRefresh = () => {
    console.log('Manual refresh triggered');
    refetch();
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="title-section">
            <h1>OSRS Price Tracker</h1>
            <p className="subtitle">Live RuneScape item prices</p>
          </div>
          
          <div className="header-actions">
            <button 
              onClick={handleRefresh} 
              className="refresh-button"
              disabled={isLoading}
            >
              {isLoading ? 'Updating...' : 'Refresh'}
            </button>
          </div>
        </div>

        <div className="stats-bar">
          <div className="stats-grid">
            <div className="stat-item">
              <span className="stat-value">{stats.totalItems.toLocaleString()}</span>
              <span className="stat-label">Total Items</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.itemsWithPrices.toLocaleString()}</span>
              <span className="stat-label">With Prices</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.expensiveItems.toLocaleString()}</span>
              <span className="stat-label">Expensive (1M+)</span>
            </div>
          </div>
        </div>
      </header>

      <main className="app-main">
        {error && (
          <div className="error-banner">
            <div className="error-content">
              <span className="error-icon">Error:</span>
              <div className="error-text">
                <strong>Error:</strong> {error}
              </div>
              <button onClick={handleRefresh} className="error-retry">
                Try Again
              </button>
            </div>
          </div>
        )}

        <ItemsTable 
          items={items}
          isLoading={isLoading}
          lastUpdated={lastUpdated}
          isSocketConnected={isSocketConnected}
        />
      </main>

      <footer className="app-footer">
        <div className="footer-content">
          <p>
            Data provided by the Old School RuneScape Wiki API
          </p>
        </div>
      </footer>
    </div>
  );
};

export default App; 