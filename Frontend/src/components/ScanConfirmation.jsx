import './ScanConfirmation.css';

export default function ScanConfirmation({ confirmation, onDismiss }) {
  return <div className="scan-confirmation-region" role="status" aria-live="polite" aria-atomic="true">
    {confirmation && <div className="scan-confirmation" key={confirmation.id}>
      <span className="scan-confirmation-icon" aria-hidden="true">✓</span>
      <p>{confirmation.message}</p>
      <button type="button" onClick={onDismiss} aria-label="Dismiss scan confirmation">×</button>
    </div>}
  </div>;
}
