import React, { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Dimensions, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { TouchableOpacity } from 'react-native';
import { Colors, Radius, Shadows, FontSizes } from '../constants/theme';
import { getMoodHistory, getMoodStats, MoodCheckin, MoodStats } from '../services/api';

const SCREEN_WIDTH = Dimensions.get('window').width;
const CHART_PADDING = 40;
const CHART_WIDTH = SCREEN_WIDTH - 40 - CHART_PADDING * 2;
const CHART_HEIGHT = 180;

const SCORE_EMOJI: Record<number, string> = {
  1: '😫', 2: '😫', 3: '😔', 4: '😔', 5: '😐',
  6: '😐', 7: '😊', 8: '😊', 9: '🥰', 10: '🥰',
};

const SCORE_LABEL: Record<number, string> = {
  1: '很差', 2: '很差', 3: '低落', 4: '低落', 5: '一般',
  6: '一般', 7: '不错', 8: '不错', 9: '很棒', 10: '很棒',
};

function getScoreColor(score: number): string {
  if (score <= 2) return '#E57373';
  if (score <= 4) return '#F5A623';
  if (score <= 6) return '#FFD54F';
  if (score <= 8) return '#81C784';
  return '#4CAF50';
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function formatFullDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export default function MoodTrendScreen() {
  const router = useRouter();
  const [records, setRecords] = useState<MoodCheckin[]>([]);
  const [stats, setStats] = useState<MoodStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getMoodHistory(30), getMoodStats(30)])
      .then(([history, statsData]) => {
        setRecords(history);
        setStats(statsData);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const trendIcon = stats?.trend === 'up'
    ? 'trending-up' : stats?.trend === 'down'
      ? 'trending-down' : 'remove-outline';
  const trendColor = stats?.trend === 'up'
    ? Colors.success : stats?.trend === 'down'
      ? Colors.danger : Colors.textSecondary;
  const trendLabel = stats?.trend === 'up'
    ? '上升趋势' : stats?.trend === 'down'
      ? '下降趋势' : '保持稳定';

  // 按日期聚合（取每天最后一次打卡）
  const dailyMap = new Map<string, MoodCheckin>();
  [...records].reverse().forEach((r) => {
    const day = formatFullDate(r.created_at);
    dailyMap.set(day, r);
  });
  const dailyPoints = Array.from(dailyMap.values());

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={Colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>心情趋势</Text>
        <View style={{ width: 32 }} />
      </View>

      {loading ? (
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      ) : (
        <ScrollView style={styles.scroll} showsVerticalScrollIndicator={false}>
          {/* 统计卡片 */}
          {stats && stats.count > 0 && (
            <View style={styles.statsRow}>
              <View style={[styles.statCard, Shadows.sm]}>
                <Text style={styles.statValue}>
                  {stats.avg_score ?? '-'}
                </Text>
                <Text style={styles.statLabel}>平均分</Text>
              </View>
              <View style={[styles.statCard, Shadows.sm]}>
                <Text style={styles.statValue}>{stats.max_score ?? '-'}</Text>
                <Text style={styles.statLabel}>最高分</Text>
              </View>
              <View style={[styles.statCard, Shadows.sm]}>
                <Text style={styles.statValue}>{stats.min_score ?? '-'}</Text>
                <Text style={styles.statLabel}>最低分</Text>
              </View>
              <View style={[styles.statCard, Shadows.sm]}>
                <Ionicons name={trendIcon as any} size={22} color={trendColor} />
                <Text style={[styles.statLabel, { marginTop: 4 }]}>{trendLabel}</Text>
              </View>
            </View>
          )}

          {/* 简易折线图 */}
          {dailyPoints.length > 1 && (
            <View style={[styles.chartCard, Shadows.sm]}>
              <Text style={styles.chartTitle}>最近 30 天</Text>
              <View style={styles.chart}>
                {/* Y 轴标签 */}
                <View style={styles.yAxis}>
                  <Text style={styles.axisLabel}>10</Text>
                  <Text style={styles.axisLabel}>5</Text>
                  <Text style={styles.axisLabel}>1</Text>
                </View>
                {/* 数据点 */}
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chartScroll}>
                  <View style={[styles.chartInner, { width: Math.max(dailyPoints.length * 36, CHART_WIDTH) }]}>
                    {/* 网格线 */}
                    {[1, 5, 10].map((v) => (
                      <View
                        key={v}
                        style={[
                          styles.gridLine,
                          { bottom: ((v - 1) / 9) * CHART_HEIGHT },
                        ]}
                      />
                    ))}
                    {/* 连线 + 点 */}
                    {dailyPoints.map((p, i) => {
                      const x = i * 36 + 18;
                      const y = ((p.score - 1) / 9) * CHART_HEIGHT;
                      return (
                        <View key={p.id} style={[styles.dotWrap, { left: x - 5, bottom: y - 5 }]}>
                          <View style={[styles.dot, { backgroundColor: getScoreColor(p.score) }]} />
                          <Text style={styles.dotLabel}>{formatDate(p.created_at)}</Text>
                        </View>
                      );
                    })}
                    {/* SVG-less 连线：使用点之间的背景色带 */}
                    {dailyPoints.length > 1 && dailyPoints.map((p, i) => {
                      if (i === 0) return null;
                      const prev = dailyPoints[i - 1];
                      const x1 = (i - 1) * 36 + 18;
                      const y1 = ((prev.score - 1) / 9) * CHART_HEIGHT;
                      const x2 = i * 36 + 18;
                      const y2 = ((p.score - 1) / 9) * CHART_HEIGHT;
                      const dx = x2 - x1;
                      const dy = y2 - y1;
                      const length = Math.sqrt(dx * dx + dy * dy);
                      const angle = Math.atan2(-dy, dx) * (180 / Math.PI);
                      return (
                        <View
                          key={`line-${i}`}
                          style={[
                            styles.line,
                            {
                              left: x1,
                              bottom: y1,
                              width: length,
                              transform: [{ rotate: `${angle}deg` }],
                              transformOrigin: 'left center',
                            },
                          ]}
                        />
                      );
                    })}
                  </View>
                </ScrollView>
              </View>
            </View>
          )}

          {/* 记录列表 */}
          <Text style={styles.listTitle}>打卡记录</Text>
          {records.length === 0 ? (
            <Text style={styles.emptyText}>暂无记录，快去打卡吧~</Text>
          ) : (
            <View style={styles.recordList}>
              {records.map((r) => (
                <View key={r.id} style={[styles.recordCard, Shadows.sm]}>
                  <Text style={styles.recordEmoji}>{SCORE_EMOJI[r.score]}</Text>
                  <View style={styles.recordInfo}>
                    <View style={styles.recordTopRow}>
                      <Text style={[styles.recordScore, { color: getScoreColor(r.score) }]}>
                        {r.score} 分
                      </Text>
                      <Text style={styles.recordLabel}>{SCORE_LABEL[r.score]}</Text>
                    </View>
                    {r.note ? <Text style={styles.recordNote}>{r.note}</Text> : null}
                    <Text style={styles.recordDate}>{formatFullDate(r.created_at)}</Text>
                  </View>
                </View>
              ))}
            </View>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.bgPhone,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  backBtn: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
    color: Colors.text,
  },
  loadingWrap: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scroll: {
    flex: 1,
  },
  statsRow: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    gap: 10,
    marginTop: 8,
  },
  statCard: {
    flex: 1,
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.md,
    padding: 14,
    alignItems: 'center',
  },
  statValue: {
    fontSize: FontSizes.xxl,
    fontWeight: '700',
    color: Colors.text,
  },
  statLabel: {
    fontSize: FontSizes.xs,
    color: Colors.textSecondary,
    marginTop: 2,
  },
  chartCard: {
    marginHorizontal: 20,
    marginTop: 16,
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg,
    padding: 16,
  },
  chartTitle: {
    fontSize: FontSizes.body,
    fontWeight: '600',
    color: Colors.text,
    marginBottom: 12,
  },
  chart: {
    flexDirection: 'row',
    height: CHART_HEIGHT + 30,
  },
  yAxis: {
    width: 24,
    justifyContent: 'space-between',
    paddingBottom: 20,
  },
  axisLabel: {
    fontSize: 10,
    color: Colors.textTertiary,
    textAlign: 'right',
  },
  chartScroll: {
    flex: 1,
  },
  chartInner: {
    height: CHART_HEIGHT + 20,
    position: 'relative',
  },
  gridLine: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 1,
    backgroundColor: Colors.border,
    opacity: 0.5,
  },
  dotWrap: {
    position: 'absolute',
    alignItems: 'center',
    zIndex: 2,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    borderWidth: 2,
    borderColor: '#fff',
  },
  dotLabel: {
    fontSize: 8,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  line: {
    position: 'absolute',
    height: 2,
    backgroundColor: Colors.primary,
    opacity: 0.4,
    zIndex: 1,
  },
  listTitle: {
    fontSize: FontSizes.xl,
    fontWeight: '600',
    color: Colors.text,
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 10,
  },
  emptyText: {
    textAlign: 'center',
    color: Colors.textSecondary,
    fontSize: FontSizes.body,
    paddingVertical: 40,
  },
  recordList: {
    paddingHorizontal: 20,
    paddingBottom: 40,
    gap: 8,
  },
  recordCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 14,
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.md,
  },
  recordEmoji: {
    fontSize: 28,
  },
  recordInfo: {
    flex: 1,
  },
  recordTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  recordScore: {
    fontSize: FontSizes.md,
    fontWeight: '700',
  },
  recordLabel: {
    fontSize: FontSizes.sm,
    color: Colors.textSecondary,
  },
  recordNote: {
    fontSize: FontSizes.body,
    color: Colors.text,
    marginTop: 4,
  },
  recordDate: {
    fontSize: FontSizes.xs,
    color: Colors.textTertiary,
    marginTop: 4,
  },
});
