import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet, Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius, Shadows, FontSizes } from '../constants/theme';
import { TREND_DATA } from '../constants/mockData';

export default function ProfileScreen() {
  const [settings, setSettings] = useState({
    notification: true,
    voiceReply: false,
    autoSave: true,
  });

  const toggle = (key: keyof typeof settings) => {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.navBar}>
        <View />
        <Text style={styles.navTitle}>我的</Text>
        <View />
      </View>
      <ScrollView style={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Profile Header */}
        <View style={styles.profileHeader}>
          <View style={styles.avatar}>
            <Text style={styles.avatarEmoji}>🙂</Text>
          </View>
          <Text style={styles.name}>MAOMAO</Text>
          <Text style={styles.subtitle}>已陪伴 12 天</Text>
        </View>

        {/* Mood Trend */}
        <View style={[styles.trendCard, Shadows.sm]}>
          <Text style={styles.trendTitle}>本周情绪趋势</Text>
          <View style={styles.trendChart}>
            {TREND_DATA.map((d) => (
              <View key={d.day} style={styles.trendBarGroup}>
                <View
                  style={[
                    styles.trendBar,
                    {
                      height: `${d.value}%`,
                      backgroundColor: d.color,
                      opacity: 0.75,
                    },
                  ]}
                />
                <Text style={styles.trendLabel}>{d.day}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* Settings */}
        <View style={styles.settingsSection}>
          <Text style={styles.groupTitle}>偏好设置</Text>

          <SettingToggle
            icon="🔔" iconBg="#E8F2F8" iconColor="#3A7CA5"
            label="消息通知" value={settings.notification}
            onToggle={() => toggle('notification')}
          />
          <SettingToggle
            icon="🎙️" iconBg="#F0E8F5" iconColor="#7B61A8"
            label="语音回复" value={settings.voiceReply}
            onToggle={() => toggle('voiceReply')}
          />
          <SettingToggle
            icon="💾" iconBg="#EBF5EC" iconColor="#4CAF50"
            label="自动保存对话" value={settings.autoSave}
            onToggle={() => toggle('autoSave')}
          />

          <Text style={styles.groupTitle}>关于</Text>

          <SettingLink icon="📋" iconBg="#FFF5E8" label="隐私政策" />
          <SettingLink icon="🗑️" iconBg="#FCE4EC" label="清除所有数据" />

          <View style={styles.settingItem}>
            <View style={styles.settingLeft}>
              <View style={[styles.settingIcon, { backgroundColor: '#F5F5F5' }]}>
                <Text>ℹ️</Text>
              </View>
              <Text style={styles.settingLabel}>版本</Text>
            </View>
            <Text style={styles.settingValue}>v0.1.0</Text>
          </View>
        </View>

        <View style={{ height: 20 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function SettingToggle({ icon, iconBg, iconColor, label, value, onToggle }: {
  icon: string; iconBg: string; iconColor?: string;
  label: string; value: boolean; onToggle: () => void;
}) {
  return (
    <View style={styles.settingItem}>
      <View style={styles.settingLeft}>
        <View style={[styles.settingIcon, { backgroundColor: iconBg }]}>
          <Text>{icon}</Text>
        </View>
        <Text style={styles.settingLabel}>{label}</Text>
      </View>
      <Switch
        value={value}
        onValueChange={onToggle}
        trackColor={{ false: Colors.border, true: Colors.success }}
        thumbColor="#fff"
      />
    </View>
  );
}

function SettingLink({ icon, iconBg, label }: {
  icon: string; iconBg: string; label: string;
}) {
  return (
    <TouchableOpacity style={styles.settingItem} activeOpacity={0.7}>
      <View style={styles.settingLeft}>
        <View style={[styles.settingIcon, { backgroundColor: iconBg }]}>
          <Text>{icon}</Text>
        </View>
        <Text style={styles.settingLabel}>{label}</Text>
      </View>
      <Ionicons name="chevron-forward" size={14} color={Colors.textTertiary} />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bgPhone },
  navBar: {
    height: 52, paddingHorizontal: 20,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    borderBottomWidth: 0.5, borderBottomColor: Colors.border,
  },
  navTitle: { fontSize: FontSizes.lg, fontWeight: '600', color: Colors.text },
  scroll: { flex: 1 },
  profileHeader: {
    alignItems: 'center', paddingVertical: 24, paddingHorizontal: 20,
  },
  avatar: {
    width: 80, height: 80, borderRadius: 40,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#E8F2F8',
    ...Shadows.md,
  },
  avatarEmoji: { fontSize: 36 },
  name: {
    fontSize: FontSizes.xxl, fontWeight: '600', color: Colors.text,
    marginTop: 12, letterSpacing: -0.3,
  },
  subtitle: { fontSize: 14, color: Colors.textSecondary, marginTop: 2 },
  trendCard: {
    marginHorizontal: 20, padding: 18,
    borderRadius: Radius.lg, backgroundColor: Colors.bgCard,
  },
  trendTitle: {
    fontSize: 13, color: Colors.textSecondary, fontWeight: '500', marginBottom: 14,
  },
  trendChart: {
    height: 100, flexDirection: 'row', alignItems: 'flex-end', gap: 6, paddingHorizontal: 4,
  },
  trendBarGroup: {
    flex: 1, alignItems: 'center', gap: 4, height: '100%', justifyContent: 'flex-end',
  },
  trendBar: {
    width: '100%', borderTopLeftRadius: 6, borderTopRightRadius: 6,
    borderBottomLeftRadius: 2, borderBottomRightRadius: 2, minHeight: 8,
  },
  trendLabel: { fontSize: FontSizes.xs, color: Colors.textTertiary },
  settingsSection: { paddingHorizontal: 20, paddingTop: 8 },
  groupTitle: {
    fontSize: 13, fontWeight: '600', color: Colors.textSecondary,
    paddingTop: 12, paddingBottom: 6,
  },
  settingItem: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    padding: 14, paddingHorizontal: 16,
    backgroundColor: Colors.bgCard, borderRadius: Radius.md, marginBottom: 6,
  },
  settingLeft: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  settingIcon: {
    width: 32, height: 32, borderRadius: 8,
    alignItems: 'center', justifyContent: 'center',
  },
  settingLabel: { fontSize: FontSizes.body, color: Colors.text },
  settingValue: { fontSize: 14, color: Colors.textSecondary },
});
