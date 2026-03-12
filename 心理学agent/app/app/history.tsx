import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius, Shadows, FontSizes } from '../constants/theme';
import { API_BASE_URL, getToken } from '../services/api';

interface SessionItem {
  session_id: string;
  title: string;
  preview: string;
  updated_at: string;
  message_count: number;
}

interface GroupedSessions {
  [group: string]: SessionItem[];
}

function groupSessions(sessions: SessionItem[]): GroupedSessions {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

  const groups: GroupedSessions = {};

  for (const s of sessions) {
    const d = new Date(s.updated_at);
    let group: string;
    if (d >= today) {
      group = '今天';
    } else if (d >= weekAgo) {
      group = '本周';
    } else {
      group = '更早';
    }
    if (!groups[group]) groups[group] = [];
    groups[group].push(s);
  }

  return groups;
}

const GROUP_ORDER = ['今天', '本周', '更早'];
const COLORS = ['#F5A623', '#8B9DC3', '#6BBF8A', '#C4A882', '#3A7CA5', '#E57373'];

export default function HistoryScreen() {
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadSessions = useCallback(() => {
    setLoading(true);
    const token = getToken();
    fetch(`${API_BASE_URL}/api/history/sessions`, {
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
      .then((res) => res.json())
      .then((data) => setSessions(data.sessions || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // 每次进入页面时刷新
  useFocusEffect(useCallback(() => { loadSessions(); }, []));

  const handleDelete = (sessionId: string) => {
    Alert.alert('删除对话', '确定要删除这个对话吗？', [
      { text: '取消', style: 'cancel' },
      {
        text: '删除', style: 'destructive', onPress: async () => {
          try {
            await fetch(`${API_BASE_URL}/api/history/sessions/${sessionId}`, { method: 'DELETE' });
            setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
          } catch {}
        }
      },
    ]);
  };

  const grouped = groupSessions(sessions);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.navBar}>
        <View />
        <Text style={styles.navTitle}>历史记录</Text>
        <View />
      </View>
      <ScrollView style={styles.scroll} showsVerticalScrollIndicator={false}>
        {loading ? (
          <ActivityIndicator color={Colors.primary} style={{ marginTop: 40 }} />
        ) : sessions.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Ionicons name="chatbubbles-outline" size={48} color={Colors.textTertiary} />
            <Text style={styles.emptyText}>还没有对话记录</Text>
          </View>
        ) : (
          GROUP_ORDER.filter((g) => grouped[g]).map((group) => (
            <View key={group}>
              <Text style={styles.groupLabel}>{group}</Text>
              <View style={styles.list}>
                {grouped[group].map((item, idx) => {
                  const color = COLORS[idx % COLORS.length];
                  return (
                    <TouchableOpacity
                      key={item.session_id}
                      style={[styles.card, Shadows.sm]}
                      onPress={() => router.push(`/chat/${item.session_id}`)}
                      onLongPress={() => handleDelete(item.session_id)}
                      activeOpacity={0.7}
                    >
                      <View style={[styles.icon, { backgroundColor: color + '18' }]}>
                        <Text style={[styles.iconText, { color }]}>
                          {(item.title || '新')[0]}
                        </Text>
                      </View>
                      <View style={styles.info}>
                        <Text style={styles.title}>{item.title || '新对话'}</Text>
                        <Text style={styles.summary} numberOfLines={1}>
                          {item.preview || `${item.message_count} 条消息`}
                        </Text>
                      </View>
                      <Ionicons name="chevron-forward" size={14} color={Colors.textTertiary} />
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>
          ))
        )}
        <View style={{ height: 20 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bgPhone },
  navBar: {
    height: 52,
    paddingHorizontal: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 0.5,
    borderBottomColor: Colors.border,
  },
  navTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
    color: Colors.text,
    letterSpacing: -0.2,
  },
  scroll: { flex: 1 },
  groupLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.textSecondary,
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  list: {
    paddingHorizontal: 20,
    gap: 8,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    padding: 14,
    paddingHorizontal: 16,
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.md,
  },
  icon: {
    width: 42,
    height: 42,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconText: {
    fontSize: 18,
    fontWeight: '600',
  },
  info: { flex: 1 },
  title: {
    fontSize: FontSizes.body,
    fontWeight: '500',
    color: Colors.text,
  },
  summary: {
    fontSize: 13,
    color: Colors.textSecondary,
    marginTop: 2,
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    paddingTop: 60,
  },
  emptyText: {
    fontSize: FontSizes.body,
    color: Colors.textSecondary,
  },
});
