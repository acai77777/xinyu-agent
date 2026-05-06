import { useEffect, useRef, useState, useCallback } from 'react';
import { AppState } from 'react-native';

const API_BASE_URL = 'https://xinyu.acai777.cn';
const WS_URL = API_BASE_URL.replace('https', 'wss');

interface WsMessage {
  type: string;
  content?: string;
  [key: string]: any;
}

export function useWebSocket(sessionId: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const connect = useCallback(() => {
    // 无效 sessionId 时不连接
    if (!sessionId || sessionId === 'pending' || sessionId === 'undefined' || sessionId === 'new') {
      return;
    }
    try {
      const ws = new WebSocket(`${WS_URL}/ws/${sessionId}`);

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setLastMessage(data);
      };

      ws.onclose = () => {
        setIsConnected(false);
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    } catch {
      // WebSocket not available (e.g. no backend running)
    }
  }, [sessionId]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active' && !isConnected) connect();
      if (state === 'background') wsRef.current?.close();
    });
    return () => sub.remove();
  }, [isConnected, connect]);

  const send = useCallback((data: WsMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { send, lastMessage, isConnected };
}
