/**
 * 语音录制按钮——长按录音，松开发送
 */
import React, { useState, useRef, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, Animated, StyleSheet,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius } from '../constants/theme';
import { startRecording, stopRecording } from '../services/audio';

interface VoiceRecorderProps {
  onRecordComplete: (uri: string) => void;
  disabled?: boolean;
}

export function VoiceRecorder({ onRecordComplete, disabled }: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [duration, setDuration] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval>>(undefined);
  const pulseAnim = useRef(new Animated.Value(1)).current;

  const startPulse = () => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1.3, duration: 600, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 600, useNativeDriver: true }),
      ]),
    ).start();
  };

  const stopPulse = () => {
    pulseAnim.stopAnimation();
    pulseAnim.setValue(1);
  };

  const handlePressIn = useCallback(async () => {
    if (disabled) return;
    try {
      await startRecording();
      setIsRecording(true);
      setDuration(0);

      timerRef.current = setInterval(() => {
        setDuration((d) => d + 1);
      }, 1000);

      startPulse();
    } catch {
      // 权限被拒绝或录制失败
    }
  }, [disabled]);

  const handlePressOut = useCallback(async () => {
    if (!isRecording) return;

    clearInterval(timerRef.current);
    stopPulse();
    setIsRecording(false);

    const uri = await stopRecording();
    if (uri && duration >= 1) {
      onRecordComplete(uri);
    }
    setDuration(0);
  }, [isRecording, duration, onRecordComplete]);

  const formatDuration = (s: number) => {
    const min = Math.floor(s / 60);
    const sec = s % 60;
    return `${min}:${sec.toString().padStart(2, '0')}`;
  };

  return (
    <View style={styles.container}>
      {isRecording && (
        <View style={styles.indicator}>
          <View style={styles.redDot} />
          <Text style={styles.timer}>{formatDuration(duration)}</Text>
        </View>
      )}
      <TouchableOpacity
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        activeOpacity={0.7}
        disabled={disabled}
        style={styles.btnWrap}
      >
        <Animated.View
          style={[
            styles.btn,
            isRecording && styles.btnRecording,
            { transform: [{ scale: pulseAnim }] },
          ]}
        >
          <Ionicons
            name={isRecording ? 'stop' : 'mic-outline'}
            size={22}
            color={isRecording ? '#fff' : Colors.textSecondary}
          />
        </Animated.View>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  indicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    position: 'absolute',
    top: -28,
    backgroundColor: Colors.bgCard,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  redDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Colors.danger,
  },
  timer: {
    fontSize: 12,
    color: Colors.danger,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  btnWrap: {},
  btn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnRecording: {
    backgroundColor: Colors.danger,
  },
});
