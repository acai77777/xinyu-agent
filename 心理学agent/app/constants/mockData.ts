import { Session, HistoryGroup, Message, Mood, TrendDataPoint, EmotionColor } from '../types';

export const MOODS: Mood[] = [
  { key: 'great', emoji: '😊', label: '很好' },
  { key: 'ok', emoji: '😐', label: '一般' },
  { key: 'low', emoji: '😔', label: '低落' },
  { key: 'anxious', emoji: '😰', label: '焦虑' },
  { key: 'angry', emoji: '😤', label: '烦躁' },
];

export const MOCK_SESSIONS: Session[] = [
  { id: '1', name: '今天的对话', preview: '我觉得今天工作压力好大...', time: '14:32', unread: 2, emoji: '🌿', bg: '#E8F2F8' },
  { id: '2', name: '昨天的倾诉', preview: '谢谢你的陪伴，我感觉好多了', time: '昨天', unread: 0, emoji: '🌸', bg: '#F5EBF0' },
  { id: '3', name: '周末的思考', preview: '关于和朋友的关系，我想了很久...', time: '周六', unread: 0, emoji: '🍃', bg: '#EBF5EC' },
  { id: '4', name: '感恩日记', preview: '今天完成了三件感恩的事', time: '3/1', unread: 0, emoji: '✨', bg: '#FFF5E8' },
];

export const MOCK_HISTORY: HistoryGroup = {
  '今天': [
    { id: 'h1', title: '工作压力倾诉', summary: '讨论了项目截止日期带来的焦虑感', emotions: ['焦虑', '疲惫'], color: '#F5A623' },
  ],
  '本周': [
    { id: 'h2', title: '人际关系探索', summary: '探讨了与同事沟通中的困扰', emotions: ['困惑', '期待'], color: '#8B9DC3' },
    { id: 'h3', title: '正念呼吸练习', summary: '完成了10分钟正念呼吸引导', emotions: ['平静'], color: '#6BBF8A' },
  ],
  '更早': [
    { id: 'h4', title: '感恩日记回顾', summary: '回顾了一周的三件感恩之事', emotions: ['感恩', '温暖'], color: '#C4A882' },
    { id: 'h5', title: '认知重构练习', summary: '用七栏法分析了一个消极想法', emotions: ['领悟'], color: '#3A7CA5' },
    { id: 'h6', title: '情绪低落时的陪伴', summary: '在难过的夜晚进行了一次深度对话', emotions: ['悲伤', '被理解'], color: '#E57373' },
  ],
};

export const AI_REPLIES = [
  '我听到你了。能和我多说说是什么让你有这样的感受吗？',
  '谢谢你愿意和我分享这些。你的感受是完全可以理解的。',
  '听起来你最近承受了不少压力。在这种时候，照顾好自己的感受很重要。',
  '我注意到你提到了这一点。你觉得是什么让你特别在意这件事呢？',
  '你已经做得很好了。有时候，允许自己休息一下也是一种力量。',
  '这种感受一定不容易。你愿意试试一个简单的放松练习吗？',
];

export const INITIAL_MESSAGES: Message[] = [
  { id: '1', role: 'assistant', type: 'text', content: '你好呀 👋 我是你的心理支持助手，可以陪你聊聊心情、帮你分析情绪背后的想法、提供专业的心理学知识（积极心理学、认知行为疗法等），还能做简单的心理评估和放松练习。今天过得怎么样？', timestamp: new Date() },
  { id: '2', role: 'user', type: 'text', content: '今天工作压力好大，感觉喘不过气来...', timestamp: new Date() },
  { id: '3', role: 'assistant', type: 'text', content: '我听到你了。工作压力大的时候确实会让人感到窒息。能和我说说具体是什么事情让你感到压力最大吗？', timestamp: new Date() },
];

export const TREND_DATA: TrendDataPoint[] = [
  { day: '一', value: 55, color: '#8B9DC3' },
  { day: '二', value: 40, color: '#E57373' },
  { day: '三', value: 65, color: '#6BBF8A' },
  { day: '四', value: 50, color: '#8B9DC3' },
  { day: '五', value: 75, color: '#6BBF8A' },
  { day: '六', value: 85, color: '#6BBF8A' },
  { day: '日', value: 70, color: '#3A7CA5' },
];

export const EMOTION_COLORS: Record<string, EmotionColor> = {
  '焦虑': { bg: '#FFF3E0', color: '#E65100' },
  '疲惫': { bg: '#FBE9E7', color: '#BF360C' },
  '困惑': { bg: '#E8EAF6', color: '#283593' },
  '期待': { bg: '#E8F5E9', color: '#2E7D32' },
  '平静': { bg: '#E0F2F1', color: '#00695C' },
  '感恩': { bg: '#FFF8E1', color: '#F57F17' },
  '温暖': { bg: '#FCE4EC', color: '#AD1457' },
  '领悟': { bg: '#E3F2FD', color: '#1565C0' },
  '悲伤': { bg: '#F3E5F5', color: '#6A1B9A' },
  '被理解': { bg: '#E8F5E9', color: '#2E7D32' },
};
