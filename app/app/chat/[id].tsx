import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  KeyboardAvoidingView, Platform, StyleSheet, Modal, Pressable,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes } from '../../constants/theme';
import { useChatStore, useMessages } from '../../stores/chatStore';
import {
  DEFAULT_MAIN_MODEL,
  MainModel,
  useWebSocket,
} from '../../services/websocket';
import { uploadAudio, uploadImage, API_BASE_URL, getToken } from '../../services/api';
import { ChatBubble } from '../../components/ChatBubble';
import { ThinkingDots } from '../../components/ThinkingDots';
import { VoiceRecorder } from '../../components/VoiceRecorder';
import { ImagePicker } from '../../components/ImagePicker';
import { CrisisBanner } from '../../components/CrisisBanner';
import { Message } from '../../types';

const MODEL_OPTIONS: Array<{
  id: MainModel;
  label: string;
  shortLabel: string;
  description: string;
}> = [
  {
    id: 'doubao-seed-2-0-mini-260428',
    label: 'Doubao Seed 2.0 Mini',
    shortLabel: 'Mini',
    description: '速度与质量均衡',
  },
  {
    id: 'doubao-seed-2-0-lite-260428',
    label: 'Doubao Seed 2.0 Lite',
    shortLabel: 'Lite',
    description: '更充分的回答',
  },
  {
    id: 'deepseek-v4-flash',
    label: 'DeepSeek V4 Flash',
    shortLabel: 'DeepSeek',
    description: '响应速度优先',
  },
];

const sessionModels = new Map<string, MainModel>();

export default function ChatScreen() {
  const { id: rawId } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(rawId === 'new' ? null : rawId!);
  const [mainModel, setMainModel] = useState<MainModel>(() => (
    rawId && rawId !== 'new'
      ? sessionModels.get(rawId) || DEFAULT_MAIN_MODEL
      : DEFAULT_MAIN_MODEL
  ));
  const [modelMenuVisible, setModelMenuVisible] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  const {
    isThinking, crisisHolding,
    addMessage, appendDeltaToLastAssistant, finalizeStreamingMessage,
    setThinking, setCrisisHolding, setSession, loadSessionMessages,
  } = useChatStore();
  const messages = useMessages();

  // 直接回调消费 ws 消息，绕开 useState 中转——
  // React 18 在 native handler 里也会合并 setState，高频 chunks 中间值会被吞。
  // zustand actions 引用稳定，放进 deps 不会反复重建 handler。
  const handleWsMessage = useCallback((msg: any) => {
    if (msg.type === 'status' && msg.content === 'thinking') {
      setThinking(true);
      return;
    }

    // 流字 chunk —— 累积到当前流式 assistant 消息
    if (msg.type === 'text_chunk') {
      setThinking(false);
      appendDeltaToLastAssistant(msg.content || '');
      return;
    }

    // 流字结束（未被改写） —— 用后端完整 content 覆盖累积
    // 后端 full_content 单调累加不受 stream_cb 异常影响，永远是完整版；
    // 优先用 content 兜底"末尾 chunk 因网络抖动/stream_cb 异常丢失"导致的末尾丢字。
    if (msg.type === 'text_done') {
      finalizeStreamingMessage(msg.content || null, msg.emotion?.primary);
      if (msg.crisis_holding !== undefined) {
        setCrisisHolding(!!msg.crisis_holding);
      }
      return;
    }

    // 流字结束（被审核改写） —— 用完整 content 替换累积内容
    if (msg.type === 'text_patch') {
      finalizeStreamingMessage(msg.content || '', msg.emotion?.primary);
      if (msg.crisis_holding !== undefined) {
        setCrisisHolding(!!msg.crisis_holding);
      }
      return;
    }

    // 老协议兜底（服务端回退到一次性发时不至于断）
    if (msg.type === 'text') {
      setThinking(false);
      addMessage({
        id: Date.now().toString(),
        role: 'assistant',
        type: 'text',
        content: msg.content || '',
        emotion: msg.emotion?.primary,
        audioUrl: msg.audio_url,
        timestamp: new Date(),
      });
      if (msg.crisis_holding !== undefined) {
        setCrisisHolding(!!msg.crisis_holding);
      }
      return;
    }

    if (msg.type === 'transcription') {
      addMessage({
        id: Date.now().toString(),
        role: 'user',
        type: 'voice',
        content: msg.content || '',
        timestamp: new Date(),
      });
      return;
    }

    if (msg.type === 'error') {
      setThinking(false);
      addMessage({
        id: Date.now().toString(),
        role: 'assistant',
        type: 'text',
        content: msg.content || '当前模型不可用，请重新选择。',
        timestamp: new Date(),
      });
    }
  }, [addMessage, appendDeltaToLastAssistant, finalizeStreamingMessage, setThinking, setCrisisHolding]);

  const { send, isConnected } = useWebSocket(sessionId || '', handleWsMessage, mainModel);

  useEffect(() => {
    if (!sessionId) return;
    setMainModel(sessionModels.get(sessionId) || DEFAULT_MAIN_MODEL);
  }, [sessionId]);

  const handleModelSelect = useCallback((model: MainModel) => {
    setMainModel(model);
    if (sessionId) sessionModels.set(sessionId, model);
    setModelMenuVisible(false);
  }, [sessionId]);

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

    let result;
    try {
      result = await uploadAudio(localUri);
    } catch (error) {
      console.error('[Voice] upload failed', error);
      addMessage({
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        type: 'text',
        content: '语音上传失败，请重试或直接打字告诉我。',
        timestamp: new Date(),
      });
      return;
    }

    try {
      send({ type: 'voice', audio_url: result.file_url, want_voice: true });
    } catch (error) {
      console.error('[Voice] send failed', error);
      addMessage({
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        type: 'text',
        content: '语音已上传，但发送到对话失败，请稍后重试。',
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

  const selectedModel = MODEL_OPTIONS.find((option) => option.id === mainModel)!;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* 危机抱持横幅 */}
      <CrisisBanner visible={crisisHolding} />

      {/* Nav Bar */}
      <View style={styles.navBar}>
        <TouchableOpacity
          style={styles.backBtn}
          onPress={() => router.back()}
          accessibilityRole="button"
          accessibilityLabel="返回"
        >
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
        <TouchableOpacity
          style={[styles.modelButton, (isThinking || !sessionId) && styles.modelButtonDisabled]}
          onPress={() => setModelMenuVisible(true)}
          disabled={isThinking || !sessionId}
          accessibilityRole="button"
          accessibilityLabel={`当前模型 ${selectedModel.label}`}
          accessibilityHint="打开主对话模型选择菜单"
        >
          <Ionicons name="hardware-chip-outline" size={16} color={Colors.primary} />
          <Text style={styles.modelButtonText} numberOfLines={1}>{selectedModel.shortLabel}</Text>
          <Ionicons name="chevron-down" size={14} color={Colors.textSecondary} />
        </TouchableOpacity>
      </View>

      <Modal
        visible={modelMenuVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setModelMenuVisible(false)}
      >
        <Pressable
          style={styles.modelOverlay}
          onPress={() => setModelMenuVisible(false)}
        >
          <Pressable
            style={styles.modelSheet}
            onPress={(event) => event.stopPropagation()}
            accessibilityViewIsModal
          >
            <View style={styles.modelSheetHeader}>
              <Text style={styles.modelSheetTitle}>选择主对话模型</Text>
              <TouchableOpacity
                style={styles.modelCloseButton}
                onPress={() => setModelMenuVisible(false)}
                accessibilityRole="button"
                accessibilityLabel="关闭"
              >
                <Ionicons name="close" size={22} color={Colors.textSecondary} />
              </TouchableOpacity>
            </View>
            {MODEL_OPTIONS.map((option) => {
              const selected = option.id === mainModel;
              return (
                <TouchableOpacity
                  key={option.id}
                  style={[styles.modelOption, selected && styles.modelOptionSelected]}
                  onPress={() => handleModelSelect(option.id)}
                  accessibilityRole="radio"
                  accessibilityState={{ selected }}
                  accessibilityLabel={`${option.label}，${option.description}`}
                >
                  <View style={styles.modelOptionText}>
                    <Text style={styles.modelOptionLabel}>{option.label}</Text>
                    <Text style={styles.modelOptionDescription}>{option.description}</Text>
                  </View>
                  {selected && (
                    <Ionicons name="checkmark-circle" size={22} color={Colors.primary} />
                  )}
                </TouchableOpacity>
              );
            })}
          </Pressable>
        </Pressable>
      </Modal>

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
    paddingHorizontal: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 0.5,
    borderBottomColor: Colors.border,
    backgroundColor: Colors.bgPhone,
  },
  backBtn: {
    width: 88,
    minHeight: 44,
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
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
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
  modelButton: {
    width: 88,
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 4,
  },
  modelButtonDisabled: {
    opacity: 0.45,
  },
  modelButtonText: {
    maxWidth: 48,
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: Colors.primary,
  },
  modelOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    padding: 16,
    backgroundColor: 'rgba(29, 29, 31, 0.48)',
  },
  modelSheet: {
    width: '100%',
    maxWidth: 420,
    alignSelf: 'center',
    overflow: 'hidden',
    borderRadius: 8,
    backgroundColor: Colors.bgCard,
  },
  modelSheetHeader: {
    minHeight: 56,
    paddingLeft: 16,
    paddingRight: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  modelSheetTitle: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: Colors.text,
  },
  modelCloseButton: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modelOption: {
    minHeight: 68,
    paddingHorizontal: 16,
    paddingVertical: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  modelOptionSelected: {
    backgroundColor: Colors.primaryLight,
  },
  modelOptionText: {
    flex: 1,
    gap: 3,
  },
  modelOptionLabel: {
    fontSize: FontSizes.body,
    fontWeight: '600',
    color: Colors.text,
  },
  modelOptionDescription: {
    fontSize: FontSizes.sm,
    color: Colors.textSecondary,
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
