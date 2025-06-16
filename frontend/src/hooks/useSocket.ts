// Socket.IO Hook for OSRS Price Tracker Frontend
// Implements real-time architecture: Connect to WebSocket and listen for price updates

import { useEffect, useState, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { UseSocketReturn, SocketMessage, ConnectionStatus } from '../types/api';

const SOCKET_URL = 'http://localhost:8000';

export const useSocket = (): UseSocketReturn => {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    connected: false
  });
  const [lastUpdate, setLastUpdate] = useState<SocketMessage | null>(null);

  // Initialize socket connection
  useEffect(() => {
    console.log('Initializing Socket.IO connection...');
    
    const newSocket = io(SOCKET_URL, {
      autoConnect: true,
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5,
      timeout: 20000,
    });

    // Connection event handlers
    newSocket.on('connect', () => {
      console.log('✓ Connected to Socket.IO server');
      setIsConnected(true);
      setConnectionStatus({
        connected: true,
        message: 'Connected to live updates',
        timestamp: new Date().toISOString()
      });
    });

    newSocket.on('disconnect', (reason) => {
      console.log('✗ Disconnected from Socket.IO server:', reason);
      setIsConnected(false);
      setConnectionStatus({
        connected: false,
        message: `Disconnected: ${reason}`,
        timestamp: new Date().toISOString()
      });
    });

    newSocket.on('connect_error', (error) => {
      console.error('Socket.IO connection error:', error);
      setConnectionStatus({
        connected: false,
        message: `Connection error: ${error.message}`,
        timestamp: new Date().toISOString()
      });
    });

    // Server confirmation
    newSocket.on('connected', (data) => {
      console.log('Server confirmation:', data);
      setConnectionStatus({
        connected: true,
        message: data.message,
        timestamp: data.timestamp
      });
    });

    // Price update events (main feature)
    newSocket.on('price_update', (message: SocketMessage) => {
      console.log(`📈 Price update received: ${message.count} items updated`);
      setLastUpdate(message);
    });

    // Pong response for ping
    newSocket.on('pong', (data) => {
      console.log('Pong received:', data.timestamp);
    });

    setSocket(newSocket);

    // Cleanup on unmount
    return () => {
      console.log('Cleaning up Socket.IO connection');
      newSocket.close();
    };
  }, []);

  // Ping function for connection testing
  const sendPing = useCallback(() => {
    if (socket?.connected) {
      console.log('Sending ping to server');
      socket.emit('ping');
    }
  }, [socket]);

  // Connection status summary
  const getConnectionStatusText = (): string => {
    if (isConnected) {
      return '🟢 Live Updates Active';
    } else {
      return '🔴 Disconnected';
    }
  };

  return {
    isConnected,
    connectionStatus,
    lastUpdate,
    sendPing,
    getConnectionStatusText
  };
}; 