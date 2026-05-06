/**
 * 练习卡片——展示 AI 推荐的心理练习（感恩日记、正念呼吸等）
 * 嵌入在聊天消息流中
 */
import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius, Shadows } from '../constants/theme';

const EXERCISE_META: Record<string, { icon: string; color: string; bg: string }> = {
  gratitude_journal:     { icon: '🙏', color: '#F57F17', bg: '#FFF8E1' },
  thought_record:        { icon: '📝', color: '#1565C0', bg: '#E3F2FD' },
  mindful_breathing:     { icon: '🌬️', color: '#00695C', bg: '#E0F2F1' },
  behavioral_activation: { icon: '🚶', color: '#2E7D32', bg: '#E8F5E9' },
  strength_spotting:     { icon: '💪', color: '#6A1B9A', bg: '#F3E5F5' },
  best_possible_self:    { icon: '⭐', color: '#E65100', bg: '#FFF3E0' },
  progressive_relaxation:{ icon: '🧘', color: '#283593', bg: '#E8EAF6' },
};

interface ExerciseCardProps {
  exerciseType: string;
  name: string;
  instruction: string;
  totalSteps?: number;
  followUpPrompts?: string[];
  onStart?: () => void;
}

export function ExerciseCard({
  exerciseType, name, instruction, totalSteps, followUpPrompts, onStart,
}: ExerciseCardProps) {
  const [expanded, setExpanded] = useState(false);
  const meta = EXERCISE_META[exerciseType] || { icon: '📋', color: Colors.primary, bg: Colors.primaryLight };

  return (
    <View style={[styles.card, Shadows.sm]}>
      {/* Header */}
      <View style={styles.header}>
        <View style={[styles.iconWrap, { backgroundColor: meta.bg }]}>
          <Text style={styles.icon}>{meta.icon}</Text>
        </View>
        <View style={styles.headerInfo}>
          <Text style={styles.name}>{name}</Text>
          {totalSteps && (
            <Text style={styles.steps}>共 {totalSteps} 步</Text>
          )}
        </View>
      </View>

      {/* Instruction Preview / Full */}
      <Text style={styles.instruction} numberOfLines={expanded ? undefined : 3}>
        {instruction}
      </Text>

      {instruction.length > 100 && (
        <TouchableOpacity onPress={() => setExpanded(!expanded)}>
          <Text style={[styles.toggle, { color: meta.color }]}>
            {expanded ? '收起' : '展开全部'}
          </Text>
        </TouchableOpacity>
      )}

      {/* Follow-up Prompts */}
      {expanded && followUpPrompts && followUpPrompts.length > 0 && (
        <View style={styles.prompts}>
          {followUpPrompts.map((p, i) => (
            <Text key={i} style={styles.prompt}>• {p}</Text>
          ))}
        </View>
      )}

      {/* Start Button */}
      {onStart && (
        <TouchableOpacity
          style={[styles.startBtn, { backgroundColor: meta.color }]}
          onPress={onStart}
          activeOpacity={0.8}
        >
          <Text style={styles.startText}>开始练习</Text>
          <Ionicons name="arrow-forward" size={14} color="#fff" />
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.md,
    padding: 16,
    marginVertical: 4,
    marginLeft: 36,
    maxWidth: '82%',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 10,
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  icon: {
    fontSize: 20,
  },
  headerInfo: {
    flex: 1,
  },
  name: {
    fontSize: 15,
    fontWeight: '600',
    color: Colors.text,
  },
  steps: {
    fontSize: 12,
    color: Colors.textSecondary,
    marginTop: 1,
  },
  instruction: {
    fontSize: 14,
    lineHeight: 20,
    color: Colors.textSecondary,
  },
  toggle: {
    fontSize: 13,
    fontWeight: '500',
    marginTop: 6,
  },
  prompts: {
    marginTop: 10,
    gap: 4,
  },
  prompt: {
    fontSize: 13,
    lineHeight: 18,
    color: Colors.textSecondary,
  },
  startBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: 12,
    paddingVertical: 10,
    borderRadius: 20,
  },
  startText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },
});
