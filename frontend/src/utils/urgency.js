export const LOW_URGENCY_THRESHOLD = 0.34
export const MEDIUM_URGENCY_THRESHOLD = 0.67

export function getUrgencyPresentation(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return { score: null, percentage: null, level: 'Unavailable', tone: 'neutral' }
  }

  const score = Math.min(1, Math.max(0, value))
  const percentage = Math.round(score * 100)
  const level = score < LOW_URGENCY_THRESHOLD ? 'Low' : score < MEDIUM_URGENCY_THRESHOLD ? 'Medium' : 'High'
  const tone = level.toLowerCase()

  return { score, percentage, level, tone }
}

export function getUrgencyLevel(score) {
  return getUrgencyPresentation(score).level
}
