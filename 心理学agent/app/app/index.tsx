import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, Linking,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { Colors, Radius, Shadows, FontSizes } from '../constants/theme';
import { MoodSelector } from '../components/MoodSelector';
import { moodCheckin, getMoodToday, API_BASE_URL, getToken } from '../services/api';

interface SessionItem {
  session_id: string;
  title: string;
  preview: string;
  updated_at: string;
  message_count: number;
}

export default function HomeScreen() {
  const router = useRouter();
  const [todayScore, setTodayScore] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  // 首次加载才显示 ActivityIndicator;后续每次焦点回来都静默刷新,
  // 否则用户从 /chat 返回时列表会闪一下空白。
  const [firstLoadDone, setFirstLoadDone] = useState(false);

  // 加载今日心情
  useEffect(() => {
    getMoodToday()
      .then((checkin) => {
        if (checkin) setTodayScore(checkin.score);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // 加载最近会话
  const loadSessions = useCallback(() => {
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
      .finally(() => setFirstLoadDone(true));
  }, []);

  // 每次首页重获焦点都重拉:从 /chat 返回时把新建/更新的 session 同步过来。
  useFocusEffect(useCallback(() => { loadSessions(); }, [loadSessions]));

  const handleMoodSubmit = async (score: number) => {
    try {
      await moodCheckin(score);
      setTodayScore(score);
    } catch {
      setTodayScore(null);
    }
  };

  const handleNewChat = async () => {
    try {
      const token = getToken();
      const res = await fetch(`${API_BASE_URL}/api/history/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ title: '' }),
      });
      const data = await res.json();
      router.push(`/chat/${data.session_id}`);
    } catch {
      router.push('/chat/new');
    }
  };

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 6) return '夜深了 🌙';
    if (hour < 12) return '早上好 ☀️';
    if (hour < 18) return '下午好 ☀️';
    return '晚上好 🌙';
  };

  const formatTime = (isoStr: string) => {
    const d = new Date(isoStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) {
      return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    }
    if (diffDays === 1) return '昨天';
    if (diffDays < 7) return `${diffDays}天前`;
    return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
  };

  const EMOJIS = ['🌿', '🌸', '🍃', '✨', '🌊', '🌙', '🌻', '🦋'];
  const BG_COLORS = ['#E8F2F8', '#F5EBF0', '#EBF5EC', '#FFF5E8', '#E8ECF5', '#F0E8F5', '#FFF8E8', '#E8F5F0'];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView style={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Text style={styles.greeting}>{getGreeting()}</Text>
          <Text style={styles.greetingSub}>今天想聊点什么？</Text>
        </View>

        <LinearGradient
          colors={['#E8F2F8', '#F0E8F5']}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.moodGradient}
        >
          {!loading && (
            <MoodSelector
              initialScore={todayScore}
              onSubmit={handleMoodSubmit}
            />
          )}
        </LinearGradient>

        {todayScore !== null && (
          <TouchableOpacity
            style={styles.trendEntry}
            onPress={() => router.push('/mood-trend')}
            activeOpacity={0.7}
          >
            <Ionicons name="trending-up-outline" size={18} color={Colors.primary} />
            <Text style={styles.trendEntryText}>查看心情趋势</Text>
            <Ionicons name="chevron-forward" size={16} color={Colors.textTertiary} />
          </TouchableOpacity>
        )}

        <Text style={styles.sectionTitle}>最近对话</Text>
        <View style={styles.sessionList}>
          {!firstLoadDone ? (
            <ActivityIndicator color={Colors.primary} style={{ marginTop: 20 }} />
          ) : sessions.length === 0 ? (
            <TouchableOpacity
              style={[styles.emptyCard, Shadows.sm]}
              onPress={handleNewChat}
              activeOpacity={0.7}
            >
              <Ionicons name="chatbubble-ellipses-outline" size={32} color={Colors.textTertiary} />
              <Text style={styles.emptyText}>还没有对话，点击开始第一次聊天</Text>
            </TouchableOpacity>
          ) : (
            sessions.slice(0, 5).map((s, idx) => (
              <TouchableOpacity
                key={s.session_id}
                style={[styles.sessionCard, Shadows.sm]}
                onPress={() => router.push(`/chat/${s.session_id}`)}
                activeOpacity={0.7}
              >
                <View style={[styles.sessionAvatar, { backgroundColor: BG_COLORS[idx % BG_COLORS.length] }]}>
                  <Text style={styles.sessionEmoji}>{EMOJIS[idx % EMOJIS.length]}</Text>
                </View>
                <View style={styles.sessionInfo}>
                  <Text style={styles.sessionName}>{s.title || '新对话'}</Text>
                  <Text style={styles.sessionPreview} numberOfLines={1}>
                    {s.preview || `${s.message_count} 条消息`}
                  </Text>
                </View>
                <View style={styles.sessionMeta}>
                  <Text style={styles.sessionTime}>{formatTime(s.updated_at)}</Text>
                </View>
              </TouchableOpacity>
            ))
          )}
        </View>

        <TouchableOpacity
          style={styles.icpFooter}
          onPress={() => Linking.openURL('https://beian.miit.gov.cn')}
          activeOpacity={0.6}
        >
          <Text style={styles.icpText}>粤ICP备2026021933号-1</Text>
        </TouchableOpacity>
      </ScrollView>

      <TouchableOpacity
        style={styles.fab}
        onPress={handleNewChat}
        activeOpacity={0.8}
      >
        <Ionicons name="add" size={28} color="#fff" />
      </TouchableOpacity>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.bgPhone,
  },
  scroll: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 20,
  },
  greeting: {
    fontSize: FontSizes.title,
    fontWeight: '700',
    color: Colors.text,
    letterSpacing: -0.5,
  },
  greetingSub: {
    fontSize: FontSizes.body,
    color: Colors.textSecondary,
    marginTop: 4,
  },
  moodGradient: {
    marginHorizontal: 20,
    marginTop: 16,
    borderRadius: Radius.lg,
  },
  trendEntry: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginHorizontal: 20,
    marginTop: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.md,
  },
  trendEntryText: {
    flex: 1,
    fontSize: FontSizes.body,
    color: Colors.primary,
    fontWeight: '500',
  },
  sectionTitle: {
    fontSize: FontSizes.xl,
    fontWeight: '600',
    color: Colors.text,
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 10,
    letterSpacing: -0.3,
  },
  sessionList: {
    paddingHorizontal: 20,
    paddingBottom: 20,
    gap: 10,
  },
  icpFooter: {
    alignItems: 'center',
    paddingVertical: 16,
    paddingBottom: 100,
  },
  icpText: {
    fontSize: 12,
    color: Colors.textTertiary,
  },
  emptyCard: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    padding: 32,
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.md,
  },
  emptyText: {
    fontSize: FontSizes.body,
    color: Colors.textSecondary,
  },
  sessionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    padding: 14,
    paddingHorizontal: 16,
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.md,
  },
  sessionAvatar: {
    width: 48,
    height: 48,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sessionEmoji: {
    fontSize: 22,
  },
  sessionInfo: {
    flex: 1,
  },
  sessionName: {
    fontSize: FontSizes.md,
    fontWeight: '500',
    color: Colors.text,
  },
  sessionPreview: {
    fontSize: 13,
    color: Colors.textSecondary,
    marginTop: 2,
  },
  sessionMeta: {
    alignItems: 'flex-end',
  },
  sessionTime: {
    fontSize: FontSizes.sm,
    color: Colors.textTertiary,
  },
  sessionBadge: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 4,
  },
  sessionBadgeText: {
    fontSize: 11,
    color: '#fff',
    fontWeight: '600',
  },
  fab: {
    position: 'absolute',
    bottom: 24,
    right: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    ...Shadows.lg,
    shadowColor: Colors.primary,
    shadowOpacity: 0.35,
    elevation: 8,
  },
});
