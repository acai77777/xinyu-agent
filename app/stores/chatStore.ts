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
  addMessage: (message: Message) => void;
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
    // 如果该 session 没有消息，初始化为欢迎消息
    if (!state.messagesBySession[sessionId]) {
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
      set({ currentSessionId: sessionId, isThinking: false, crisisHolding: false });
    }
  },

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
