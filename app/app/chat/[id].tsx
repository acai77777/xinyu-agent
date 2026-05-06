import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  KeyboardAvoidingView, Platform, StyleSheet,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes } from '../../constants/theme';
import { useChatStore, useMessages } from '../../stores/chatStore';
import { useWebSocket } from '../../services/websocket';
import { uploadAudio, uploadImage, API_BASE_URL, getToken } from '../../services/api';
import { ChatBubble } from '../../components/ChatBubble';
import { ThinkingDots } from '../../components/ThinkingDots';
import { VoiceRecorder } from '../../components/VoiceRecorder';
import { ImagePicker } from '../../components/ImagePicker';
import { CrisisBanner } from '../../components/CrisisBanner';
import { Message } from '../../types';

export default function ChatScreen() {
  const { id: rawId } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(rawId === 'new' ? null : rawId!);
  const flatListRef = useRef<FlatList>(null);

  const {
    isThinking, crisisHolding,
    addMessage, setThinking, setCrisisHolding, setSession, loadSessionMessages,
  } = useChatStore();
  const messages = useMessages();
  const { send, lastMessage, isConnected } = useWebSocket(sessionId || '');

  // 创建新会话或加载已有会话
  useEffect(() => {
    if (rawId === 'new') {
      // 创建新会话
      const token = getToken();
      fetch(`${API_BASE_URL}/api/history/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ title: '' }),
      })
        .then((res) => res.json())
        .then((data) => {
          const newId = data.session_id;
          setSessionId(newId);
          setSession(newId);
          // 替换路由，避免返回时再次触发 new
          router.replace(`/chat/${newId}`);
        })
        .catch(() => {
          // 创建失败，用临时 ID
          const tempId = `local-${Date.now()}`;
          setSessionId(tempId);
          setSession(tempId);
        });
    } else if (rawId) {
      setSession(rawId);
      loadSessionMessages(rawId);
    }
  }, [rawId]);

  // 处理服务端 WebSocket 消息
  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === 'status' && lastMessage.content === 'thinking') {
      setThinking(true);
      return;
    }

    if (lastMessage.type === 'text') {
      setThinking(false);

      const aiMsg: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        type: 'text',
        content: lastMessage.content || '',
        emotion: lastMessage.emotion?.primary,
        audioUrl: lastMessage.audio_url,
        timestamp: new Date(),
      };
      addMessage(aiMsg);

      if (lastMessage.crisis_holding !== undefined) {
        setCrisisHolding(!!lastMessage.crisis_holding);
      }
    }

    if (lastMessage.type === 'transcription') {
      addMessage({
        id: Date.now().toString(),
        role: 'user',
        type: 'voice',
        content: lastMessage.content || '',
        timestamp: new Date(),
      });
    }
  }, [lastMessage]);

  // 发送文字消息
  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || isThinking) return;

    addMessage({
      id: Date.now().toString(),
      role: 'user',
      type: 'text',
      content: text,
      timestamp: new Date(),
    });
    setInput('');

    if (isConnected) {
      send({ type: 'text', content: text });
    } else {
      setTimeout(() => {
        addMessage({
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          type: 'text',
          content: '当前网络未连接，请稍后重试。你的消息我会记住的。',
          timestamp: new Date(),
        });
      }, 500);
    }
  }, [input, isThinking, isConnected, addMessage, send]);

  // 发送语音消息
  const handleVoiceSend = useCallback(async (localUri: string) => {
    addMessage({
      id: Date.now().toString(),
      role: 'user',
      type: 'voice',
      content: '🎙️ 语音消息',
      audioUrl: localUri,
      timestamp: new Date(),
    });

    try {
      const result = await uploadAudio(localUri);
      send({ type: 'voice', audio_url: result.file_url, want_voice: true });
    } catch {
      addMessage({
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        type: 'text',
        content: '语音上传失败，请重试或直接打字告诉我。',
        timestamp: new Date(),
      });
    }
  }, [addMessage, send]);

  // 发送图片消息
  const handleImageSend = useCallback(async (localUri: string) => {
    addMessage({
      id: Date.now().toString(),
      role: 'user',
      type: 'image',
      content: '',
      imageUri: localUri,
      timestamp: new Date(),
    });

    try {
      const result = await uploadImage(localUri);
      send({ type: 'image', image_url: result.file_url, content: '' });
    } catch {
      addMessage({
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        type: 'text',
        content: '图片上传失败，请重试。',
        timestamp: new Date(),
      });
    }
  }, [addMessage, send]);

  const renderItem = useCallback(({ item }: { item: Message }) => (
    <ChatBubble message={item} />
  ), []);

  const renderFooter = useCallback(() => {
    if (!isThinking) return null;
    return <ThinkingDots />;
  }, [isThinking]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* 危机抱持横幅 */}
      <CrisisBanner visible={crisisHolding} />

      {/* Nav Bar */}
      <View style={styles.navBar}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={22} color={Colors.primary} />
          <Text style={styles.backText}>返回</Text>
        </TouchableOpacity>
        <View style={styles.chatNav}>
          <View style={styles.chatAvatarSmall}>
            <Text style={{ fontSize: 16 }}>🌿</Text>
          </View>
          <View>
            <Text style={styles.chatNavName}>心语</Text>
            <Text style={[styles.chatNavStatus, !isConnected && styles.offline]}>
              {isConnected ? '● 在线' : '○ 离线'}
            </Text>
          </View>
        </View>
        <View style={{ width: 60 }} />
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={0}
      >
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          ListFooterComponent={renderFooter}
          onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
          contentContainerStyle={styles.messageList}
          showsVerticalScrollIndicator={false}
        />

        {/* Input Bar */}
        <View style={styles.inputBar}>
          <ImagePicker onImageSelected={handleImageSend} disabled={isThinking} />
          <View style={styles.inputWrapper}>
            <TextInput
              style={styles.textInput}
              value={input}
              onChangeText={setInput}
              placeholder="说说你的感受..."
              placeholderTextColor={Colors.textTertiary}
              multiline
              maxLength={2000}
              onSubmitEditing={handleSend}
              blurOnSubmit={false}
            />
          </View>
          {input.trim() ? (
            <TouchableOpacity style={styles.sendBtn} onPress={handleSend}>
              <Ionicons name="send" size={18} color="#fff" />
            </TouchableOpacity>
          ) : (
            <VoiceRecorder onRecordComplete={handleVoiceSend} disabled={isThinking} />
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bgPhone },
  flex: { flex: 1 },
  navBar: {
    height: 52,
    paddingHorizontal: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 0.5,
    borderBottomColor: Colors.border,
    backgroundColor: Colors.bgPhone,
  },
  backBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    padding: 6,
  },
  backText: {
    fontSize: FontSizes.md,
    color: Colors.primary,
  },
  chatNav: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  chatAvatarSmall: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: '#E8F2F8',
    alignItems: 'center',
    justifyContent: 'center',
  },
  chatNavName: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: Colors.text,
  },
  chatNavStatus: {
    fontSize: 11,
    color: Colors.success,
  },
  offline: {
    color: Colors.textTertiary,
  },
  messageList: {
    padding: 16,
    paddingBottom: 8,
  },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: 28,
    backgroundColor: Colors.bgCard,
    borderTopWidth: 0.5,
    borderTopColor: Colors.border,
  },
  inputWrapper: {
    flex: 1,
    backgroundColor: Colors.bgInput,
    borderRadius: 22,
    paddingHorizontal: 14,
    paddingVertical: 8,
    justifyContent: 'center',
  },
  textInput: {
    fontSize: FontSizes.body,
    color: Colors.text,
    maxHeight: 80,
    lineHeight: 21,
  },
  sendBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
