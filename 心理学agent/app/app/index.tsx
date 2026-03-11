import React, { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { Colors, Radius, Shadows, FontSizes } from '../constants/theme';
import { MOCK_SESSIONS } from '../constants/mockData';
import { MoodSelector } from '../components/MoodSelector';
import { moodCheckin, getMoodToday } from '../services/api';

export default function HomeScreen() {
  const router = useRouter();
  const [todayScore, setTodayScore] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMoodToday()
      .then((checkin) => {
        if (checkin) setTodayScore(checkin.score);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleMoodSubmit = async (score: number) => {
    try {
      await moodCheckin(score);
      setTodayScore(score);
    } catch {
      setTodayScore(null);
    }
  };

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 6) return '夜深了 🌙';
    if (hour < 12) return '早上好 ☀️';
    if (hour < 18) return '下午好 ☀️';
    return '晚上好 🌙';
  };

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
          {MOCK_SESSIONS.map((s) => (
            <TouchableOpacity
              key={s.id}
              style={[styles.sessionCard, Shadows.sm]}
              onPress={() => router.push(`/chat/${s.id}`)}
              activeOpacity={0.7}
            >
              <View style={[styles.sessionAvatar, { backgroundColor: s.bg }]}>
                <Text style={styles.sessionEmoji}>{s.emoji}</Text>
              </View>
              <View style={styles.sessionInfo}>
                <Text style={styles.sessionName}>{s.name}</Text>
                <Text style={styles.sessionPreview} numberOfLines={1}>{s.preview}</Text>
              </View>
              <View style={styles.sessionMeta}>
                <Text style={styles.sessionTime}>{s.time}</Text>
                {s.unread > 0 && (
                  <View style={styles.sessionBadge}>
                    <Text style={styles.sessionBadgeText}>{s.unread}</Text>
                  </View>
                )}
              </View>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      <TouchableOpacity
        style={styles.fab}
        onPress={() => router.push('/chat/new')}
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
    paddingBottom: 100,
    gap: 10,
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
