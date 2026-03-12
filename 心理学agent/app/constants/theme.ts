export const Colors = {
  bgBody: '#F0EDE8',
  bgPhone: '#FAFAF8',
  bgCard: '#FFFFFF',
  bgInput: '#F2F0ED',
  bgBubbleUser: '#3A7CA5',
  bgBubbleAi: '#F2F0ED',

  primary: '#3A7CA5',
  primaryLight: '#E8F2F8',
  accent: '#8B9DC3',
  warm: '#C4A882',

  text: '#1D1D1F',
  textSecondary: '#86868B',
  textTertiary: '#AEAEB2',
  border: '#E5E5EA',

  success: '#6BBF8A',
  warning: '#F5A623',
  danger: '#E57373',
};

export const Radius = {
  sm: 8,
  md: 14,
  lg: 20,
  xl: 28,
};

export const Shadows = {
  sm: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 3,
    elevation: 1,
  },
  md: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.06,
    shadowRadius: 12,
    elevation: 3,
  },
  lg: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.08,
    shadowRadius: 30,
    elevation: 5,
  },
} as const;

export const FontSizes = {
  xs: 10,
  sm: 12,
  body: 15,
  md: 16,
  lg: 17,
  xl: 20,
  xxl: 22,
  title: 28,
};
