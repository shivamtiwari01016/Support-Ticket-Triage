import { useState } from 'react'
import { AlertCircle, ArrowDown, ScanText } from 'lucide-react'
import PredictionCard from '../components/analyzer/PredictionCard'
import TicketInput from '../components/analyzer/TicketInput'
import RecentTickets from '../components/dashboard/RecentTickets'
import { analyzeTicket } from '../services/api'

export default function TicketAnalyzer({ history, onPrediction, backendStatus }) {
  const [text, setText] = useState('')
  const [prediction, setPrediction] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [validationError, setValidationError] = useState('')
  const [requestError, setRequestError] = useState('')

  function updateText(value) {
    setText(value)
    setValidationError('')
    setRequestError('')
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (isSubmitting) return
    const trimmedText = text.trim()
    if (!trimmedText) {
      setValidationError('Please enter a support ticket before analyzing.')
      setPrediction(null)
      return
    }

    setValidationError('')
    setRequestError('')
    setPrediction(null)
    setIsSubmitting(true)
    try {
      const result = await analyzeTicket(trimmedText)
      setPrediction(result)
      onPrediction(result)
    } catch (error) {
      setRequestError(error.message || 'The NLP service encountered an error. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="page analyzer-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">SUPPORT OPERATIONS / NEW CASE</p>
          <h1>Ticket Analyzer</h1>
          <p className="page-heading__subtitle">Send a support ticket to the NLP service for category and sentiment-based urgency estimates.</p>
        </div>
        <span className={`service-chip service-chip--${backendStatus}`}>
          <span className="backend-status__dot" />
          {backendStatus === 'connected' ? 'API ready' : backendStatus === 'checking' ? 'Checking API' : 'API unavailable'}
        </span>
      </div>

      <div className="analyzer-layout">
        <section className="surface-panel analyzer-entry">
          <div className="section-heading">
            <div>
              <p className="eyebrow">INCOMING TICKET</p>
              <h2>Analyze support ticket</h2>
            </div>
            <span className="step-chip"><ScanText size={14} aria-hidden="true" /> Input</span>
          </div>
          <TicketInput
            value={text}
            onChange={updateText}
            onSubmit={handleSubmit}
            isSubmitting={isSubmitting}
            validationError={validationError}
          />
          <div className="request-flow" aria-hidden="true">
            <span>Ticket text</span><ArrowDown size={14} /><span>POST /api/v1/predictions</span><ArrowDown size={14} /><span>Verified response</span>
          </div>
        </section>

        <section className="analyzer-result" aria-live="polite">
          {isSubmitting ? (
            <div className="result-placeholder result-placeholder--loading">
              <span className="large-spinner" aria-hidden="true" />
              <p className="eyebrow">PROCESSING REQUEST</p>
              <h2>Contacting NLP service</h2>
              <p>Your text is being evaluated by the configured FastAPI endpoint.</p>
            </div>
          ) : requestError ? (
            <div className="error-panel" role="alert">
              <span className="error-panel__icon"><AlertCircle size={20} aria-hidden="true" /></span>
              <p className="eyebrow">REQUEST NOT COMPLETED</p>
              <h2>Prediction unavailable</h2>
              <p>{requestError}</p>
              <span className="error-panel__retry">Your ticket text is preserved. Correct the issue and retry.</span>
            </div>
          ) : prediction ? (
            <PredictionCard prediction={prediction} />
          ) : (
            <div className="result-placeholder">
              <p className="eyebrow">PREDICTION</p>
              <h2>Result appears here</h2>
              <p>Category and urgency are displayed only after a valid response from the backend.</p>
              <span className="result-placeholder__rule" />
              <span className="result-placeholder__foot">No browser-side classification</span>
            </div>
          )}
        </section>
      </div>

      <RecentTickets records={history} compact />
    </div>
  )
}
