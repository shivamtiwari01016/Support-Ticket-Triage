import { Component, lazy, Suspense, useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './App.css'
import AppLayout from './components/layout/AppLayout'
import { checkBackendHealth, getTickets } from './services/api'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const ModelInfo = lazy(() => import('./pages/ModelInfo'))
const Pipeline = lazy(() => import('./pages/Pipeline'))
const TicketAnalyzer = lazy(() => import('./pages/TicketAnalyzer'))

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="page">
          <div className="error-panel" role="alert">
            <span className="error-panel__icon">!</span>
            <p className="eyebrow">APPLICATION ERROR</p>
            <h2>Something went wrong</h2>
            <p>The dashboard could not be rendered. Please refresh the page and try again.</p>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

function App() {
  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState('')
  const [backendStatus, setBackendStatus] = useState('checking')

  useEffect(() => {
    let isMounted = true
    getTickets(10)
      .then((tickets) => {
        if (!isMounted) return
        setHistory(tickets)
        setHistoryError('')
      })
      .catch((error) => {
        if (isMounted) setHistoryError(error.message)
      })
      .finally(() => {
        if (isMounted) setHistoryLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    let isMounted = true
    const refreshStatus = async () => {
      const isAvailable = await checkBackendHealth()
      if (isMounted) setBackendStatus(isAvailable ? 'connected' : 'unavailable')
    }

    refreshStatus()
    const intervalId = window.setInterval(refreshStatus, 60_000)
    return () => {
      isMounted = false
      window.clearInterval(intervalId)
    }
  }, [])

  function handlePrediction(ticket) {
    setHistory((current) => [ticket, ...current.filter((item) => item.ticketId !== ticket.ticketId)].slice(0, 10))
    setHistoryError('')
    setHistoryLoading(false)
  }

  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Suspense fallback={<div className="route-loading" role="status">Loading workspace…</div>}>
          <Routes>
            <Route element={<AppLayout status={backendStatus} />}>
              <Route index element={<Dashboard history={history} historyLoading={historyLoading} historyError={historyError} />} />
              <Route
                path="analyze"
                element={
                  <TicketAnalyzer
                    history={history}
                    historyLoading={historyLoading}
                    historyError={historyError}
                    onPrediction={handlePrediction}
                    backendStatus={backendStatus}
                  />
                }
              />
              <Route path="pipeline" element={<Pipeline />} />
              <Route path="model" element={<ModelInfo />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </BrowserRouter>
  )
}

export default App
