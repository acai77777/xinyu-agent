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

  // 关键：闭包绑死旧 sessionId 的 connect，必须清 handler 再 close，
  // 否则 close 触发 onclose → setTimeout(connect_OLD, 3000) → 3 秒后
  // 重连回旧 sid 覆盖 wsRef.current，新会话消息会跑到旧 session 上。
  const closeSilently = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close();
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      closeSilently();
    };
  }, [connect, closeSilently]);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active' && !isConnected) connect();
      // background 也走 closeSilently：语义是用户回前台再手动 connect，
      // 不希望 close 后 3 秒自动重连跟手动逻辑打架。
      if (state === 'background') closeSilently();
    });
    return () => sub.remove();
  }, [isConnected, connect, closeSilently]);

  const send = useCallback((data: WsMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { send, lastMessage, isConnected };
}
