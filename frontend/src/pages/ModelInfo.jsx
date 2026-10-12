import { useEffect, useState } from 'react'
import { AlertTriangle, BookOpenCheck, ChartNoAxesColumnIncreasing, Scale } from 'lucide-react'
import { getMetrics } from '../services/api'

function DetailRow({ label, value }) {
  return <div className="detail-row"><dt>{label}</dt><dd>{value}</dd></div>
}

export default function ModelInfo() {
  const [metrics, setMetrics] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let isMounted = true
    getMetrics()
      .then((data) => { if (isMounted) setMetrics(data) })
      .catch((requestError) => { if (isMounted) setError(requestError.message) })
      .finally(() => { if (isMounted) setIsLoading(false) })
    return () => { isMounted = false }
  }, [])

  const belowBaseline = metrics && metrics.accuracy < metrics.majority_baseline_accuracy
  const metricRows = metrics
    ? [
        ['Accuracy', metrics.accuracy],
        ['Weighted precision', metrics.precision],
        ['Weighted recall', metrics.recall],
        ['Weighted F1-score', metrics.f1_score],
        ['Macro precision', metrics.macro_precision],
        ['Macro recall', metrics.macro_recall],
        ['Macro F1-score', metrics.macro_f1],
      ]
    : []

  return (
    <div className="page model-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">MODEL CARD / IMPLEMENTATION NOTES</p>
          <h1>Model Information</h1>
          <p className="page-heading__subtitle">A compact, inspectable baseline designed to be explained and challenged.</p>
        </div>
        <span className="snapshot-tag">Metrics · evaluation artifact</span>
      </div>

      {belowBaseline && (
        <section className="model-warning" role="note">
          <AlertTriangle size={19} aria-hidden="true" />
          <div>
            <strong>Not ready for automatic routing</strong>
            <p>Measured accuracy is below the majority-class baseline. The dataset has proxy Ticket Type labels, not verified queue destinations.</p>
          </div>
        </section>
      )}
      {error && <div className="dashboard-alert" role="alert">{error}</div>}

      <div className="model-overview-grid">
        <section className="model-section">
          <div className="model-section__heading"><BookOpenCheck size={17} aria-hidden="true" /><h2>Classification</h2></div>
          <dl className="detail-list">
            <DetailRow label="Algorithm" value="Logistic Regression" />
            <DetailRow label="Input features" value="TF-IDF sparse vectors" />
            <DetailRow label="N-grams" value="Unigrams + bigrams" />
            <DetailRow label="Categories" value="Billing · Technical Support · Account · General" />
            <DetailRow label="Training split" value="80 / 20 stratified · random_state 42" />
            <DetailRow label="Imbalance handling" value="Stratification + balanced class weights" />
          </dl>
        </section>
        <section className="model-section">
          <div className="model-section__heading"><Scale size={17} aria-hidden="true" /><h2>NLP processing</h2></div>
          <dl className="detail-list">
            <DetailRow label="Language tools" value="spaCy en_core_web_sm" />
            <DetailRow label="Normalization" value="Cleaning · script validation · tokenization" />
            <DetailRow label="Linguistic steps" value="Stop words · lemmatization · noun chunks" />
            <DetailRow label="Structured features" value="NER types: DATE · MONEY · ORG" />
            <DetailRow label="Urgency" value="VADER sentiment heuristic" />
            <DetailRow label="Category model" value="scikit-learn TF-IDF + Logistic Regression" />
          </dl>
        </section>
      </div>

      <section className="model-section metrics-section">
        <div className="section-heading section-heading--inline">
          <div><p className="eyebrow">HELD-OUT EVALUATION{metrics?.dataset_rows ? ` · ${metrics.dataset_rows.toLocaleString()} ROWS` : ''}</p><h2>Measured classification metrics</h2></div>
          <span className="snapshot-tag">GET /api/v1/metrics</span>
        </div>
        {isLoading ? (
          <div className="empty-state empty-state--compact" role="status"><p>Loading training metrics…</p></div>
        ) : error ? (
          <div className="empty-state empty-state--compact" role="alert"><p>Training metrics are unavailable.</p></div>
        ) : (
          <div className="metrics-table-wrap">
            <table className="metrics-table">
              <thead><tr><th scope="col">Metric</th><th scope="col">Score</th><th scope="col">Interpretation</th></tr></thead>
              <tbody>
                {metricRows.map(([label, value]) => (
                  <tr key={label}><th scope="row">{label}</th><td>{Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : '—'}</td><td>Four-way proxy-label holdout</td></tr>
                ))}
                <tr className="metrics-table__baseline"><th scope="row">Majority accuracy baseline</th><td>{Number.isFinite(metrics?.majority_baseline_accuracy) ? `${(metrics.majority_baseline_accuracy * 100).toFixed(1)}%` : '—'}</td><td>Predict the largest class for every ticket</td></tr>
              </tbody>
            </table>
          </div>
        )}
        <p className="metrics-note"><ChartNoAxesColumnIncreasing size={15} aria-hidden="true" /> Metrics are loaded from the actual training evaluation JSON; they are not calculated from live ticket history.</p>
      </section>

      <section className="model-footer-note">
        <span className="model-footer-note__line" />
        <p><strong>Interpretation:</strong> TF-IDF assigns higher weight to terms that are informative within a ticket and less common across the corpus. Logistic Regression learns a coefficient per feature and category; balanced class weights increase the loss contribution of underrepresented classes. This is inspectable, unlike a black-box deep model.</p>
      </section>
    </div>
  )
}
