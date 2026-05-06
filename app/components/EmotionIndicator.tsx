/**
 * 情绪状态指示器——显示在 AI 消息气泡旁，反映检测到的情绪
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Radius } from '../constants/theme';

const EMOTION_MAP: Record<string, { emoji: string; color: string; bg: string }> = {
  '悲伤': { emoji: '😢', color: '#6A1B9A', bg: '#F3E5F5' },
  '焦虑': { emoji: '😰', color: '#E65100', bg: '#FFF3E0' },
  '愤怒': { emoji: '😤', color: '#B71C1C', bg: '#FFEBEE' },
  '恐惧': { emoji: '😨', color: '#4A148C', bg: '#EDE7F6' },
  '疲惫': { emoji: '😮‍💨', color: '#BF360C', bg: '#FBE9E7' },
  '困惑': { emoji: '😕', color: '#283593', bg: '#E8EAF6' },
  '平静': { emoji: '😌', color: '#00695C', bg: '#E0F2F1' },
  '开心': { emoji: '😊', color: '#2E7D32', bg: '#E8F5E9' },
  '感恩': { emoji: '🙏', color: '#F57F17', bg: '#FFF8E1' },
  '希望': { emoji: '✨', color: '#1565C0', bg: '#E3F2FD' },
};

interface EmotionIndicatorProps {
  emotion: string;
  compact?: boolean;
}

export function EmotionIndicator({ emotion, compact }: EmotionIndicatorProps) {
  const info = EMOTION_MAP[emotion];
  if (!info) return null;

  if (compact) {
    return (
      <View style={[styles.compactBadge, { backgroundColor: info.bg }]}>
        <Text style={styles.compactEmoji}>{info.emoji}</Text>
      </View>
    );
  }

  return (
    <View style={[styles.badge, { backgroundColor: info.bg }]}>
      <Text style={styles.emoji}>{info.emoji}</Text>
      <Text style={[styles.label, { color: info.color }]}>{emotion}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 10,
    alignSelf: 'flex-start',
  },
  emoji: {
    fontSize: 12,
  },
  label: {
    fontSize: 11,
    fontWeight: '500',
  },
  compactBadge: {
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
  },
  compactEmoji: {
    fontSize: 11,
  },
});
