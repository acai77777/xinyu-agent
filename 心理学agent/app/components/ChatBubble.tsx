import React, { useState } from 'react';
import { View, Text, Image, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius } from '../constants/theme';
import { Message } from '../types';
import { EmotionIndicator } from './EmotionIndicator';
import { ExerciseCard } from './ExerciseCard';
import { playAudio, stopPlayback } from '../services/audio';

interface ChatBubbleProps {
  message: Message;
}

export function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === 'user';
  const [isPlaying, setIsPlaying] = useState(false);
  const timeStr =
    message.timestamp instanceof Date
      ? message.timestamp.getHours().toString().padStart(2, '0') +
        ':' +
        message.timestamp.getMinutes().toString().padStart(2, '0')
      : '';

  // 练习卡片单独渲染
  if (message.type === 'exercise' && message.exercise) {
    return (
      <View style={[styles.row, styles.rowAi]}>
        <View style={styles.avatarTiny}>
          <Text style={styles.avatarText}>🌿</Text>
        </View>
        <View style={styles.bubbleWrap}>
          <ExerciseCard
            exerciseType={message.exercise.exerciseType}
            name={message.exercise.name}
            instruction={message.exercise.instruction}
            totalSteps={message.exercise.totalSteps}
            followUpPrompts={message.exercise.followUpPrompts}
          />
          <Text style={[styles.time, styles.timeAi]}>{timeStr}</Text>
        </View>
      </View>
    );
  }

  const handlePlayAudio = async () => {
    if (!message.audioUrl) return;
    if (isPlaying) {
      await stopPlayback();
      setIsPlaying(false);
    } else {
      setIsPlaying(true);
      try {
        await playAudio(message.audioUrl);
      } finally {
        setIsPlaying(false);
      }
    }
  };

  return (
    <View style={[styles.row, isUser ? styles.rowUser : styles.rowAi]}>
      {!isUser && (
        <View style={styles.avatarTiny}>
          <Text style={styles.avatarText}>🌿</Text>
        </View>
      )}
      <View style={styles.bubbleWrap}>
        <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAi]}>
          {/* 图片消息 */}
          {message.type === 'image' && message.imageUri && (
            <Image
              source={{ uri: message.imageUri }}
              style={styles.image}
              resizeMode="cover"
            />
          )}

          {/* 语音消息 */}
          {message.type === 'voice' && (
            <TouchableOpacity style={styles.voiceRow} onPress={handlePlayAudio}>
              <Ionicons
                name={isPlaying ? 'pause' : 'play'}
                size={18}
                color={isUser ? '#fff' : Colors.primary}
              />
              <View style={styles.voiceWaves}>
                {[0.4, 0.7, 1, 0.6, 0.8, 0.5, 0.9].map((h, i) => (
                  <View
                    key={i}
                    style={[
                      styles.voiceBar,
                      {
                        height: 14 * h,
                        backgroundColor: isUser ? 'rgba(255,255,255,0.6)' : Colors.primary,
                        opacity: isPlaying ? 1 : 0.5,
                      },
                    ]}
                  />
                ))}
              </View>
            </TouchableOpacity>
          )}

          {/* 文字内容（图片消息可附带描述） */}
          {message.content ? (
            <Text style={[styles.bubbleText, isUser && styles.bubbleTextUser]}>
              {message.content}
            </Text>
          ) : null}
        </View>

        {/* AI 消息的情绪标签 */}
        {!isUser && message.emotion && (
          <View style={styles.emotionWrap}>
            <EmotionIndicator emotion={message.emotion} />
          </View>
        )}

        {/* AI 语音回复播放按钮 */}
        {!isUser && message.audioUrl && message.type === 'text' && (
          <TouchableOpacity style={styles.listenBtn} onPress={handlePlayAudio}>
            <Ionicons
              name={isPlaying ? 'pause-circle' : 'volume-medium-outline'}
              size={16}
              color={Colors.primary}
            />
            <Text style={styles.listenText}>
              {isPlaying ? '暂停' : '听语音'}
            </Text>
          </TouchableOpacity>
        )}

        <Text style={[styles.time, isUser ? styles.timeUser : styles.timeAi]}>
          {timeStr}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: 8,
    maxWidth: '82%',
    marginBottom: 8,
  },
  rowUser: {
    alignSelf: 'flex-end',
    flexDirection: 'row-reverse',
  },
  rowAi: {
    alignSelf: 'flex-start',
  },
  avatarTiny: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
    backgroundColor: '#E8F2F8',
  },
  avatarText: {
    fontSize: 13,
  },
  bubbleWrap: {
    flexShrink: 1,
  },
  bubble: {
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 18,
    overflow: 'hidden',
  },
  bubbleUser: {
    backgroundColor: Colors.bgBubbleUser,
    borderBottomRightRadius: 6,
  },
  bubbleAi: {
    backgroundColor: Colors.bgBubbleAi,
    borderBottomLeftRadius: 6,
  },
  bubbleText: {
    fontSize: 15,
    lineHeight: 20,
    color: Colors.text,
    letterSpacing: -0.1,
  },
  bubbleTextUser: {
    color: '#FFFFFF',
  },
  image: {
    width: 200,
    height: 150,
    borderRadius: 12,
    marginBottom: 6,
  },
  voiceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    minWidth: 120,
  },
  voiceWaves: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    flex: 1,
  },
  voiceBar: {
    width: 3,
    borderRadius: 1.5,
  },
  emotionWrap: {
    marginTop: 4,
  },
  listenBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 4,
  },
  listenText: {
    fontSize: 12,
    color: Colors.primary,
  },
  time: {
    fontSize: 10,
    color: Colors.textTertiary,
    marginTop: 3,
  },
  timeUser: {
    textAlign: 'right',
  },
  timeAi: {
    textAlign: 'left',
  },
});
