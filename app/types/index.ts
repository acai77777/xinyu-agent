export interface Message {
  id: string;
  role: 'user' | 'assistant';
  type: 'text' | 'voice' | 'image' | 'exercise';
  content: string;
  emotion?: string;
  audioUrl?: string;
  imageUri?: string;
  exercise?: ExerciseData;
  timestamp: Date;
}

export interface ExerciseData {
  exerciseType: string;
  name: string;
  instruction: string;
  totalSteps?: number;
  followUpPrompts?: string[];
}

export interface Session {
  id: string;
  name: string;
  preview: string;
  time: string;
  unread: number;
  emoji: string;
  bg: string;
}

export interface HistoryItem {
  id: string;
  title: string;
  summary: string;
  emotions: string[];
  color: string;
}

export interface HistoryGroup {
  [group: string]: HistoryItem[];
}

export type MoodKey = 'great' | 'ok' | 'low' | 'anxious' | 'angry';

export interface Mood {
  key: MoodKey;
  emoji: string;
  label: string;
}

export interface TrendDataPoint {
  day: string;
  value: number;
  color: string;
}

export interface EmotionColor {
  bg: string;
  color: string;
}
