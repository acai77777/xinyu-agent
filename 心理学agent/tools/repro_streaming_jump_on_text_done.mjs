/**
 * 复现"流式输出在 text_done 时一次性蹦出一大段"的 bug。
 *
 * 背景：客户端 WS 在流式过程中断开 → 后端 stream_cb 大面积失败但 run_agent
 * 继续跑 → 跑完后 text_done 一次性带完整 final_text 到前端 → 前端 accumulated
 * 几乎是空（或断点前的一小段），整段替换造成"一坨蹦出"。
 *
 * 两份实现对照：
 *   - BUGGY = 当前 chatStore.ts 的 finalizeStreamingMessage
 *     · 拿到 final_text 直接整段替换 accumulated
 *     · 视觉：瞬间从短跳到长
 *   - FIXED = smart merge
 *     · 若 final.startsWith(accumulated) → 启动 ~400ms 尾巴动画分帧 append
 *     · 否则（审核改写） → 整段替换（与 BUGGY 等价）
 *
 * 注意：这份脚本是 chatStore 真实逻辑的等价重写,不会自动跟代码同步。
 * 它的价值是"演示因果链 + 验证修复思路"而不是"防止回归"。
 */

const TAIL_ANIM_TOTAL_MS = 400;
const TAIL_ANIM_FRAMES = 20;
const TAIL_ANIM_INTERVAL_MS = TAIL_ANIM_TOTAL_MS / TAIL_ANIM_FRAMES; // 20ms

/** 模拟 chatStore 的最小子集 —— 只保留这次要测的部分 */
function makeStore({ smartMerge }) {
  let state = {
    last: { content: '', isStreaming: true, emotion: undefined },
  };
  let tailTimer = null;
  const listeners = [];

  const emit = () => listeners.forEach((fn) => fn(state));
  const subscribe = (fn) => listeners.push(fn);
  const snapshot = () => ({
    content: state.last.content,
    isStreaming: state.last.isStreaming,
    emotion: state.last.emotion,
  });

  const cancelTailAnimation = () => {
    if (tailTimer) {
      clearTimeout(tailTimer);
      tailTimer = null;
    }
  };

  const appendDelta = (delta) => {
    state.last.content += delta;
    emit();
  };

  const finalize = (finalContent, emotion) => {
    cancelTailAnimation();
    if (!state.last.isStreaming) return;

    // 旧协议 null content 兜底：直接 finalize 当前累积
    if (finalContent === null) {
      state.last.isStreaming = false;
      state.last.emotion = emotion ?? state.last.emotion;
      emit();
      return;
    }

    const accumulated = state.last.content;

    if (!smartMerge) {
      // BUGGY：整段替换
      state.last.content = finalContent;
      state.last.emotion = emotion ?? state.last.emotion;
      state.last.isStreaming = false;
      emit();
      return;
    }

    // FIXED case A: final 以 accumulated 为前缀且更长 → 尾巴动画
    if (
      finalContent.startsWith(accumulated) &&
      finalContent.length > accumulated.length
    ) {
      const tailLen = finalContent.length - accumulated.length;
      const charsPerTick = Math.max(1, Math.ceil(tailLen / TAIL_ANIM_FRAMES));

      const tick = () => {
        const cur = state.last.content;
        const remaining = finalContent.length - cur.length;
        if (remaining <= 0) {
          state.last.content = finalContent;
          state.last.emotion = emotion ?? state.last.emotion;
          state.last.isStreaming = false;
          tailTimer = null;
          emit();
          return;
        }
        const step = Math.min(charsPerTick, remaining);
        state.last.content = finalContent.slice(0, cur.length + step);
        emit();
        tailTimer = setTimeout(tick, TAIL_ANIM_INTERVAL_MS);
      };
      tailTimer = setTimeout(tick, TAIL_ANIM_INTERVAL_MS);
      return;
    }

    // FIXED case B: 审核改写 / final 比 accumulated 短 → 整段替换
    state.last.content = finalContent;
    state.last.emotion = emotion ?? state.last.emotion;
    state.last.isStreaming = false;
    emit();
  };

  /** 用于打断动画的外部事件（如 setSession / clearCurrent） */
  const interruptWithJumpToEnd = (finalContent) => {
    cancelTailAnimation();
    if (finalContent !== undefined) {
      state.last.content = finalContent;
      state.last.isStreaming = false;
      emit();
    }
  };

  return {
    appendDelta,
    finalize,
    interruptWithJumpToEnd,
    snapshot,
    subscribe,
  };
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/* ───────────── 测试用例 ───────────── */

/** CASE 1: 经典场景 —— accumulated 是 final 的前缀，差距巨大 */
async function case1_classic({ smartMerge, label }) {
  const store = makeStore({ smartMerge });
  // 流式收到了一小段
  store.appendDelta('你好，今天');
  // 假设 ws 断了 → 累积停在这里
  const FINAL = '你好，今天天气真好，希望你也心情愉快！记得照顾好自己 😊';

  // 收到 text_done
  store.finalize(FINAL);

  // 立即（finalize 调用之后那一帧）的 content
  const immediate = store.snapshot();

  if (!smartMerge) {
    // BUGGY: 立刻整段
    const passed = immediate.content === FINAL && immediate.isStreaming === false;
    return { label, passed, detail: `immediate.content.length=${immediate.content.length}/${FINAL.length}` };
  } else {
    // FIXED: 立刻应该还没补完
    const stillAnimating =
      immediate.content !== FINAL && immediate.content.startsWith('你好，今天');
    // 等动画结束
    await wait(TAIL_ANIM_TOTAL_MS + 100);
    const final = store.snapshot();
    const completed = final.content === FINAL && final.isStreaming === false;
    return {
      label,
      passed: stillAnimating && completed,
      detail: `immediate.content.length=${immediate.content.length}, final.content.length=${final.content.length}/${FINAL.length}, stillAnimating=${stillAnimating}, completed=${completed}`,
    };
  }
}

/** CASE 2: final === accumulated → 不需要动画，直接 finalize */
async function case2_equal({ smartMerge, label }) {
  const store = makeStore({ smartMerge });
  const TEXT = '你好，世界。';
  store.appendDelta(TEXT);
  store.finalize(TEXT);
  const immediate = store.snapshot();
  const ok = immediate.content === TEXT && immediate.isStreaming === false;
  return { label, passed: ok, detail: `content=${immediate.content}, isStreaming=${immediate.isStreaming}` };
}

/** CASE 3: 审核改写（accumulated 不是 final 前缀） → 整段替换 */
async function case3_rewrite({ smartMerge, label }) {
  const store = makeStore({ smartMerge });
  store.appendDelta('我觉得自杀也许是');
  const FINAL = '听到你这么说我很担心。如果有自伤念头，请拨打 24 小时心理援助热线 400-161-9995。';
  store.finalize(FINAL);
  const immediate = store.snapshot();
  // 两种实现都期望"立即整段替换"
  const ok = immediate.content === FINAL && immediate.isStreaming === false;
  return { label, passed: ok, detail: `content.len=${immediate.content.length}/${FINAL.length}` };
}

/** CASE 4: accumulated 为空（ws 一开始就断了） → smart merge 走 case A 整段动画 */
async function case4_empty_accumulated({ smartMerge, label }) {
  const store = makeStore({ smartMerge });
  // 不 appendDelta，模拟从未收到 chunk
  const FINAL = '这是一段从未流式过的完整回复。';
  store.finalize(FINAL);
  const immediate = store.snapshot();

  if (!smartMerge) {
    const ok = immediate.content === FINAL && immediate.isStreaming === false;
    return { label, passed: ok, detail: `BUGGY: 立即整段` };
  } else {
    const stillAnimating = immediate.content !== FINAL && immediate.content.length < FINAL.length;
    await wait(TAIL_ANIM_TOTAL_MS + 100);
    const final = store.snapshot();
    const completed = final.content === FINAL && final.isStreaming === false;
    return {
      label,
      passed: stillAnimating && completed,
      detail: `immediate.len=${immediate.content.length}, final.len=${final.content.length}, anim=${stillAnimating}, done=${completed}`,
    };
  }
}

/** CASE 5: final 极短（< accumulated.length） → 走 case B 整段替换 */
async function case5_truncation({ smartMerge, label }) {
  const store = makeStore({ smartMerge });
  store.appendDelta('一段很长的累积内容，被后置审核截断了');
  const FINAL = '简短回复。';
  store.finalize(FINAL);
  const immediate = store.snapshot();
  const ok = immediate.content === FINAL && immediate.isStreaming === false;
  return { label, passed: ok, detail: `immediate.content=${immediate.content}` };
}

/** CASE 6: 动画中被 interrupt → jump-to-end */
async function case6_interrupt({ label }) {
  const store = makeStore({ smartMerge: true });
  store.appendDelta('你好，');
  const FINAL = '你好，这是补完中的一段长长长长长长长长长长长长长长长长长长内容。';
  store.finalize(FINAL);

  // 立即（动画刚启动）
  await wait(50);
  const mid = store.snapshot();
  const midOk = mid.content !== FINAL && mid.content.startsWith('你好，');

  // 模拟用户切 session → interrupt
  store.interruptWithJumpToEnd(FINAL);
  const afterInterrupt = store.snapshot();
  const interruptOk =
    afterInterrupt.content === FINAL && afterInterrupt.isStreaming === false;

  // 等更久，确保动画不再继续触发
  await wait(TAIL_ANIM_TOTAL_MS);
  const final = store.snapshot();
  const stableOk = final.content === FINAL && final.isStreaming === false;

  return {
    label,
    passed: midOk && interruptOk && stableOk,
    detail: `mid.len=${mid.content.length}, afterInterrupt.ok=${interruptOk}, stable.ok=${stableOk}`,
  };
}

/** CASE 7: 连续两次 finalize → 后者取代前者 */
async function case7_double_finalize({ label }) {
  const store = makeStore({ smartMerge: true });
  store.appendDelta('A');
  store.finalize('ABCDEFGHIJ'); // 启动动画 1
  await wait(40); // 让动画跑两帧
  store.finalize('AXYZWVUTSRQP'); // 注意 startsWith('A') 仍成立，但目标变了
  // 等到第二个动画完成
  await wait(TAIL_ANIM_TOTAL_MS + 100);
  const final = store.snapshot();
  const ok = final.content === 'AXYZWVUTSRQP' && final.isStreaming === false;
  return { label, passed: ok, detail: `final.content=${final.content}` };
}

/* ───────────── 运行 ───────────── */

async function run() {
  console.log('=== BUGGY（当前 chatStore.finalizeStreamingMessage：整段替换） ===');
  const b1 = await case1_classic({ smartMerge: false, label: 'BUGGY/CASE1 经典跳变' });
  const b2 = await case2_equal({ smartMerge: false, label: 'BUGGY/CASE2 final===accumulated' });
  const b3 = await case3_rewrite({ smartMerge: false, label: 'BUGGY/CASE3 审核改写' });
  const b4 = await case4_empty_accumulated({ smartMerge: false, label: 'BUGGY/CASE4 空累积' });
  const b5 = await case5_truncation({ smartMerge: false, label: 'BUGGY/CASE5 截断' });

  // BUGGY 期望：CASE1 也"立即整段"（这就是 bug 表现，所以 passed=true 表示 bug 被复现）
  for (const r of [b1, b2, b3, b4, b5]) {
    console.log(`  [${r.passed ? 'OK' : 'NG'}] ${r.label} — ${r.detail}`);
  }

  console.log('\n=== FIXED（smart merge：尾巴 ~400ms 动画补完） ===');
  const f1 = await case1_classic({ smartMerge: true, label: 'FIXED/CASE1 平滑补完' });
  const f2 = await case2_equal({ smartMerge: true, label: 'FIXED/CASE2 final===accumulated' });
  const f3 = await case3_rewrite({ smartMerge: true, label: 'FIXED/CASE3 审核改写仍整段' });
  const f4 = await case4_empty_accumulated({ smartMerge: true, label: 'FIXED/CASE4 空累积也走动画' });
  const f5 = await case5_truncation({ smartMerge: true, label: 'FIXED/CASE5 截断走整段替换' });
  const f6 = await case6_interrupt({ label: 'FIXED/CASE6 动画中被 interrupt 跳到末尾' });
  const f7 = await case7_double_finalize({ label: 'FIXED/CASE7 连续两次 finalize' });

  for (const r of [f1, f2, f3, f4, f5, f6, f7]) {
    console.log(`  [${r.passed ? 'OK' : 'NG'}] ${r.label} — ${r.detail}`);
  }

  const allOk =
    b1.passed && b2.passed && b3.passed && b4.passed && b5.passed &&
    f1.passed && f2.passed && f3.passed && f4.passed && f5.passed && f6.passed && f7.passed;
  console.log(`\n=== 总结: ${allOk ? '[OK] bug 复现 + 修复思路全部通过' : '[BAD] 有用例未通过'} ===`);
  process.exit(allOk ? 0 : 1);
}

run().catch((e) => {
  console.error(e);
  process.exit(2);
});
