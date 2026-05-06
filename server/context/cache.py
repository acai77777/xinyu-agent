"""
子 Agent 结果 LRU 缓存——超时降级时使用上一轮结果。

按 session_id 分区，每个 session 保留最近一轮各 agent 的结果。
内存级缓存，进程重启后自动清空。
"""
from collections import OrderedDict


class SubAgentCache:
    def __init__(self, max_sessions: int = 100):
        self._store: OrderedDict[str, dict[str, str]] = OrderedDict()
        self._max = max_sessions

    def get(self, session_id: str, agent_name: str) -> str | None:
        if session_id in self._store:
            return self._store[session_id].get(agent_name)
        return None

    def put(self, session_id: str, agent_name: str, result: str):
        if session_id not in self._store:
            if len(self._store) >= self._max:
                self._store.popitem(last=False)
            self._store[session_id] = {}
        self._store[session_id][agent_name] = result
        self._store.move_to_end(session_id)


# 全局单例
cache = SubAgentCache()
