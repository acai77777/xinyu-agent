/**
 * 复现 app 端切换 session 时显示其他 session 气泡的 bug。
 *
 * 不依赖 zustand / React，重写一份最小化状态机模拟当前 chatStore 行为。
 * 跑两种实现做对照：
 *   - BUGGY = 当前 app/stores/chatStore.ts 的行为
 *   - FIXED = P1 + P2 修复后的行为
 *
 * 期望输出：
 *   修复前：CASE1 [FAIL], CASE2 [FAIL]   ← bug 复现
 *   修复后：CASE1 [PASS], CASE2 [PASS]   ← 修复生效
 *
 * 注意：脚本里的状态机是真实 store 的重写复刻，不会自动跟代码同步。
 * 它的价值是"演示因果链"而不是"防止回归"。
 */

const WELCOME = {
  id: 'welcome',
  role: 'assistant',
  content: 'WELCOME',
  isStreaming: false,
};

/** 当前 chatStore.ts 的行为（含 bug） */
function makeStoreBuggy() {
  let state = { currentSessionId: null, messagesBySession: {} };
  return {
    name: 'BUGGY',
    getState: () => state,
    setSession: (sid) => {
      if (!state.messagesBySession[sid]) {
        state = {
          currentSessionId: sid,
          messagesBySession: { ...state.messagesBySession, [sid]: [WELCOME] },
        };
      } else {
        state = { ...state, currentSessionId: sid };
      }
    },
    // 修复前没有这个 action
    clearCurrent: null,
    useMessages: () => {
      if (!state.currentSessionId) return [WELCOME];
      return state.messagesBySession[state.currentSessionId] ?? [WELCOME];
    },
    appendStreaming: (sid, content) => {
      const cur = state.messagesBySession[sid] ?? [];
      state = {
        ...state,
        messagesBySession: {
          ...state.messagesBySession,
          [sid]: [
            ...cur,
            { id: 'stream-x', role: 'assistant', content, isStreaming: true },
          ],
        },
      };
    },
    seed: (sid, msgs) => {
      state = {
        currentSessionId: sid,
        messagesBySession: { ...state.messagesBySession, [sid]: msgs },
      };
    },
  };
}

/** P1 + P2 修复后的 chatStore 行为 */
function makeStoreFixed() {
  let state = { currentSessionId: null, messagesBySession: {} };
  return {
    name: 'FIXED',
    getState: () => state,
    // P1: 新 action，把 currentSessionId 切到 null
    clearCurrent: () => {
      state = { ...state, currentSessionId: null };
    },
    setSession: (sid) => {
      // P2: 切入前清掉目标 session 末尾的 isStreaming 残留
      const existing = state.messagesBySession[sid];
      let cleaned = existing;
      if (existing && existing.length > 0) {
        const last = existing[existing.length - 1];
        if (last && last.role === 'assistant' && last.isStreaming) {
          cleaned = existing.slice(0, -1);
        }
      }
      if (!cleaned) {
        state = {
          currentSessionId: sid,
          messagesBySession: { ...state.messagesBySession, [sid]: [WELCOME] },
        };
      } else {
        state = {
          currentSessionId: sid,
          messagesBySession:
            cleaned === existing
              ? state.messagesBySession
              : { ...state.messagesBySession, [sid]: cleaned },
        };
      }
    },
    useMessages: () => {
      if (!state.currentSessionId) return [WELCOME];
      return state.messagesBySession[state.currentSessionId] ?? [WELCOME];
    },
    appendStreaming: (sid, content) => {
      const cur = state.messagesBySession[sid] ?? [];
      state = {
        ...state,
        messagesBySession: {
          ...state.messagesBySession,
          [sid]: [
            ...cur,
            { id: 'stream-x', role: 'assistant', content, isStreaming: true },
          ],
        },
      };
    },
    seed: (sid, msgs) => {
      state = {
        currentSessionId: sid,
        messagesBySession: { ...state.messagesBySession, [sid]: msgs },
      };
    },
  };
}

/** CASE 1: 新建对话时 fetch 期间不应显示上一个 session 的气泡 */
function runCase1(store) {
  // 步骤 1: 用户在 session_A 聊过几句
  store.seed('A', [
    WELCOME,
    { id: 'u1', role: 'user', content: '我心情不好', isStreaming: false },
    { id: 'a1', role: 'assistant', content: '怎么了？', isStreaming: false },
  ]);

  // 步骤 2: 用户按返回 → 点"新建对话" → 进 /chat/new
  // FIXED 实现里 [id].tsx 会立即调用 clearCurrent()
  // BUGGY 实现里 [id].tsx 没有这一步，currentSessionId 还指着 'A'
  if (store.clearCurrent) {
    store.clearCurrent();
  }

  // 步骤 3: fetch POST 还没回，UI 这一帧渲染 messages
  const messagesShownDuringFetch = store.useMessages();
  const contents = messagesShownDuringFetch.map((m) => m.content);
  const leaked = messagesShownDuringFetch.some(
    (m) => m.content === '我心情不好',
  );

  console.log(`  [${store.name}] CASE1 fetch 期间显示:`, contents);
  return { ok: !leaked, detail: leaked ? '泄露了 session_A 的气泡' : 'OK' };
}

/** CASE 2: 离开 session_B 时残留的流式消息，再回来不应再出现 */
function runCase2(store) {
  // 步骤 1: 进 session_B
  store.setSession('B');
  // 步骤 2: AI 流式回复中，挂了一条 isStreaming: true 的消息
  store.appendStreaming('B', '我正在思考...');
  // 步骤 3: 用户半路按返回（没等 finalize）→ 切到 C → 再切回 B
  store.setSession('C');
  store.setSession('B');

  // 步骤 4: 看 messages 末尾是否还挂着流式残留
  const final = store.useMessages();
  const hasResidual = final.some((m) => m.isStreaming);

  console.log(
    `  [${store.name}] CASE2 再回 session_B:`,
    final.map((m) => `${m.content}${m.isStreaming ? '(streaming)' : ''}`),
  );
  return {
    ok: !hasResidual,
    detail: hasResidual ? 'session_B 末尾还挂着流式残留' : 'OK',
  };
}

console.log('=== 修复前（当前 chatStore 行为） ===');
const buggy1 = runCase1(makeStoreBuggy());
const buggy2 = runCase2(makeStoreBuggy());
console.log(`  CASE1: ${buggy1.ok ? '[PASS]' : '[FAIL]'} ${buggy1.detail} (期望 [FAIL])`);
console.log(`  CASE2: ${buggy2.ok ? '[PASS]' : '[FAIL]'} ${buggy2.detail} (期望 [FAIL])`);

console.log('\n=== 修复后（P1 + P2） ===');
const fixed1 = runCase1(makeStoreFixed());
const fixed2 = runCase2(makeStoreFixed());
console.log(`  CASE1: ${fixed1.ok ? '[PASS]' : '[FAIL]'} ${fixed1.detail} (期望 [PASS])`);
console.log(`  CASE2: ${fixed2.ok ? '[PASS]' : '[FAIL]'} ${fixed2.detail} (期望 [PASS])`);

const allOk = !buggy1.ok && !buggy2.ok && fixed1.ok && fixed2.ok;
console.log(`\n=== 总结: ${allOk ? '[OK] bug 复现 + 修复生效' : '[BAD] 不符合预期'} ===`);
process.exit(allOk ? 0 : 1);
