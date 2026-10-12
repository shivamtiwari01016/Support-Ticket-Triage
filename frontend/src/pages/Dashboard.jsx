import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, BarChart3, Layers3, Ticket } from 'lucide-react'
import CategoryChart from '../components/dashboard/CategoryChart'
import RecentTickets from '../components/dashboard/RecentTickets'
import StatCard from '../components/dashboard/StatCard'
import { CATEGORIES } from '../data/categories'
import { getMetrics, getStatistics } from '../services/api'

export default function Dashboard({ history, historyLoading, historyError }) {
  const [statistics, setStatistics] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [statisticsLoading, setStatisticsLoading] = useState(true)
  const [metricsLoading, setMetricsLoading] = useState(true)
  const [statisticsError, setStatisticsError] = useState('')
  const [metricsError, setMetricsError] = useState('')

  useEffect(() => {
    let isMounted = true
    getStatistics()
      .then((data) => { if (isMounted) setStatistics(data) })
      .catch((error) => { if (isMounted) setStatisticsError(error.message) })
      .finally(() => { if (isMounted) setStatisticsLoading(false) })
    getMetrics()
      .then((data) => { if (isMounted) setMetrics(data) })
      .catch((error) => { if (isMounted) setMetricsError(error.message) })
      .finally(() => { if (isMounted) setMetricsLoading(false) })

    return () => { isMounted = false }
  }, [])

  const categoryData = CATEGORIES
    .map(({ name, color }) => ({
      category: name,
      count: statistics?.categoryDistribution[name] || 0,
      color,
    }))
    .filter((entry) => entry.count > 0)
  const averageUrgency = statistics
    ? `${Math.round(statistics.averageUrgency * 100)}%`
    : statisticsLoading ? '—' : '0%'
  const hasMetrics = Number.isFinite(metrics?.accuracy)
  const pct = (value) => (Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : '—')
  const accuracy = hasMetrics ? pct(metrics.accuracy) : metricsLoading ? '—' : 'Unavailable'
  const baseline = metrics?.majority_baseline_accuracy
  const belowBaseline = hasMetrics && Number.isFinite(baseline) && metrics.accuracy < baseline
  const delta = hasMetrics && Number.isFinite(baseline) ? metrics.accuracy - baseline : null

  return (
    <div className="page dashboard-page">
      <div className="page-heading page-heading--dashboard">
        <div>
          <p className="eyebrow">SUPPORT OPERATIONS / OVERVIEW</p>
          <h1>Support Ticket Triage</h1>
          <p className="page-heading__subtitle">Automatically classify support tickets and estimate urgency using an explainable NLP pipeline.</p>
        </div>
        <div className="dashboard-page__date">
          <span className="status-pulse" />
          MySQL runtime data · {history.length} recent shown
        </div>
      </div>

      <section className="stats-grid" aria-label="Support triage summary">
        <StatCard icon={Ticket} label="Total Tickets" value={statistics?.totalTickets ?? (statisticsLoading ? '—' : '0')} detail="Persisted runtime tickets" tone="teal" />
        <StatCard icon={Layers3} label="Categories" value={CATEGORIES.length} detail="Classifier label set" tone="blue" />
        <StatCard icon={Activity} label="Average Urgency" value={averageUrgency} detail={statistics ? 'Across saved predictions' : statisticsLoading ? 'Loading database statistics' : 'No saved predictions'} tone="amber" />
        <StatCard
          icon={BarChart3}
          label="Model Accuracy"
          value={accuracy}
          detail={hasMetrics ? `F1 ${pct(metrics.f1_score)} · baseline ${pct(baseline)}` : 'Training evaluation endpoint'}
          tone="coral"
        />
      </section>

      {(statisticsError || metricsError) && (
        <div className="dashboard-alert" role="alert">
          <AlertTriangle size={17} aria-hidden="true" />
          <p>{statisticsError || metricsError}</p>
        </div>
      )}
      {belowBaseline && (
        <div className="dashboard-alert" role="note">
          <AlertTriangle size={17} aria-hidden="true" />
          <p><strong>Evaluation caveat.</strong> Accuracy is {(Math.abs(delta) * 100).toFixed(1)} points below the {pct(baseline)} majority baseline; verify category predictions before routing.</p>
        </div>
      )}

      <section className="surface-panel metrics-panel" aria-label="Model evaluation metrics">
        <div className="section-heading">
          <div>
            <p className="eyebrow">HELD-OUT EVALUATION</p>
            <h2>Model accuracy on the test split</h2>
          </div>
          <span className="snapshot-tag">
            {metrics?.test_rows ? `${metrics.test_rows} test rows` : 'Evaluation artifact'}
          </span>
        </div>
        <p className="panel-caption">
          Measured offline on a stratified {metrics?.test_rows || '—'}-row holdout of the
          training set, not computed from live tickets. Baseline = always predict the most
          frequent category.
        </p>
        {metricsLoading ? (
          <div className="empty-state"><p>Loading evaluation metrics…</p></div>
        ) : hasMetrics ? (
          <>
            <div className="metric-grid">
              {[
                { label: 'Accuracy', value: metrics.accuracy },
                { label: 'Weighted F1', value: metrics.f1_score },
                { label: 'Weighted Precision', value: metrics.precision },
                { label: 'Weighted Recall', value: metrics.recall },
                { label: 'Macro F1', value: metrics.macro_f1 },
                { label: 'Majority Baseline', value: baseline },
              ].map(({ label, value }) => (
                <div className="metric-cell" key={label}>
                  <span className="metric-cell__label">{label}</span>
                  <span className="metric-cell__value">{pct(value)}</span>
                  <span className="metric-bar">
                    <span className="metric-bar__fill" style={{ width: pct(value) }} />
                  </span>
                </div>
              ))}
            </div>
            {delta !== null && (
              <p className="metric-footnote">
                Accuracy delta vs majority baseline:{' '}
                <strong className={delta >= 0 ? 'delta-up' : 'delta-down'}>
                  {delta >= 0 ? '+' : ''}{(delta * 100).toFixed(1)} pts
                </strong>
              </p>
            )}
          </>
        ) : (
          <div className="empty-state"><p>Evaluation metrics are unavailable.</p></div>
        )}
      </section>

      <section className="overview-grid">
        <article className="surface-panel category-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">PERSISTED TICKETS</p>
              <h2>Predicted category distribution</h2>
            </div>
            <span className="snapshot-tag">Live · MySQL</span>
          </div>
          <p className="panel-caption">Category counts are calculated from stored prediction records; no Kaggle training rows are imported.</p>
          {statisticsLoading ? (
            <div className="empty-state"><p>Loading database statistics…</p></div>
          ) : categoryData.length ? (
            <CategoryChart data={categoryData} />
          ) : (
            <div className="empty-state"><p>No ticket predictions yet.</p></div>
          )}
        </article>
        <article className="surface-panel operator-note">
          <p className="eyebrow">TRIAGE WORKFLOW</p>
          <div className="operator-note__mark">Workflow</div>
          <h2>Read the signal. Verify the route.</h2>
          <p>The model combines TF-IDF features with Logistic Regression. Urgency comes from sentiment and should guide review, not replace an operator’s judgment.</p>
          <div className="operator-note__footer">
            <span className="operator-note__line" />
            <span>Explainable baseline · operator review</span>
          </div>
        </article>
      </section>

      <RecentTickets records={history} loading={historyLoading} error={historyError} />
    </div>
  )
}
