/**
 * 音频录制与播放封装——基于 expo-av
 */
import { Audio } from 'expo-av';

let currentRecording: Audio.Recording | null = null;
let currentSound: Audio.Sound | null = null;

/**
 * 请求麦克风权限并开始录音
 * 返回 Recording 实例
 */
export async function startRecording(): Promise<Audio.Recording> {
  const { granted } = await Audio.requestPermissionsAsync();
  if (!granted) {
    throw new Error('未获得麦克风权限');
  }

  await Audio.setAudioModeAsync({
    allowsRecordingIOS: true,
    playsInSilentModeIOS: true,
  });

  const { recording } = await Audio.Recording.createAsync(
    Audio.RecordingOptionsPresets.HIGH_QUALITY,
  );
  currentRecording = recording;
  return recording;
}

/**
 * 停止录音并返回本地文件 URI
 */
export async function stopRecording(): Promise<string | null> {
  if (!currentRecording) return null;

  await currentRecording.stopAndUnloadAsync();
  await Audio.setAudioModeAsync({ allowsRecordingIOS: false });

  const uri = currentRecording.getURI();
  currentRecording = null;
  return uri;
}

/**
 * 获取当前录音时长（毫秒），用于 UI 计时器
 */
export async function getRecordingDuration(): Promise<number> {
  if (!currentRecording) return 0;
  const status = await currentRecording.getStatusAsync();
  return status.isRecording ? status.durationMillis : 0;
}

/**
 * 播放音频（用于播放 AI 语音回复）
 */
export async function playAudio(uri: string): Promise<void> {
  await stopPlayback();

  await Audio.setAudioModeAsync({
    allowsRecordingIOS: false,
    playsInSilentModeIOS: true,
  });

  const { sound } = await Audio.Sound.createAsync({ uri });
  currentSound = sound;
  await sound.playAsync();

  // 播放完毕后自动释放
  sound.setOnPlaybackStatusUpdate((status) => {
    if (status.isLoaded && status.didJustFinish) {
      sound.unloadAsync();
      currentSound = null;
    }
  });
}

/**
 * 停止当前播放
 */
export async function stopPlayback(): Promise<void> {
  if (currentSound) {
    await currentSound.stopAsync();
    await currentSound.unloadAsync();
    currentSound = null;
  }
}
