import './Presentation.css';
import { useCallback, useEffect, useRef, useState } from 'react';
import PresentationPhone from '../components/PresentationPhone';
import { request, authHeaders } from '../lib/api';
import { presentationContent, nextStory, nextAction, topicForEvent } from '../lib/presentationContent';

export default function Presentation() {
  const [{ page }, setNavigation] = useState({ page: 'title', history: [] });
  const setPage = value => setNavigation(current => ({ ...current, page: value }));
  const setHistory = value => setNavigation(current => ({ ...current, history: value }));
  const [sample, setSample] = useState(false);
  const [sampleKey, setSampleKey] = useState(0);
  const [livePage, setLivePage] = useState('intro');
  const [prompt, setPrompt] = useState('');
  const [statuses, setStatuses] = useState({});
  const [prepare, setPrepare] = useState(false);
  const [checks, setChecks] = useState({ backend: 'Not checked', account: 'Not checked' });
  const [checking, setChecking] = useState(false);
  const frameRef = useRef(null);
  const sampleFrameRef = useRef(null);
  const checkController = useRef(null);
  const content = presentationContent[page];
  const showPhone = page !== 'title' && page !== 'ending';

  const select = useCallback(next => {
    setNavigation(current => current.page === next ? current : { page: next, history: [...current.history, current.page] });
    setPrompt('');
  }, []);
  const back = useCallback(() => {
    setNavigation(current => {
      if (!current.history.length) return current;
      const previous = current.history.at(-1);
      return { page: previous === 'inventory' ? 'voice' : previous, history: current.history.slice(0, -1) };
    });
    setPrompt('');
  }, []);
  const next = useCallback(() => {
    if (nextStory[page]) select(nextStory[page]);
    else setPrompt(nextAction[page] || 'Use the app to continue, or press End to jump to the wrap-up.');
  }, [page, select]);

  useEffect(() => {
    function message(event) {
      const frame = sample ? sampleFrameRef : frameRef;
      if (event.origin !== window.location.origin || event.source !== frame.current?.contentWindow) return;
      if (event.data?.type !== 'nosh-demo') return;
      if (event.data.kind === 'status') {
        const { operation, status, message: detail } = event.data;
        if (typeof operation !== 'string' || !['loading', 'success', 'error'].includes(status)) return;
        setStatuses(previous => ({ ...previous, [operation]: { status, message: typeof detail === 'string' ? detail : '' } }));
        return;
      }
      const topic = topicForEvent(event.data);
      if (topic && showPhone) select(topic);
    }
    window.addEventListener('message', message);
    return () => window.removeEventListener('message', message);
  }, [sample, showPhone, select]);
  useEffect(() => {
    function key(event) {
      if (event.target.closest?.('button, input, select, textarea, a, [contenteditable]') || event.altKey || event.ctrlKey || event.metaKey || event.repeat) return;
      if (event.key === 'ArrowRight') { event.preventDefault(); next(); }
      if (event.key === 'End') { event.preventDefault(); select('challenges'); }
      if (event.key === 'ArrowLeft') { event.preventDefault(); back(); }
    }
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [next, back, select]);
  useEffect(() => {
    if (!['intro', 'problem', 'challenges'].includes(page)) return;
    const frame = sample ? sampleFrameRef : frameRef;
    frame.current?.contentWindow?.postMessage(
      { type: 'nosh-demo-command', command: 'show-intro' }, window.location.origin);
  }, [page, sample]);
  useEffect(() => () => checkController.current?.abort(), []);

  async function checkReadiness() {
    checkController.current?.abort();
    const controller = new AbortController();
    checkController.current = controller;
    setChecking(true);
    const [health, account] = await Promise.allSettled([
      request('/health', { timeout: 5000, signal: controller.signal }),
      request('/me', { headers: authHeaders(), timeout: 5000, signal: controller.signal }),
    ]);
    if (controller.signal.aborted) return;
    setChecks({ backend: health.status === 'fulfilled' ? 'Reachable' : 'Unavailable — start the backend and retry',
      account: account.status === 'fulfilled' && account.value.username ? `Signed in as ${account.value.username}` : 'Sign in inside the live phone before presenting' });
    setChecking(false);
  }
  function changeMode() {
    if (!sample) {
      frameRef.current?.contentWindow?.postMessage({ type: "nosh-demo-pause" }, window.location.origin);
      setLivePage(page);
      setSampleKey(key => key + 1);
      setPage('scan');
    } else setPage(livePage);
    setSample(!sample);
    setStatuses({}); setHistory([]); setPrompt('');
  }
  function reset() {
    setSampleKey(key => key + 1);
    setPage(sample ? 'scan' : 'title');
    setHistory([]); setStatuses({}); setPrompt('');
  }
  return <main className={`presentation guided-presentation${showPhone ? " presentation-started" : ""}`} tabIndex={-1} aria-label="NOSH guided presentation">
    <header className="presenter-toolbar">
      <strong>{sample ? 'SAMPLE DEMO · SIMULATED' : 'LIVE DEMO'}</strong>
      <button onClick={() => { setPrepare(value => !value); }}>Preparation</button>
      <button onClick={changeMode}>{sample ? 'Return to live app' : 'Use sample demo'}</button>
      <button onClick={reset}>Reset {sample ? 'sample' : 'presentation'}</button>
    </header>
    {prepare && <aside className="presenter-preparation" aria-label="Presenter preparation">
      <h2>Before you present</h2>
      <p>Backend: {checks.backend}</p><p>Account: {checks.account}</p>
      <p>A reachable health endpoint does not verify MongoDB, scanning models, or Ollama.</p>
      <ul><li>Sign in inside the live phone before starting.</li><li>Have a fridge photo or video ready.</li><li>Allow microphone access and try a voice question.</li></ul>
      <button disabled={checking} onClick={checkReadiness}>{checking ? 'Checking…' : 'Check / Retry readiness'}</button>
      <button onClick={() => { if (sample) changeMode(); setPage('intro'); setPrepare(false); }}>Open live phone</button>
      <button onClick={() => setPrepare(false)}>Close preparation</button>
    </aside>}
    {!showPhone && <section className="presentation-title-screen">
      <span className="presentation-title-label">YOUR AI COOKING BUDDY</span>
      <h1 className="presentation-title-logo">{page === 'title' ? 'nosh' : 'Thank you'}<span>.</span></h1>
      <p className="presentation-title-tagline">{page === 'title' ? 'Present the story. Cook along with the demo.' : 'Questions?'}</p>
      <button className="presentation-control" onClick={() => select('intro')}>{page === 'title' ? 'Begin presentation →' : 'Back to start'}</button>
    </section>}
    <div className="presentation-layout" style={{ visibility: showPhone ? 'visible' : 'hidden' }} inert={!showPhone} aria-hidden={!showPhone}>
      <PresentationPhone frameRef={frameRef} sampleFrameRef={sampleFrameRef} started={showPhone} sample={sample} sampleKey={sampleKey} />
      <section className="presentation-content">
        {content && <div key={page} className="presentation-copy" aria-live="polite">
          <span className="presentation-eyebrow">{content.label}</span><h1>{content.title}</h1>
          <p className="presentation-description">{content.description}</p>
          <div className="presentation-features">{content.points.map(point => <span key={point}>{point}</span>)}</div>
          {content.note && <p className="presentation-note">{content.note}</p>}
        </div>}
        <div className="presentation-next-action" role="status"><strong>Next demo action</strong><p>{prompt || nextAction[page] || 'Press → to continue the explanation.'}</p></div>
        {Object.entries(statuses).filter(([, value]) => value.status !== 'success').map(([operation, value]) => <p key={operation} role={value.status === 'error' ? 'alert' : 'status'} className="presentation-operation">
          {operation}: {value.message || value.status}. {value.status === 'error' && 'Retry the action in the phone, or choose Use sample demo.'}
        </p>)}
      </section>
    </div>

  </main>;
}
