import axios from 'axios'
import { LOW_URGENCY_THRESHOLD, MEDIUM_URGENCY_THRESHOLD } from '../utils/urgency'

// Default to a relative base so the Vite dev/preview proxy handles the request
// (same origin -> no CORS, no IPv4/IPv6 "localhost" split). Set VITE_API_URL to
// an absolute origin only when serving a production build without a proxy.
const API_BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')
const API_V1_URL = `${API_BASE_URL}/api/v1`
const API_KEY = (import.meta.env.VITE_API_KEY || '').trim()
const PREDICTION_TIMEOUT_MS = 45000
const HEALTH_TIMEOUT_MS = 8000
const DATA_TIMEOUT_MS = 20000

function withAuthHeaders(extra = {}) {
  if (!API_KEY) {
    return extra
  }
  return {
    ...extra,
    headers: {
      ...(extra.headers || {}),
      'X-API-Key': API_KEY,
    },
  }
}

let healthCheckPromise

function normalizeUrgency(value) {
  if (typeof value === 'number') {
    if (Number.isFinite(value) && value >= 0 && value <= 1) return value
  } else if (value && typeof value === 'object' && Number.isFinite(value.score)) {
    const normalizedScore = value.score / 100
    if (normalizedScore >= 0 && normalizedScore <= 1) return normalizedScore
  }
  return 0
}

const KNOWN_STATUSES = new Set(['open', 'in_progress', 'resolved'])
const KNOWN_URGENCY_LEVELS = new Set(['Low', 'Medium', 'High'])

function safeString(value, fallback = '') {
  return typeof value === 'string' ? value : fallback
}

// Tolerant on purpose: one unexpected status/level value must not blank the
// whole dashboard, so unknown enum values degrade instead of throwing.
function normalizeTicket(record) {
  if (!record || typeof record.ticket_id !== 'string' || typeof record.text !== 'string') {
    return null
  }

  const urgency = normalizeUrgency(record.urgency)
  const status = KNOWN_STATUSES.has(record.status) ? record.status : 'open'
  const urgencyLevel = KNOWN_URGENCY_LEVELS.has(record.urgency_level)
    ? record.urgency_level
    : urgency >= MEDIUM_URGENCY_THRESHOLD
      ? 'High'
      : urgency >= LOW_URGENCY_THRESHOLD
        ? 'Medium'
        : 'Low'

  return {
    id: record.ticket_id,
    ticketId: record.ticket_id,
    text: record.text,
    status,
    category: safeString(record.category, 'Unclassified'),
    assignedTeam: safeString(record.assigned_team, 'Unassigned'),
    urgency,
    score: urgency,
    urgencyLevel,
    level: urgencyLevel,
    createdAt: safeString(record.created_at),
  }
}

function apiError(error, notFoundMessage = 'The requested support data is unavailable.') {
  if (!axios.isAxiosError(error)) return error
  if (!error.response) {
    return new Error('Unable to connect to the NLP backend. Please verify that the FastAPI server is running.')
  }
  if (error.response.status === 401 || error.response.status === 403) {
    return new Error('Authentication failed. Check the configured API key for this environment.')
  }
  if (error.response.status === 404) return new Error(notFoundMessage)
  if (error.response.status === 422) return new Error('Please enter a valid support ticket.')
  if (error.response.status === 429) return new Error('Too many requests. Please wait a moment and try again.')
  if (error.response.status === 503) {
    return new Error('The support service or database is unavailable. Please try again shortly.')
  }
  if (error.response.status >= 500) {
    return new Error('The NLP service encountered an error. Please try again.')
  }
  return new Error('The NLP service could not complete the request. Please try again.')
}

export async function analyzeTicket(text) {
  try {
    const { data } = await axios.post(
      `${API_V1_URL}/predictions`,
      { text },
      withAuthHeaders({ timeout: PREDICTION_TIMEOUT_MS }),
    )

    if (!data || typeof data.category !== 'string' || !data.category.trim()) {
      throw new Error('Received an invalid response from the NLP service.')
    }

    return { ...normalizeTicket(data), category: data.category.trim() }
  } catch (error) {
    if (axios.isAxiosError(error)) throw apiError(error)
    throw error
  }
}

export async function getTickets(limit = 20) {
  try {
    const { data } = await axios.get(`${API_V1_URL}/tickets`, withAuthHeaders({
      params: { limit },
      timeout: DATA_TIMEOUT_MS,
    }))
    if (!Array.isArray(data)) throw new Error('Received an invalid response from the NLP service.')
    return data.map(normalizeTicket).filter(Boolean)
  } catch (error) {
    throw apiError(error, 'Ticket history is unavailable from the backend.')
  }
}

export async function getTicket(ticketId) {
  try {
    const { data } = await axios.get(
      `${API_V1_URL}/tickets/${encodeURIComponent(ticketId)}`,
      withAuthHeaders({ timeout: DATA_TIMEOUT_MS }),
    )
    return normalizeTicket(data)
  } catch (error) {
    throw apiError(error, 'Ticket not found.')
  }
}

export async function getStatistics() {
  try {
    const { data } = await axios.get(`${API_V1_URL}/statistics`, withAuthHeaders({ timeout: DATA_TIMEOUT_MS }))
    if (!Number.isFinite(data.average_urgency)) data.average_urgency = 0
    if (
      !data.category_distribution ||
      typeof data.category_distribution !== 'object' ||
      Array.isArray(data.category_distribution)
    ) {
      data.category_distribution = {}
    }
    return {
      totalTickets: Number.isFinite(data.total_tickets) ? data.total_tickets : 0,
      averageUrgency: Math.min(Math.max(data.average_urgency, 0), 1),
      categoryDistribution: data.category_distribution,
    }
  } catch (error) {
    throw apiError(error)
  }
}

export async function getMetrics() {
  try {
    const { data } = await axios.get(`${API_V1_URL}/metrics`, withAuthHeaders({ timeout: DATA_TIMEOUT_MS }))
    if (!data || typeof data !== 'object') {
      throw new Error('Received an invalid response from the NLP service.')
    }
    // Per-field: a single absent metric must not hide the whole panel.
    const read = (field) => (Number.isFinite(data[field]) ? data[field] : null)
    return {
      accuracy: read('accuracy'),
      precision: read('precision'),
      recall: read('recall'),
      f1_score: read('f1_score'),
      macro_precision: read('macro_precision'),
      macro_recall: read('macro_recall'),
      macro_f1: read('macro_f1'),
      majority_baseline_accuracy: read('majority_baseline_accuracy'),
      dataset_rows: read('dataset_rows'),
      test_rows: read('test_rows'),
    }
  } catch (error) {
    throw apiError(error)
  }
}

export function checkBackendHealth() {
  if (!healthCheckPromise) {
    healthCheckPromise = axios
      .get(`${API_V1_URL}/health`, withAuthHeaders({ timeout: HEALTH_TIMEOUT_MS }))
      .then(({ data }) =>
        data?.status === 'ok' &&
        data?.database === 'connected' &&
        data?.model === 'loaded' &&
        data?.nlp === 'ready',
      )
      .catch(() => false)
      .finally(() => {
        healthCheckPromise = undefined
      })
  }

  return healthCheckPromise
}
