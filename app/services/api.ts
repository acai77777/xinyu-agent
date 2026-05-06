/**
 * REST API 客户端——认证 + 业务接口
 */

export const API_BASE_URL = 'https://xinyu.acai777.cn';

// === Token 管理（支持 Remember Me + 自动过期） ===

const TOKEN_KEY = 'auth_token';
const EXPIRES_KEY = 'token_expires_at';
const USER_KEY = 'user_info';
const REMEMBER_EXPIRY_MS = 7 * 24 * 60 * 60 * 1000;   // 7 天
const SESSION_EXPIRY_MS = 24 * 60 * 60 * 1000;          // 24 小时

let _token: string | null = null;

function hasWindow(): boolean {
  return typeof window !== 'undefined' && !!window.localStorage;
}

/** 检查 token 是否已过期，过期则自动清除 */
function isTokenExpired(): boolean {
  if (!hasWindow()) return false;
  const expiresAt = localStorage.getItem(EXPIRES_KEY) || sessionStorage.getItem(EXPIRES_KEY);
  if (!expiresAt) return false;
  if (Date.now() > Number(expiresAt)) {
    clearToken();
    return true;
  }
  return false;
}

export function getToken(): string | null {
  if (_token && !isTokenExpired()) return _token;
  if (isTokenExpired()) return null;
  if (hasWindow()) {
    _token = localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
  }
  return _token;
}

export function setToken(token: string, rememberMe: boolean = true) {
  _token = token;
  if (!hasWindow()) return;
  const expiresAt = String(Date.now() + (rememberMe ? REMEMBER_EXPIRY_MS : SESSION_EXPIRY_MS));
  if (rememberMe) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(EXPIRES_KEY, expiresAt);
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(EXPIRES_KEY);
  } else {
    sessionStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(EXPIRES_KEY, expiresAt);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EXPIRES_KEY);
  }
}

export function clearToken() {
  _token = null;
  if (!hasWindow()) return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EXPIRES_KEY);
  localStorage.removeItem(USER_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(EXPIRES_KEY);
  sessionStorage.removeItem(USER_KEY);
}

export function getUserInfo(): { user_id: string; display_name: string } | null {
  if (!hasWindow()) return null;
  const raw = localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY);
  if (raw) {
    try { return JSON.parse(raw); } catch { return null; }
  }
  return null;
}

export function setUserInfo(info: { user_id: string; display_name: string }, rememberMe: boolean = true) {
  if (!hasWindow()) return;
  const val = JSON.stringify(info);
  if (rememberMe) {
    localStorage.setItem(USER_KEY, val);
    sessionStorage.removeItem(USER_KEY);
  } else {
    sessionStorage.setItem(USER_KEY, val);
    localStorage.removeItem(USER_KEY);
  }
}

function getAuthHeaders(): Record<string, string> {
  const token = getToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

// === 认证 API ===

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  display_name: string;
}

export async function register(username: string, password: string, displayName?: string, rememberMe: boolean = true): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, display_name: displayName || '' }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '注册失败' }));
    throw new Error(err.detail || '注册失败');
  }
  const data: AuthResponse = await res.json();
  setToken(data.access_token, rememberMe);
  setUserInfo({ user_id: data.user_id, display_name: data.display_name }, rememberMe);
  return data;
}

export async function login(username: string, password: string, rememberMe: boolean = true): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '登录失败' }));
    throw new Error(err.detail || '登录失败');
  }
  const data: AuthResponse = await res.json();
  setToken(data.access_token, rememberMe);
  setUserInfo({ user_id: data.user_id, display_name: data.display_name }, rememberMe);
  return data;
}

export function logout() {
  clearToken();
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

// === 通用类型 ===

interface UploadResult {
  file_url: string;
  file_id: string;
}

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

// === 文件上传 ===

export async function uploadAudio(uri: string): Promise<UploadResult> {
  const form = new FormData();
  form.append('file', {
    uri,
    name: 'audio.m4a',
    type: 'audio/m4a',
  } as any);

  const res = await fetch(`${API_BASE_URL}/upload/audio`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: form,
  });

  if (!res.ok) {
    throw new Error(`上传音频失败: ${res.status}`);
  }
  return res.json();
}

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
    headers: getAuthHeaders(),
    body: form,
  });

  if (!res.ok) {
    throw new Error(`上传图片失败: ${res.status}`);
  }
  return res.json();
}
