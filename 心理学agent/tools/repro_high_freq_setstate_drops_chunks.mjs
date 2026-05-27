/**
 * 复现"useState 当消息总线，高频 chunk 被吞"的 bug。
 *
 * 背景：useWebSocket 用 useState<WsMessage> 暂存最新一条 ws 消息，组件
 * 通过 useEffect([lastMessage]) 消费。React 18 在 native event handler 里
 * 仍然 batch setState 调用——更准确地说，React 是"保留最新值 + 调度一次
 * 渲染"。如果 ws.onmessage 触发频率 > React commit 频率，多个 setState
 * 的中间值会被覆盖，useEffect 永远不会看见。
 *
 * 两份实现做对照：
 *   - BUGGY = useState 中转模式
 *     · setLastMessage(A)，没等 commit 又 setLastMessage(B) → 消费方只看到 B
 *   - FIXED = 直接回调模式
 *     · ws.onmessage 直接 onMessage(data)，不走 React state
 *
 * 注意：脚本不依赖真实 React，是 React 18 调度模型的最小化复刻。
 * 它的价值是"演示因果链 + 验证方案"，不是"防止回归"。
 */

/* ───────────── React 18 调度模型最小复刻 ───────────── */

/**
 * 模拟 React 18 的 setState + commit 行为。
 * 核心规则：
 * - setState(v) 只保存最新值，不入队列
 * - 多次同步 setState 调用 → 只 schedule 一次 commit（其值是最新那次）
 * - commit 触发 useEffect 看到新值
 *
 * 真实 React 在 macrotask 之间会 commit，但在一个 microtask
 * batch 里多次 setState 仅保留最后值。这里用 setImmediate (Node) 模拟
 * "下一个 tick 提交"。
 */
function createReactLikeState(initial, onCommit) {
  let value = initial;
  let lastCommittedValue = initial;
  let pending = false;

  const setState = (next) => {
    value = next;
    if (!pending) {
      pending = true;
      // 用 setImmediate 模拟 "下一个 macrotask 才 commit"
      setImmediate(() => {
        pending = false;
        if (value !== lastCommittedValue) {
          lastCommittedValue = value;
          onCommit(value);
        }
      });
    }
  };

  return { setState };
}

/* ───────────── 模拟 ws 高频推送 chunks ───────────── */

/** 在一个事件循环 tick 内同步发出 N 个 chunks（模拟极端 race） */
function emitChunksSyncBurst(N, send) {
  for (let i = 0; i < N; i++) {
    send({ type: 'text_chunk', content: `c${i}` });
  }
}

/** 异步发出 N 个 chunks，每两个之间隔 delayMs（模拟正常流式） */
async function emitChunksAsync(N, delayMs, send) {
  for (let i = 0; i < N; i++) {
    send({ type: 'text_chunk', content: `c${i}` });
    await new Promise((r) => setTimeout(r, delayMs));
  }
}

/* ───────────── BUGGY 模型：useState 中转 ───────────── */

async function runBuggy(label, emitter) {
  const consumed = [];
  // 消费方：useEffect([lastMessage]) → consumed.push
  const onCommit = (msg) => {
    if (msg && msg.type === 'text_chunk') consumed.push(msg.content);
  };
  const { setState } = createReactLikeState(null, onCommit);

  const send = (msg) => setState(msg);

  await emitter(send);
  // 等微/宏任务全部跑完
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setTimeout(r, 20));

  return { label, consumed };
}

/* ───────────── FIXED 模型：直接回调 ───────────── */

async function runFixed(label, emitter) {
  const consumed = [];
  // ws.onmessage 直接 onMessage(data)
  const onMessage = (msg) => {
    if (msg && msg.type === 'text_chunk') consumed.push(msg.content);
  };

  const send = (msg) => onMessage(msg);

  await emitter(send);
  return { label, consumed };
}

/* ───────────── 测试用例 ───────────── */

async function run() {
  const N = 20;

  console.log(`=== BUGGY（useState 中转）—— 高频同步爆发 ${N} 个 chunks ===`);
  const b1 = await runBuggy('BUGGY/同步爆发', (send) => emitChunksSyncBurst(N, send));
  console.log(`  消费到 ${b1.consumed.length}/${N} 个 chunks: [${b1.consumed.join(',')}]`);
  const buggyDropsBurst = b1.consumed.length < N;
  console.log(`  CASE: ${buggyDropsBurst ? '[OK] 复现 bug —— 中间值被吞' : '[NG] 期望被吞但没吞'}`);

  console.log(`\n=== BUGGY（useState 中转）—— 异步 5ms 间隔 ${N} 个 chunks ===`);
  const b2 = await runBuggy('BUGGY/异步快流', (send) => emitChunksAsync(N, 5, send));
  console.log(`  消费到 ${b2.consumed.length}/${N} 个 chunks: [${b2.consumed.join(',')}]`);
  // 异步间隔时是否被吞取决于 commit 速度;不强断言
  console.log(`  CASE: 消费率 ${((b2.consumed.length / N) * 100).toFixed(0)}%（间隔越短丢得越多）`);

  console.log(`\n=== FIXED（直接回调）—— 同步爆发 ${N} 个 chunks ===`);
  const f1 = await runFixed('FIXED/同步爆发', (send) => emitChunksSyncBurst(N, send));
  console.log(`  消费到 ${f1.consumed.length}/${N} 个 chunks`);
  const fixedAllBurst = f1.consumed.length === N;
  console.log(`  CASE: ${fixedAllBurst ? '[OK] 全部消费' : '[NG] 漏了'}`);

  console.log(`\n=== FIXED（直接回调）—— 异步 5ms 间隔 ${N} 个 chunks ===`);
  const f2 = await runFixed('FIXED/异步快流', (send) => emitChunksAsync(N, 5, send));
  console.log(`  消费到 ${f2.consumed.length}/${N} 个 chunks`);
  const fixedAllAsync = f2.consumed.length === N;
  console.log(`  CASE: ${fixedAllAsync ? '[OK] 全部消费' : '[NG] 漏了'}`);

  const allOk = buggyDropsBurst && fixedAllBurst && fixedAllAsync;
  console.log(`\n=== 总结: ${allOk ? '[OK] bug 复现 + 修复思路有效' : '[BAD] 不符合预期'} ===`);
  process.exit(allOk ? 0 : 1);
}

run().catch((e) => {
  console.error(e);
  process.exit(2);
});
