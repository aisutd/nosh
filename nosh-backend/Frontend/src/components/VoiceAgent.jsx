import { authHeaders } from '../lib/api';
import { CookingFeedback } from './CookingMemory.jsx';
import { useEffect, useRef, useState } from 'react';
import './VoiceAgent.css';

const API = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

export default function VoiceAgent({ ingredients = [], recipe = '' }) {
  const [activeRecipe, setActiveRecipe] = useState(recipe);
  const [draft, setDraft] = useState('');
  const [interim, setInterim] = useState('');
  const [status, setStatus] = useState('Ready');
  const [error, setError] = useState('');
  const [messages, setMessages] = useState([]);
  const [spoken, setSpoken] = useState(true);
  const [listening, setListening] = useState(false);
  const [busy, setBusy] = useState(false);
  const recognition = useRef(null);
  const request = useRef(null);
  const session = useRef({ recipe, step: -1 });
  const locked = useRef(false);
  const enabled = useRef(true);
  const latest = useRef({ ingredients, spoken });
  useEffect(() => { latest.current = { ingredients, spoken }; }, [ingredients, spoken]);

  useEffect(() => {
    enabled.current = true;
    session.current = { recipe, step: -1 };
    return () => {
      enabled.current = false;
      if (recognition.current) {
        recognition.current.onend = null;
        recognition.current.onerror = null;
        recognition.current.onresult = null;
        recognition.current.abort();
        recognition.current = null;
      }
      request.current?.abort();
      window.speechSynthesis?.cancel();
    };
  }, [recipe]);

  async function send(text) {
    const message = text.trim();
    if (!message || locked.current) return;
    locked.current = true;
    recognition.current?.abort();
    window.speechSynthesis?.cancel();
    setListening(false); setBusy(true); setError(''); setDraft(''); setInterim('');
    setStatus('NOSH is thinking…');
    setMessages(items => [...items, { who: 'You', text: message }]);
    const controller = new AbortController();
    request.current = controller;
    const timeout = setTimeout(() => controller.abort(), 180000);
    try {
      const response = await fetch(`${API}/voice/turn`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ message, ingredients: latest.current.ingredients, ...session.current }),
        signal: controller.signal,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'NOSH could not respond. Try again.');
      if (typeof data?.answer !== 'string' || !Number.isInteger(data.step)) throw new Error('Unexpected NOSH response. Try again.');
      if (!enabled.current || controller.signal.aborted) return;
      if (data.recipe) setActiveRecipe(data.recipe);
      session.current = { recipe: data.recipe ?? session.current.recipe, step: data.step };
      setMessages(items => [...items, { who: 'NOSH', text: data.answer }]);
      setStatus('Ready');
      if (latest.current.spoken && window.speechSynthesis) {
        const utterance = new SpeechSynthesisUtterance(data.answer);
        utterance.onstart = () => enabled.current && setStatus('NOSH is speaking…');
        utterance.onend = utterance.onerror = () => enabled.current && setStatus('Ready');
        window.speechSynthesis.speak(utterance);
      }
    } catch (err) {
      if (enabled.current) {
        setDraft(message);
        setError(err.name === 'AbortError' ? 'The request timed out. Try again.' : err instanceof TypeError ? 'The NOSH backend is unavailable. Check that it is running, then try again.' : err.message);
        setStatus('Ready');
      }
    } finally {
      clearTimeout(timeout);
      locked.current = false;
      if (enabled.current) setBusy(false);
    }
  }

  function startListening() {
    if (!Recognition || busy || listening) return;
    window.speechSynthesis?.cancel();
    setError(''); setInterim('');
    const mic = new Recognition();
    mic.lang = 'en-US'; mic.interimResults = true; mic.continuous = false;
    recognition.current = mic;
    mic.onstart = () => { setListening(true); setStatus('Listening…'); };
    mic.onresult = event => {
      let partial = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) { void send(event.results[i][0].transcript); return; }
        partial += event.results[i][0].transcript;
      }
      setInterim(partial);
    };
    mic.onerror = event => {
      if (event.error === 'aborted') return;
      setError(event.error === 'not-allowed' ? 'Microphone access was denied. Allow it in browser settings, or type below.' : `Speech recognition stopped (${event.error}). Try again or type below.`);
    };
    mic.onend = () => { setListening(false); if (!locked.current) setStatus('Ready'); };
    try { mic.start(); } catch { setError('Could not start the microphone. Try again or type below.'); }
  }

  return <section className="voice-agent" aria-label="NOSH voice assistant">
    <h2>Cook with NOSH</h2>
    <p>Ask about your recipe, say “next step” or “repeat”. From your pantry, ask “What can I cook?”</p>
    <div className="voice-controls">
      <button disabled={!Recognition || busy || !window.isSecureContext} aria-pressed={listening} onClick={() => {
        if (listening) { recognition.current?.abort(); setInterim(''); setStatus('Ready'); }
        else startListening();
      }}>{listening ? '■ Stop listening' : '🎙 Start listening'}</button>
      <button onClick={() => { window.speechSynthesis?.cancel(); setStatus(busy ? 'NOSH is thinking…' : listening ? 'Listening…' : 'Ready'); }}>Stop speaking</button>
      <label><input type="checkbox" checked={spoken} onChange={event => {
        setSpoken(event.target.checked);
        if (!event.target.checked) { window.speechSynthesis?.cancel(); setStatus('Ready'); }
      }} /> Speak replies</label>
    </div>
    <p role="status">{status}{interim && ` You: ${interim}`}</p>
    {!Recognition && <p>Voice recognition is unavailable in this browser. You can type below.</p>}
    {Recognition && !window.isSecureContext && <p>Microphone access requires HTTPS or localhost. You can type below.</p>}
    {error && <p role="alert">{error}</p>}
    <div className="voice-messages" role="log" aria-label="Conversation with NOSH" aria-live="polite">
      {messages.map((item, index) => <p key={index}><strong>{item.who}: </strong>{item.text}</p>)}
    </div>
    <form onSubmit={event => { event.preventDefault(); void send(draft); }}>
      <label htmlFor="voice-question">Your cooking question</label>
      <div className="voice-controls"><input id="voice-question" maxLength={2000} value={draft} onChange={event => setDraft(event.target.value)} disabled={busy} placeholder="Ask NOSH…" />
      <button disabled={busy || !draft.trim()}>Send</button></div>
    </form>
    <div className="voice-controls">
      {['Start cooking', 'Previous step', 'Next step', 'Repeat'].map(command => <button key={command} disabled={busy || listening} onClick={() => void send(command)}>{command}</button>)}
    </div>
    {activeRecipe && <CookingFeedback key={activeRecipe} recipeTitle={activeRecipe.split("\n")[0].replace(/^Recipe Name:\s*/i, "").slice(0, 200)} />}
  </section>;
}
