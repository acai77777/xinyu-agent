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

// 尾巴补完动画的总时长 / 帧数。短回复 ~400ms 平滑追上；长回复同样 ~400ms 内
// 完成（按尾巴长度自适应每帧字数），避免动画时间过长。
const TAIL_ANIM_TOTAL_MS = 400;
const TAIL_ANIM_FRAMES = 20;
const TAIL_ANIM_INTERVAL_MS = TAIL_ANIM_TOTAL_MS / TAIL_ANIM_FRAMES;

export const useChatStore = create<ChatState>((set, get) => {
  // 尾巴补完动画的私有状态（不暴露给 React，避免触发额外 re-render）。
  // 任何"切走当前 session / 清空当前 / 收到新 finalize"都会调 cancelTailAnimation：
  // 若动画正在跑，就 jump-to-end 写入完整 final_text，避免半成品停在中间或被 P2 清理掉。
  let tailAnimationTimer: ReturnType<typeof setTimeout> | null = null;
  let pendingFinalize: {
    sid: string;
    finalContent: string;
    emotion: string | undefined;
  } | null = null;

  const cancelTailAnimation = () => {
    if (tailAnimationTimer) {
      clearTimeout(tailAnimationTimer);
      tailAnimationTimer = null;
    }
    const pending = pendingFinalize;
    pendingFinalize = null;
    if (!pending) return;
    // jump-to-end：把当前流式消息一次性补到 final_text
    const { sid, finalContent, emotion } = pending;
    set((state) => {
      const current = state.messagesBySession[sid] ?? [];
      const last = current[current.length - 1];
      if (!last || last.role !== 'assistant' || !last.isStreaming) return state;
      return {
        messagesBySession: {
          ...state.messagesBySession,
          [sid]: [
            ...current.slice(0, -1),
            { ...last, content: finalContent, emotion: emotion ?? last.emotion, isStreaming: false },
          ],
        },
      };
    });
  };

  return {
    messagesBySession: {},
    currentSessionId: null,
    isThinking: false,
    crisisHolding: false,

    setSession: (sessionId) => {
      cancelTailAnimation();
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
    clearCurrent: () => {
      cancelTailAnimation();
      set({ currentSessionId: null, isThinking: false, crisisHolding: false });
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

    // 拿到 text_done / text_patch 的 final_text 后：
    // - case A：final 以 accumulated 为前缀且更长 → 启动尾巴动画分帧 append，避免一次性蹦出
    // - case B：审核改写 / final 比 accumulated 短 → 整段替换（仍是瞬时，但语义上必须整段)
    finalizeStreamingMessage: (finalContent, emotion) => {
      cancelTailAnimation();
      const state = get();
      const sid = state.currentSessionId;
      if (!sid) return;
      const current = state.messagesBySession[sid] ?? [];
      const last = current[current.length - 1];
      if (!last || last.role !== 'assistant' || !last.isStreaming) return;

      // 旧协议兜底：text_done 没带 content（finalContent === null）→ 保留累积直接 finalize
      if (finalContent === null) {
        set({
          messagesBySession: {
            ...state.messagesBySession,
            [sid]: [
              ...current.slice(0, -1),
              { ...last, emotion: emotion ?? last.emotion, isStreaming: false },
            ],
          },
        });
        return;
      }

      const accumulated = last.content;

      // case A：尾巴动画
      if (finalContent.startsWith(accumulated) && finalContent.length > accumulated.length) {
        const tailLen = finalContent.length - accumulated.length;
        const charsPerTick = Math.max(1, Math.ceil(tailLen / TAIL_ANIM_FRAMES));
        pendingFinalize = { sid, finalContent, emotion };

        const tick = () => {
          // 每帧都重新 get()——动画期间若 appendDelta 又 push 了 chunk（理论不该发生），
          // 也能基于当前 content.length 继续推进，不会回退。
          const st = get();
          const cur = st.messagesBySession[sid] ?? [];
          const l = cur[cur.length - 1];
          if (!l || l.role !== 'assistant' || !l.isStreaming) {
            // 末尾消息被外部改了 / 清掉了 —— 放弃动画
            tailAnimationTimer = null;
            pendingFinalize = null;
            return;
          }
          const remaining = finalContent.length - l.content.length;
          if (remaining <= 0) {
            set({
              messagesBySession: {
                ...st.messagesBySession,
                [sid]: [
                  ...cur.slice(0, -1),
                  { ...l, content: finalContent, emotion: emotion ?? l.emotion, isStreaming: false },
                ],
              },
            });
            tailAnimationTimer = null;
            pendingFinalize = null;
            return;
          }
          const step = Math.min(charsPerTick, remaining);
          const nextContent = finalContent.slice(0, l.content.length + step);
          set({
            messagesBySession: {
              ...st.messagesBySession,
              [sid]: [...cur.slice(0, -1), { ...l, content: nextContent }],
            },
          });
          tailAnimationTimer = setTimeout(tick, TAIL_ANIM_INTERVAL_MS);
        };
        tailAnimationTimer = setTimeout(tick, TAIL_ANIM_INTERVAL_MS);
        return;
      }

      // case B：审核改写 / final 比 accumulated 短 → 整段替换
      set({
        messagesBySession: {
          ...state.messagesBySession,
          [sid]: [
            ...current.slice(0, -1),
            { ...last, content: finalContent, emotion: emotion ?? last.emotion, isStreaming: false },
          ],
        },
      });
    },

    setThinking: (thinking) => set({ isThinking: thinking }),
    setCrisisHolding: (active) => set({ crisisHolding: active }),

    resetMessages: () => {
      cancelTailAnimation();
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
      });
    },

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
  };
});

/** 从 store 中派生当前会话的消息列表 */
export function useMessages(): Message[] {
  return useChatStore((state) => {
    const { currentSessionId, messagesBySession } = state;
    if (!currentSessionId) return [WELCOME_MESSAGE];
    return messagesBySession[currentSessionId] ?? [WELCOME_MESSAGE];
  });
}
