/**
 * 复现 useWebSocket 切换 session 时的"幽灵重连"bug。
 *
 * 不依赖 React，重写一份最小化生命周期模型来演示问题。
 * 两份实现做对照：
 *   - BUGGY = 当前 app/services/websocket.ts 的行为
 *     · 切 session 时只 wsRef.current?.close()
 *     · ws.onclose 闭包闭着旧 connect → setTimeout(connect_A, 3000) 重连回旧 session
 *   - FIXED = 先把 onclose/onerror/onmessage 置 null 再 close
 *
 * 期望输出：
 *   BUGGY: [FAIL] 幽灵重连把 wsRef 改回 sid_A
 *   FIXED: [PASS] cleanup 后没有重连
 *
 * 注意：脚本里的状态机是真实 hook 的重写复刻，不会自动跟代码同步。
 * 它的价值是"演示因果链"而不是"防止回归"。
 */

let nowMs = 0;
let nextWsId = 1;

/** 极简 setTimeout 调度器：用 nowMs 模拟时间推进 */
class Scheduler {
  constructor() {
    this.tasks = []; // {fireAt, fn, cancelled}
  }
  setTimeout(fn, ms) {
    const task = { fireAt: nowMs + ms, fn, cancelled: false };
    this.tasks.push(task);
    return task;
  }
  clearTimeout(task) {
    if (task) task.cancelled = true;
  }
  advance(ms) {
    const end = nowMs + ms;
    // 按 fireAt 排序，每次 pop 最早的；fn 可能再加新任务，所以循环到时间用完
    while (true) {
      const ready = this.tasks
        .filter((t) => !t.cancelled && t.fireAt <= end)
        .sort((a, b) => a.fireAt - b.fireAt);
      if (ready.length === 0) break;
      const next = ready[0];
      nowMs = next.fireAt;
      next.cancelled = true; // 标记已触发
      this.tasks = this.tasks.filter((t) => t !== next);
      next.fn();
    }
    nowMs = end;
  }
}

/** Mock WebSocket。new 出来就立刻 OPEN，close() 触发 onclose */
class MockWs {
  constructor(url) {
    this.id = nextWsId++;
    this.url = url;
    this.readyState = 1; // OPEN
    this.onopen = null;
    this.onclose = null;
    this.onerror = null;
    this.onmessage = null;
    // 模拟"创建即 open"
    setTimeout(() => this.onopen?.(), 0);
  }
  close() {
    if (this.readyState === 3) return;
    this.readyState = 3; // CLOSED
    this.onclose?.();
  }
}

/** 安全关闭：先清 handler 再 close，阻断 onclose 触发的自动重连 */
function unbindAndClose(ws) {
  if (!ws) return;
  ws.onclose = null;
  ws.onerror = null;
  ws.onmessage = null;
  ws.close();
}

/** 工厂：跑一遍 hook 的生命周期，返回 wsRef.current 以验证最终连到哪个 sid */
function runHook({ fixCleanup, fixBackground }) {
  const scheduler = new Scheduler();
  const _setTimeout = (fn, ms) => scheduler.setTimeout(fn, ms);
  const _clearTimeout = (t) => scheduler.clearTimeout(t);

  let wsRef = { current: null };
  let reconnectTimer = { current: null };
  let connectedSid = null;
  let connectFn = null;

  /** 模拟 useEffect 的一次 mount：传入 sessionId */
  function mount(sessionId) {
    // useCallback(connect, [sessionId]) —— sessionId 变 connect 重新生成
    connectFn = () => {
      if (!sessionId) return;
      const ws = new MockWs(`wss://x/ws/${sessionId}`);
      ws.onopen = () => {
        connectedSid = sessionId;
      };
      ws.onclose = () => {
        // 这里是 bug：闭包绑死了当前 sessionId 的 connectFn
        reconnectTimer.current = _setTimeout(connectFn, 3000);
      };
      ws.onerror = () => ws.close();
      wsRef.current = ws;
    };
    connectFn();

    // 返回 cleanup 函数（对应 useEffect return）
    return () => {
      _clearTimeout(reconnectTimer.current);
      if (fixCleanup) {
        unbindAndClose(wsRef.current);
      } else {
        wsRef.current?.close();
      }
    };
  }

  /** 模拟 AppState='background' 触发的 close（第二个 useEffect 的分支） */
  function goBackground() {
    if (fixBackground) {
      unbindAndClose(wsRef.current);
    } else {
      wsRef.current?.close();
    }
  }

  return {
    scheduler,
    mount,
    goBackground,
    getRef: () => wsRef,
    getConnected: () => connectedSid,
  };
}

/** CASE1: 切 session 时 cleanup 路径 */
function runCase1(label, opts) {
  const hook = runHook(opts);
  const cleanupA = hook.mount('A');
  hook.scheduler.advance(1);
  const ws_A_id = hook.getRef().current?.id;

  cleanupA();
  const cleanupB = hook.mount('B');
  hook.scheduler.advance(1);
  const ws_B_id = hook.getRef().current?.id;

  hook.scheduler.advance(5000);
  const finalWsId = hook.getRef().current?.id;

  cleanupB();

  console.log(
    `  [${label}] CASE1 切 session: ws_A.id=${ws_A_id}, ws_B.id=${ws_B_id}, 5s 后 wsRef.id=${finalWsId}`,
  );
  return { ghostHappened: finalWsId !== ws_B_id };
}

/** CASE2: AppState=background 路径 */
function runCase2(label, opts) {
  const hook = runHook(opts);
  const cleanupA = hook.mount('A');
  hook.scheduler.advance(1);
  const ws_A_id = hook.getRef().current?.id;

  // 模拟切到后台
  hook.goBackground();

  // 推进 5 秒：buggy 路径会触发幽灵重连
  hook.scheduler.advance(5000);
  const finalWsId = hook.getRef().current?.id;

  cleanupA();

  console.log(
    `  [${label}] CASE2 进 background: ws_A.id=${ws_A_id}, 5s 后 wsRef.id=${finalWsId}`,
  );
  // 期望：background close 后不应自动重连，wsRef 应保持 ws_A
  // BUGGY 下 onclose 会触发 setTimeout(connect, 3000)，3s 后 ws 被新实例覆盖
  return { ghostHappened: finalWsId !== ws_A_id };
}

console.log('=== BUGGY（当前 websocket.ts 行为：cleanup + background 都不清 handler） ===');
const buggy1 = runCase1('BUGGY', { fixCleanup: false, fixBackground: false });
console.log(`  CASE1: ${buggy1.ghostHappened ? '[FAIL] 幽灵重连把 wsRef 改了' : '[PASS]'} (期望 [FAIL])`);
const buggy2 = runCase2('BUGGY', { fixCleanup: false, fixBackground: false });
console.log(`  CASE2: ${buggy2.ghostHappened ? '[FAIL] 后台后被自动重连' : '[PASS]'} (期望 [FAIL])`);

console.log('\n=== FIXED（cleanup + background 都先清 handler 再 close） ===');
const fixed1 = runCase1('FIXED', { fixCleanup: true, fixBackground: true });
console.log(`  CASE1: ${fixed1.ghostHappened ? '[FAIL]' : '[PASS] cleanup 后没有重连'} (期望 [PASS])`);
const fixed2 = runCase2('FIXED', { fixCleanup: true, fixBackground: true });
console.log(`  CASE2: ${fixed2.ghostHappened ? '[FAIL]' : '[PASS] background 后没有重连'} (期望 [PASS])`);

const allOk =
  buggy1.ghostHappened && buggy2.ghostHappened && !fixed1.ghostHappened && !fixed2.ghostHappened;
console.log(`\n=== 总结: ${allOk ? '[OK] bug 复现 + 修复生效' : '[BAD] 不符合预期'} ===`);
process.exit(allOk ? 0 : 1);
