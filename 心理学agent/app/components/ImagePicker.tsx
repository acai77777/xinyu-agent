/**
 * 图片选择器——从相册选择图片发送
 */
import React, { useCallback } from 'react';
import { TouchableOpacity, Alert, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ExpoImagePicker from 'expo-image-picker';
import { Colors } from '../constants/theme';

interface ImagePickerProps {
  onImageSelected: (uri: string) => void;
  disabled?: boolean;
}

export function ImagePicker({ onImageSelected, disabled }: ImagePickerProps) {
  const handlePress = useCallback(async () => {
    if (disabled) return;

    const { status } = await ExpoImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('权限不足', '需要相册权限才能选择图片');
      return;
    }

    const result = await ExpoImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.8,
      allowsEditing: false,
    });

    if (!result.canceled && result.assets[0]) {
      onImageSelected(result.assets[0].uri);
    }
  }, [disabled, onImageSelected]);

  return (
    <TouchableOpacity
      style={styles.btn}
      onPress={handlePress}
      activeOpacity={0.7}
      disabled={disabled}
    >
      <Ionicons name="image-outline" size={22} color={Colors.textSecondary} />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  btn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
