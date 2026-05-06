/**
 * 危机资源横幅——在危机抱持模式激活时显示
 * 提供温暖的陪伴提示 + 可展开的求助热线
 */
import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, Linking, StyleSheet, LayoutAnimation,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius } from '../constants/theme';

const HOTLINES = [
  { name: '全国24小时心理援助热线', number: '400-161-9995' },
  { name: '北京心理危机研究与干预中心', number: '010-82951332' },
  { name: '生命热线', number: '400-821-1215' },
];

interface CrisisBannerProps {
  visible: boolean;
}

export function CrisisBanner({ visible }: CrisisBannerProps) {
  const [expanded, setExpanded] = useState(false);

  if (!visible) return null;

  const toggleExpand = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpanded(!expanded);
  };

  const callHotline = (number: string) => {
    Linking.openURL(`tel:${number}`);
  };

  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.header} onPress={toggleExpand} activeOpacity={0.8}>
        <View style={styles.headerLeft}>
          <Ionicons name="heart" size={16} color="#fff" />
          <Text style={styles.headerText}>我在这里陪着你</Text>
        </View>
        <Ionicons
          name={expanded ? 'chevron-up' : 'chevron-down'}
          size={16}
          color="rgba(255,255,255,0.7)"
        />
      </TouchableOpacity>

      {expanded && (
        <View style={styles.body}>
          <Text style={styles.bodyText}>
            如果你需要专业支持，可以随时拨打以下热线：
          </Text>
          {HOTLINES.map((h) => (
            <TouchableOpacity
              key={h.number}
              style={styles.hotline}
              onPress={() => callHotline(h.number)}
              activeOpacity={0.7}
            >
              <View style={styles.hotlineInfo}>
                <Ionicons name="call-outline" size={14} color="#fff" />
                <Text style={styles.hotlineName}>{h.name}</Text>
              </View>
              <Text style={styles.hotlineNumber}>{h.number}</Text>
            </TouchableOpacity>
          ))}
          <Text style={styles.footer}>
            打完电话之后，如果你还想聊，我一直都在。
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: Colors.warm,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#fff',
  },
  body: {
    paddingHorizontal: 16,
    paddingBottom: 14,
  },
  bodyText: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.85)',
    lineHeight: 18,
    marginBottom: 10,
  },
  hotline: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: Radius.sm,
    paddingVertical: 10,
    paddingHorizontal: 12,
    marginBottom: 6,
  },
  hotlineInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flex: 1,
  },
  hotlineName: {
    fontSize: 13,
    color: '#fff',
    flex: 1,
  },
  hotlineNumber: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
    fontVariant: ['tabular-nums'],
  },
  footer: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.7)',
    marginTop: 6,
    textAlign: 'center',
  },
});
