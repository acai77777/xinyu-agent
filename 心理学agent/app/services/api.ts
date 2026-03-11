/**
 * REST API 客户端——用于文件上传等非实时操作
 */

export const API_BASE_URL = 'https://shiny-worldly-carrol.ngrok-free.dev';

interface UploadResult {
  file_url: string;
  file_id: string;
}

// === 心情打卡相关类型 ===

export interface MoodCheckin {
  id: number;
  score: number;
  note: string;
  created_at: string;
}

export interface MoodStats {
  avg_score: number | null;
  max_score: number | null;
  min_score: number | null;
  count: number;
  trend: 'up' | 'down' | 'stable';
}

/** 获取存储的 token（需在 app 中实现实际存取逻辑） */
function getAuthHeaders(): Record<string, string> {
  // TODO: 从 SecureStore / AsyncStorage 获取 token
  return {};
}

// === 心情打卡 API ===

export async function moodCheckin(score: number, note: string = ''): Promise<MoodCheckin> {
  const res = await fetch(`${API_BASE_URL}/api/mood/checkin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({ score, note }),
  });
  if (!res.ok) throw new Error(`打卡失败: ${res.status}`);
  return res.json();
}

export async function getMoodToday(): Promise<MoodCheckin | null> {
  const res = await fetch(`${API_BASE_URL}/api/mood/today`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`获取今日打卡失败: ${res.status}`);
  const data = await res.json();
  return data.checkin;
}

export async function getMoodHistory(days: number = 30): Promise<MoodCheckin[]> {
  const res = await fetch(`${API_BASE_URL}/api/mood/history?days=${days}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`获取历史失败: ${res.status}`);
  const data = await res.json();
  return data.records;
}

export async function getMoodStats(days: number = 30): Promise<MoodStats> {
  const res = await fetch(`${API_BASE_URL}/api/mood/stats?days=${days}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`获取统计失败: ${res.status}`);
  return res.json();
}

/**
 * 上传音频文件到后端
 */
export async function uploadAudio(uri: string): Promise<UploadResult> {
  const form = new FormData();
  form.append('file', {
    uri,
    name: 'audio.m4a',
    type: 'audio/m4a',
  } as any);

  const res = await fetch(`${API_BASE_URL}/upload/audio`, {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    throw new Error(`上传音频失败: ${res.status}`);
  }
  return res.json();
}

/**
 * 上传图片文件到后端
 */
export async function uploadImage(uri: string): Promise<UploadResult> {
  const ext = uri.split('.').pop() || 'jpg';
  const form = new FormData();
  form.append('file', {
    uri,
    name: `image.${ext}`,
    type: `image/${ext === 'jpg' ? 'jpeg' : ext}`,
  } as any);

  const res = await fetch(`${API_BASE_URL}/upload/image`, {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    throw new Error(`上传图片失败: ${res.status}`);
  }
  return res.json();
}
