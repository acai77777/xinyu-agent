/**
 * 复现首页"最近对话"不同步的 bug。
 *
 * 不依赖 React，重写一份最小化生命周期模型来演示问题。
 * 两份实现做对照：
 *   - BUGGY = 当前 app/app/index.tsx 的行为
 *     · useEffect(() => loadSessions(), []) —— 只在首次 mount 拉一次
 *     · 切到 /chat/X 再 back 回来时 HomeScreen 没卸载，useEffect 不重跑
 *   - FIXED = useFocusEffect(useCallback(() => loadSessions(), []))
 *
 * 期望输出：
 *   BUGGY: [FAIL] 焦点回来后还显示旧 sessions
 *   FIXED: [PASS] 焦点回来后看到新 sessions
 *
 * 注意：脚本里的状态机是真实 hook 的重写复刻，不会自动跟代码同步。
 * 它的价值是"演示因果链"而不是"防止回归"。
 */

/** 模拟服务端的 sessions list endpoint */
function makeServer() {
  let sessions = [{ session_id: 'A', title: 'A', preview: '旧内容' }];
  return {
    getSessions: () => structuredClone(sessions),
    /** 模拟用户在 /chat 页面发了消息：A 被更新 + 新建 B */
    simulateChatActivity: () => {
      sessions = [
        { session_id: 'B', title: 'B', preview: '刚发的新消息' },
        { session_id: 'A', title: 'A', preview: 'A 的最新一句' },
      ];
    },
  };
}

/** 模拟 HomeScreen 的生命周期 */
function runHook({ useFocusEffect }) {
  const server = makeServer();
  let displayedSessions = [];

  // 抽出 loadSessions 等价物
  const loadSessions = () => {
    displayedSessions = server.getSessions();
  };

  return {
    server,
    getDisplayed: () => displayedSessions,
    /** 第一次进首页（mount） */
    mount: () => {
      // 两种实现首次 mount 都会拉一次
      loadSessions();
    },
    /** 切到 /chat/X 再 back 回首页（refocus） */
    refocus: () => {
      // BUGGY 实现：useEffect 空依赖，不会重跑
      // FIXED 实现：useFocusEffect 每次都重跑
      if (useFocusEffect) {
        loadSessions();
      }
    },
  };
}

function runCase(label, useFocusEffect) {
  const hook = runHook({ useFocusEffect });

  // 步骤 1：用户首次进首页
  hook.mount();
  const afterMount = hook.getDisplayed();

  // 步骤 2：用户点 A → 进 chat 页 → 在里面聊了消息（服务端 sessions 变了）
  hook.server.simulateChatActivity();

  // 步骤 3：用户 back 回首页（refocus）
  hook.refocus();
  const afterRefocus = hook.getDisplayed();

  console.log(
    `  [${label}] mount 后:`,
    afterMount.map((s) => `${s.session_id}:${s.preview}`),
  );
  console.log(
    `  [${label}] refocus 后:`,
    afterRefocus.map((s) => `${s.session_id}:${s.preview}`),
  );

  // 期望：refocus 后应该看到 B + A 的最新 preview
  const hasB = afterRefocus.some((s) => s.session_id === 'B');
  const aPreviewUpdated = afterRefocus.find((s) => s.session_id === 'A')?.preview === 'A 的最新一句';
  const synced = hasB && aPreviewUpdated;

  return { synced };
}

console.log('=== BUGGY（当前 index.tsx 行为：useEffect 空依赖） ===');
const buggy = runCase('BUGGY', false);
console.log(`  CASE: ${buggy.synced ? '[PASS]' : '[FAIL] 列表没同步'} (期望 [FAIL])`);

console.log('\n=== FIXED（useFocusEffect 每次 focus 重拉） ===');
const fixed = runCase('FIXED', true);
console.log(`  CASE: ${fixed.synced ? '[PASS] 列表同步到最新' : '[FAIL]'} (期望 [PASS])`);

const allOk = !buggy.synced && fixed.synced;
console.log(`\n=== 总结: ${allOk ? '[OK] bug 复现 + 修复生效' : '[BAD] 不符合预期'} ===`);
process.exit(allOk ? 0 : 1);
