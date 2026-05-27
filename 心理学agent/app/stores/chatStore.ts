import { create } from 'zustand';
import { Message } from '../types';
import { API_BASE_URL, getToken } from '../services/api';

interface ChatState {
  /** 按 sessionId 存储消息 */
  messagesBySession: Record<string, Message[]>;
  currentSessionId: string | null;
  isThinking: boolean;
  crisisHolding: boolean;

  setSession: (sessionId: string) => void;
  clearCurrent: () => void;
  addMessage: (message: Message) => void;
  appendDeltaToLastAssistant: (delta: string) => void;
  finalizeStreamingMessage: (finalContent: string | null, emotion?: string) => void;
  setThinking: (thinking: boolean) => void;
  setCrisisHolding: (active: boolean) => void;
  resetMessages: () => void;
  loadSessionMessages: (sessionId: string) => Promise<void>;
}

const WELCOME_MESSAGE: Message = {
  id: 'welcome',
  role: 'assistant',
  type: 'text',
  content: '你好呀 👋 我是你的心理支持助手，可以陪你聊聊心情、帮你分析情绪背后的想法、提供专业的心理学知识（积极心理学、认知行为疗法等），还能做简单的心理评估和放松练习。今天过得怎么样？',
  timestamp: new Date(),
};

export const useChatStore = create<ChatState>((set, get) => ({
  messagesBySession: {},
  currentSessionId: null,
  isThinking: false,
  crisisHolding: false,

  setSession: (sessionId) => {
    const state = get();
    const existing = state.messagesBySession[sessionId];

    // P2: 切入前清掉目标 session 末尾的 isStreaming 残留——
    // 用户上次离开时流字没 finalize，半成品挂在末尾，再进来不应再出现。
    let cleaned: Message[] | undefined = existing;
    if (existing && existing.length > 0) {
      const last = existing[existing.length - 1];
      if (last && last.role === 'assistant' && last.isStreaming) {
        cleaned = existing.slice(0, -1);
      }
    }

    if (!cleaned) {
      set({
        currentSessionId: sessionId,
        messagesBySession: {
          ...state.messagesBySession,
          [sessionId]: [WELCOME_MESSAGE],
        },
        isThinking: false,
        crisisHolding: false,
      });
    } else {
      set({
        currentSessionId: sessionId,
        messagesBySession:
          cleaned === existing
            ? state.messagesBySession
            : { ...state.messagesBySession, [sessionId]: cleaned },
        isThinking: false,
        crisisHolding: false,
      });
    }
  },

  // P1: 把 currentSessionId 切到 null，让 useMessages 返回 WELCOME，
  // 用于 /chat/new 走 POST 期间避免显示上一个 session 的气泡。
  clearCurrent: () => set({ currentSessionId: null, isThinking: false, crisisHolding: false }),

  addMessage: (message) =>
    set((state) => {
      const sid = state.currentSessionId;
      if (!sid) return state;
      const current = state.messagesBySession[sid] ?? [];
      return {
        messagesBySession: {
          ...state.messagesBySession,
          [sid]: [...current, message],
        },
      };
    }),

  appendDeltaToLastAssistant: (delta) =>
    set((state) => {
      const sid = state.currentSessionId;
      if (!sid) return state;
      const current = state.messagesBySession[sid] ?? [];
      const last = current[current.length - 1];
      if (last && last.role === 'assistant' && last.isStreaming) {
        const updated: Message = { ...last, content: last.content + delta };
        return {
          messagesBySession: {
            ...state.messagesBySession,
            [sid]: [...current.slice(0, -1), updated],
          },
        };
      }
      const newMsg: Message = {
        id: `stream-${Date.now()}`,
        role: 'assistant',
        type: 'text',
        content: delta,
        isStreaming: true,
        timestamp: new Date(),
      };
      return {
        messagesBySession: {
          ...state.messagesBySession,
          [sid]: [...current, newMsg],
        },
      };
    }),

  finalizeStreamingMessage: (finalContent, emotion) =>
    set((state) => {
      const sid = state.currentSessionId;
      if (!sid) return state;
      const current = state.messagesBySession[sid] ?? [];
      const last = current[current.length - 1];
      if (!last || last.role !== 'assistant' || !last.isStreaming) return state;
      const updated: Message = {
        ...last,
        content: finalContent !== null ? finalContent : last.content,
        emotion: emotion ?? last.emotion,
        isStreaming: false,
      };
      return {
        messagesBySession: {
          ...state.messagesBySession,
          [sid]: [...current.slice(0, -1), updated],
        },
      };
    }),

  setThinking: (thinking) => set({ isThinking: thinking }),
  setCrisisHolding: (active) => set({ crisisHolding: active }),

  resetMessages: () =>
    set((state) => {
      const sid = state.currentSessionId;
      if (!sid) return state;
      return {
        messagesBySession: {
          ...state.messagesBySession,
          [sid]: [WELCOME_MESSAGE],
        },
        isThinking: false,
        crisisHolding: false,
      };
    }),

  loadSessionMessages: async (sessionId: string) => {
    try {
      const token = getToken();
      const res = await fetch(`${API_BASE_URL}/api/history/sessions/${sessionId}`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
      if (!res.ok) return;
      const data = await res.json();

      if (data.messages && data.messages.length > 0) {
        const msgs: Message[] = data.messages.map((m: any, i: number) => ({
          id: `loaded-${i}`,
          role: m.role,
          type: m.type || 'text',
          content: m.content,
          timestamp: new Date(m.created_at),
        }));
        set((state) => ({
          messagesBySession: {
            ...state.messagesBySession,
            [sessionId]: msgs,
          },
        }));
      }
    } catch {
      // 加载失败则保留欢迎消息
    }
  },
}))

/** 从 store 中派生当前会话的消息列表 */
export function useMessages(): Message[] {
  return useChatStore((state) => {
    const { currentSessionId, messagesBySession } = state;
    if (!currentSessionId) return [WELCOME_MESSAGE];
    return messagesBySession[currentSessionId] ?? [WELCOME_MESSAGE];
  });
}
