import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import Slider from '@react-native-community/slider';
import { Colors, Radius, FontSizes } from '../constants/theme';

interface MoodSelectorProps {
  initialScore?: number | null;
  onSubmit: (score: number, note?: string) => void;
  disabled?: boolean;
}

const SCORE_MAP: Record<number, { emoji: string; label: string }> = {
  1: { emoji: '😫', label: '很差' },
  2: { emoji: '😫', label: '很差' },
  3: { emoji: '😔', label: '低落' },
  4: { emoji: '😔', label: '低落' },
  5: { emoji: '😐', label: '一般' },
  6: { emoji: '😐', label: '一般' },
  7: { emoji: '😊', label: '不错' },
  8: { emoji: '😊', label: '不错' },
  9: { emoji: '🥰', label: '很棒' },
  10: { emoji: '🥰', label: '很棒' },
};

function getScoreColor(score: number): string {
  if (score <= 2) return '#E57373';
  if (score <= 4) return '#F5A623';
  if (score <= 6) return '#FFD54F';
  if (score <= 8) return '#81C784';
  return '#4CAF50';
}

export function MoodSelector({ initialScore, onSubmit, disabled }: MoodSelectorProps) {
  const [score, setScore] = useState(initialScore ?? 5);
  const [submitted, setSubmitted] = useState(!!initialScore);

  const info = SCORE_MAP[score];
  const color = getScoreColor(score);

  const handleSubmit = () => {
    setSubmitted(true);
    onSubmit(score);
  };

  if (submitted) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>今日心情</Text>
        <View style={styles.resultRow}>
          <Text style={styles.resultEmoji}>{info.emoji}</Text>
          <Text style={[styles.resultScore, { color }]}>{score} 分</Text>
          <Text style={styles.resultLabel}>· {info.label}</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>现在的心情</Text>

      <View style={styles.scoreDisplay}>
        <Text style={[styles.scoreNumber, { color }]}>{score}</Text>
        <Text style={styles.scoreEmoji}>{info.emoji}</Text>
        <Text style={styles.scoreLabel}>{info.label}</Text>
      </View>

      <View style={styles.sliderRow}>
        <Text style={styles.endLabel}>😞</Text>
        <View style={styles.sliderWrap}>
          <Slider
            style={styles.slider}
            minimumValue={1}
            maximumValue={10}
            step={1}
            value={score}
            onValueChange={(v) => setScore(Math.round(v))}
            minimumTrackTintColor={color}
            maximumTrackTintColor={Colors.border}
            thumbTintColor={color}
            disabled={disabled}
          />
          <View style={styles.tickRow}>
            {Array.from({ length: 10 }, (_, i) => (
              <View
                key={i}
                style={[
                  styles.tick,
                  i + 1 <= score && { backgroundColor: color },
                ]}
              />
            ))}
          </View>
        </View>
        <Text style={styles.endLabel}>😊</Text>
      </View>

      <TouchableOpacity
        style={[styles.submitBtn, { backgroundColor: color }]}
        onPress={handleSubmit}
        activeOpacity={0.8}
        disabled={disabled}
      >
        <Text style={styles.submitText}>记录心情</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginHorizontal: 20,
    marginTop: 16,
    borderRadius: Radius.lg,
    padding: 20,
    overflow: 'hidden',
  },
  title: {
    fontSize: 13,
    color: Colors.textSecondary,
    fontWeight: '500',
    marginBottom: 12,
  },
  scoreDisplay: {
    alignItems: 'center',
    marginBottom: 8,
  },
  scoreNumber: {
    fontSize: 40,
    fontWeight: '700',
  },
  scoreEmoji: {
    fontSize: 28,
    marginTop: 4,
  },
  scoreLabel: {
    fontSize: FontSizes.body,
    color: Colors.textSecondary,
    marginTop: 2,
  },
  sliderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 8,
  },
  endLabel: {
    fontSize: 20,
  },
  sliderWrap: {
    flex: 1,
  },
  slider: {
    width: '100%',
    height: 40,
  },
  tickRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    marginTop: -4,
  },
  tick: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: Colors.border,
  },
  submitBtn: {
    marginTop: 16,
    paddingVertical: 12,
    borderRadius: Radius.md,
    alignItems: 'center',
  },
  submitText: {
    color: '#fff',
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  resultRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  resultEmoji: {
    fontSize: 24,
  },
  resultScore: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  resultLabel: {
    fontSize: FontSizes.body,
    color: Colors.textSecondary,
  },
});
