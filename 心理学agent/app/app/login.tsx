import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert,
  ScrollView,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius, Shadows, FontSizes } from '../constants/theme';
import { login, register } from '../services/api';

export default function LoginScreen() {
  const router = useRouter();
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [secureEntry, setSecureEntry] = useState(true);
  const [secureEntryConfirm, setSecureEntryConfirm] = useState(true);
  const [rememberMe, setRememberMe] = useState(true);

  const handleSubmit = async () => {
    setError('');
    if (!username.trim() || !password.trim()) {
      setError('请填写用户名和密码');
      return;
    }
    if (isRegister && password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    if (isRegister && password.length < 6) {
      setError('密码至少需要 6 个字符');
      return;
    }

    setLoading(true);
    try {
      if (isRegister) {
        await register(username.trim(), password, displayName.trim() || undefined, rememberMe);
      } else {
        await login(username.trim(), password, rememberMe);
      }
      router.replace('/');
    } catch (e: any) {
      setError(e.message || '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = () => {
    Alert.alert('忘记密码', '请联系管理员重置密码。', [{ text: '好的' }]);
  };

  const switchMode = () => {
    setIsRegister(!isRegister);
    setError('');
    setConfirmPassword('');
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {/* 品牌区域 */}
          <View style={styles.brandArea}>
            <View style={styles.logoContainer}>
              <Ionicons name="leaf" size={36} color={Colors.primary} />
            </View>
            <Text style={styles.brandTitle}>心语</Text>
            <Text style={styles.brandSubtitle}>AI 心理健康助手</Text>
          </View>

          {/* 表单卡片 */}
          <View style={[styles.formCard, Shadows.md]}>
            <Text style={styles.formTitle}>
              {isRegister ? '创建账号' : '欢迎回来'}
            </Text>
            <Text style={styles.formSubtitle}>
              {isRegister ? '注册后即可开始心理健康之旅' : '登录以继续使用心语'}
            </Text>

            {/* 用户名 */}
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>用户名</Text>
              <View style={styles.inputWrapper}>
                <Ionicons name="person-outline" size={18} color={Colors.textTertiary} style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  value={username}
                  onChangeText={setUsername}
                  placeholder="请输入用户名"
                  placeholderTextColor={Colors.textTertiary}
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </View>
            </View>

            {/* 昵称（注册时） */}
            {isRegister && (
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>昵称（选填）</Text>
                <View style={styles.inputWrapper}>
                  <Ionicons name="happy-outline" size={18} color={Colors.textTertiary} style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    value={displayName}
                    onChangeText={setDisplayName}
                    placeholder="给自己取个名字"
                    placeholderTextColor={Colors.textTertiary}
                  />
                </View>
              </View>
            )}

            {/* 密码 */}
            <View style={styles.inputGroup}>
              <View style={styles.labelRow}>
                <Text style={styles.inputLabel}>密码</Text>
                {!isRegister && (
                  <TouchableOpacity onPress={handleForgotPassword} activeOpacity={0.6}>
                    <Text style={styles.forgotText}>忘记密码？</Text>
                  </TouchableOpacity>
                )}
              </View>
              <View style={styles.inputWrapper}>
                <Ionicons name="lock-closed-outline" size={18} color={Colors.textTertiary} style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  value={password}
                  onChangeText={setPassword}
                  placeholder={isRegister ? '至少 6 个字符' : '请输入密码'}
                  placeholderTextColor={Colors.textTertiary}
                  secureTextEntry={secureEntry}
                />
                <TouchableOpacity
                  onPress={() => setSecureEntry(!secureEntry)}
                  style={styles.eyeBtn}
                  activeOpacity={0.6}
                >
                  <Ionicons
                    name={secureEntry ? 'eye-off-outline' : 'eye-outline'}
                    size={18}
                    color={Colors.textTertiary}
                  />
                </TouchableOpacity>
              </View>
            </View>

            {/* 确认密码（注册时） */}
            {isRegister && (
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>确认密码</Text>
                <View style={styles.inputWrapper}>
                  <Ionicons name="lock-closed-outline" size={18} color={Colors.textTertiary} style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    value={confirmPassword}
                    onChangeText={setConfirmPassword}
                    placeholder="请再次输入密码"
                    placeholderTextColor={Colors.textTertiary}
                    secureTextEntry={secureEntryConfirm}
                  />
                  <TouchableOpacity
                    onPress={() => setSecureEntryConfirm(!secureEntryConfirm)}
                    style={styles.eyeBtn}
                    activeOpacity={0.6}
                  >
                    <Ionicons
                      name={secureEntryConfirm ? 'eye-off-outline' : 'eye-outline'}
                      size={18}
                      color={Colors.textTertiary}
                    />
                  </TouchableOpacity>
                </View>
              </View>
            )}

            {/* 记住我 */}
            <TouchableOpacity
              style={styles.rememberRow}
              onPress={() => setRememberMe(!rememberMe)}
              activeOpacity={0.6}
            >
              <View style={[styles.checkbox, rememberMe && styles.checkboxChecked]}>
                {rememberMe && (
                  <Ionicons name="checkmark" size={14} color="#fff" />
                )}
              </View>
              <Text style={styles.rememberText}>记住我</Text>
              <Text style={styles.rememberHint}>
                {rememberMe ? '7 天内免登录' : '关闭浏览器后需重新登录'}
              </Text>
            </TouchableOpacity>

            {/* 错误提示 */}
            {error ? (
              <View style={styles.errorRow}>
                <Ionicons name="alert-circle" size={16} color={Colors.danger} />
                <Text style={styles.errorText}>{error}</Text>
              </View>
            ) : null}

            {/* 提交按钮 */}
            <TouchableOpacity
              style={[styles.submitBtn, loading && styles.submitBtnDisabled]}
              onPress={handleSubmit}
              disabled={loading}
              activeOpacity={0.8}
            >
              {loading ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.submitText}>
                  {isRegister ? '注册' : '登录'}
                </Text>
              )}
            </TouchableOpacity>
          </View>

          {/* 底部切换 */}
          <View style={styles.switchRow}>
            <Text style={styles.switchHint}>
              {isRegister ? '已有账号？' : '没有账号？'}
            </Text>
            <TouchableOpacity onPress={switchMode} activeOpacity={0.6}>
              <Text style={styles.switchLink}>
                {isRegister ? '去登录' : '去注册'}
              </Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.bgPhone,
  },
  flex: { flex: 1 },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
    paddingVertical: 40,
  },

  /* 品牌区域 */
  brandArea: {
    alignItems: 'center',
    marginBottom: 32,
  },
  logoContainer: {
    width: 64,
    height: 64,
    borderRadius: 20,
    backgroundColor: Colors.primaryLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  brandTitle: {
    fontSize: 32,
    fontWeight: '700',
    color: Colors.text,
    letterSpacing: 1,
  },
  brandSubtitle: {
    fontSize: FontSizes.body,
    color: Colors.textSecondary,
    marginTop: 6,
  },

  /* 表单卡片 */
  formCard: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.lg,
    paddingHorizontal: 24,
    paddingTop: 28,
    paddingBottom: 24,
  },
  formTitle: {
    fontSize: FontSizes.xxl,
    fontWeight: '700',
    color: Colors.text,
    marginBottom: 4,
  },
  formSubtitle: {
    fontSize: FontSizes.sm,
    color: Colors.textSecondary,
    marginBottom: 24,
  },

  /* 输入框 */
  inputGroup: {
    marginBottom: 18,
  },
  labelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.textSecondary,
    marginBottom: 8,
  },
  forgotText: {
    fontSize: 13,
    color: Colors.primary,
    fontWeight: '500',
    marginBottom: 8,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.bgInput,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  inputIcon: {
    marginLeft: 14,
  },
  input: {
    flex: 1,
    paddingHorizontal: 10,
    paddingVertical: 14,
    fontSize: FontSizes.body,
    color: Colors.text,
  },
  eyeBtn: {
    paddingHorizontal: 14,
    paddingVertical: 14,
  },

  /* 记住我 */
  rememberRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 18,
    gap: 8,
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.bgInput,
  },
  checkboxChecked: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary,
  },
  rememberText: {
    fontSize: FontSizes.body,
    color: Colors.text,
    fontWeight: '500',
  },
  rememberHint: {
    flex: 1,
    fontSize: FontSizes.sm,
    color: Colors.textTertiary,
    textAlign: 'right',
  },

  /* 错误提示 */
  errorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 14,
  },
  errorText: {
    color: Colors.danger,
    fontSize: 13,
    flex: 1,
  },

  /* 提交按钮 */
  submitBtn: {
    backgroundColor: Colors.primary,
    borderRadius: Radius.md,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 4,
  },
  submitBtnDisabled: {
    opacity: 0.6,
  },
  submitText: {
    color: '#fff',
    fontSize: FontSizes.lg,
    fontWeight: '600',
  },

  /* 底部切换 */
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 24,
    gap: 4,
  },
  switchHint: {
    fontSize: FontSizes.body,
    color: Colors.textSecondary,
  },
  switchLink: {
    fontSize: FontSizes.body,
    color: Colors.primary,
    fontWeight: '600',
  },
});
