import { demoStatus } from "../lib/demo";
import NativeVoiceAgent from './NativeVoiceAgent.jsx';
import { LuMic, LuSquare } from 'react-icons/lu';
import { API, authHeaders } from '../lib/api';
import { CookingFeedback } from './CookingMemory.jsx';
import { useEffect, useRef, useState } from 'react';
import './VoiceAgent.css';

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

const VOICE_KEY = 'nosh-reply-voice';

function voiceQuality(voice) {
  if (/natural|neural|premium/i.test(voice.name)) return 3;
  if (/enhanced|google/i.test(voice.name)) return 2;
  return voice.default ? 1 : 0;
}

function speechText(text) {
  const fractions = { '1/2': 'half', '1/3': 'one third', '2/3': 'two thirds', '1/4': 'one quarter', '3/4': 'three quarters' };
  return text
    .replace(/\b(\d+)\s+([123]\/[234])\b/g, (match, whole, fraction) =>
      fractions[fraction] ? `${whole} and ${fraction === '1/2' ? 'a half' : fractions[fraction]}` : match)
    .replace(/(?<![\d/])(?:1\/2|1\/3|2\/3|1\/4|3\/4)(?![\d/])/g, fraction => fractions[fraction]);
}

export default function VoiceAgent(props) {
  if (window.ReactNativeWebView?.postMessage) return <NativeVoiceAgent {...props} />;
  return <VoiceConversation key={props.recipe ?? ''} {...props} />;
}

function VoiceConversation({ ingredients = [], recipe = '' }) {
  const [activeRecipe, setActiveRecipe] = useState(recipe);
  const [draft, setDraft] = useState('');
  const [interim, setInterim] = useState('');
  const [status, setStatus] = useState('Ready');
  const [error, setError] = useState('');
  const [messages, setMessages] = useState([]);
  const [spoken, setSpoken] = useState(true);
  const [voices, setVoices] = useState([]);
  const [voiceURI, setVoiceURI] = useState(() => {
    try { return window.localStorage.getItem(VOICE_KEY) || ''; }
    catch { return ''; }
  });
  useEffect(() => {
    const synthesis = window.speechSynthesis;
    if (!synthesis) return;
    function loadVoices() {
      setVoices(synthesis.getVoices().filter(voice => /^en(?:-|$)/i.test(voice.lang)).sort((a, b) =>
        voiceQuality(b) - voiceQuality(a)
        || Number(b.lang === 'en-US') - Number(a.lang === 'en-US')
        || a.name.localeCompare(b.name)));
    }
    loadVoices();
    synthesis.addEventListener('voiceschanged', loadVoices);
    return () => synthesis.removeEventListener('voiceschanged', loadVoices);
  }, []);
  const selectedVoice = voices.find(voice => voice.voiceURI === voiceURI) ?? voices[0];
  const [conversationOn, setConversationOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const recognition = useRef(null);
  const request = useRef(null);
  const reply = useRef(null);
  const restart = useRef(null);
  const emptyStarts = useRef(0);
  const conversation = useRef(false);
  const session = useRef({ recipe, step: -1, history: [] });
  const latest = useRef({ ingredients, spoken, selectedVoice });
  useEffect(() => { latest.current = { ingredients, spoken, selectedVoice }; }, [ingredients, spoken, selectedVoice]);

  useEffect(() => () => {
    conversation.current = false;
    clearTimeout(restart.current);
    const mic = recognition.current;
    recognition.current = null;
    mic?.abort();
    const pending = request.current;
    request.current = null;
    pending?.abort();
    if (reply.current) {
      reply.current = null;
      window.speechSynthesis.cancel();
    }
  }, []);

  useEffect(() => {
    function pauseForSample(event) {
      if (event.origin !== window.location.origin || event.source !== window.parent || event.data?.type !== 'nosh-demo-pause') return;
      conversation.current = false;
      setConversationOn(false);
      clearTimeout(restart.current);
      const mic = recognition.current;
      recognition.current = null;
      mic?.abort();
      if (request.current) { request.current.allowSpeech = false; request.current.cancelled = true; request.current.abort(); }
      if (reply.current) { reply.current = null; window.speechSynthesis.cancel(); }
      setInterim(''); setStatus('Paused for sample demo');
    }
    window.addEventListener('message', pauseForSample);
    return () => window.removeEventListener('message', pauseForSample);
  }, []);

  function pauseMic() {
    clearTimeout(restart.current);
    const mic = recognition.current;
    recognition.current = null;
    mic?.abort();
    setInterim('');
  }

  function resumeMic() {
    clearTimeout(restart.current);
    if (!conversation.current) {
      setStatus('Ready');
      return;
    }
    if (request.current || reply.current || recognition.current) return;
    setStatus('Getting the microphone ready…');
    restart.current = setTimeout(openMic, 300);
  }

  function stopReply() {
    if (!reply.current) return;
    reply.current = null;
    window.speechSynthesis.cancel();
  }

  function speakReply(text) {
    pauseMic();
    stopReply();
    const utterance = new SpeechSynthesisUtterance(speechText(text));
    const voice = latest.current.selectedVoice;
    if (voice) utterance.voice = voice;
    utterance.lang = voice?.lang || 'en-US';
    utterance.rate = 0.96;
    reply.current = utterance;
    utterance.onend = utterance.onerror = () => {
      if (reply.current !== utterance) return;
      reply.current = null;
      resumeMic();
    };
    setStatus('NOSH is speaking…');
    try { window.speechSynthesis.speak(utterance); }
    catch { utterance.onerror(); }
  }

  function stopConversation() {
    conversation.current = false;
    setConversationOn(false);
    pauseMic();
    stopReply();
    setStatus(request.current ? 'NOSH is thinking…' : 'Ready');
  }

  async function send(text) {
    const message = text.trim().slice(0, 2000);
    if (!message || request.current) return;
    demoStatus('Voice', 'loading', 'Waiting for a cooking reply');
    pauseMic();
    stopReply();
    emptyStarts.current = 0;
    setBusy(true); setError(''); setDraft('');
    setStatus('NOSH is thinking…');
    setMessages(items => [...items, { who: 'You', text: message }]);
    const controller = new AbortController();
    request.current = controller;
    const timeout = setTimeout(() => controller.abort(), 45000);
    try {
      const response = await fetch(`${API}/voice/turn`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ message, ingredients: latest.current.ingredients, ...session.current }),
        signal: controller.signal,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'NOSH could not respond. Try again.');
      if (typeof data?.answer !== 'string' || !Number.isInteger(data.step)) throw new Error('Unexpected NOSH response. Try again.');
      if (request.current !== controller || controller.signal.aborted) return;
      const nextRecipe = data.recipe ?? session.current.recipe;
      if (data.recipe) setActiveRecipe(data.recipe);
      const history = nextRecipe === session.current.recipe ? session.current.history : [];
      session.current = {
        recipe: nextRecipe,
        step: data.step,
        history: [...history, { question: message, answer: data.answer.slice(0, 2000) }].slice(-4),
      };
      demoStatus('Voice', 'success');
      setMessages(items => [...items, { who: 'NOSH', text: data.answer }]);
      if (latest.current.spoken && window.speechSynthesis && controller.allowSpeech !== false) {
        speakReply(data.answer);
      }
    } catch (err) {
      if (request.current === controller) {
        stopReply();
        setDraft(message);
        demoStatus('Voice', 'error', 'Voice request failed. Retry your question in the phone.');
        setError(err.name === 'AbortError' ? controller.cancelled ? 'Request cancelled.' : 'NOSH took too long to answer. Check that Ollama is running, then try again.' : err instanceof TypeError ? 'The NOSH backend is unavailable. Check that it is running, then try again.' : err.message);
      }
    } finally {
      clearTimeout(timeout);
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
        if (!reply.current) resumeMic();
      }
    }
  }

  function openMic() {
    if (!conversation.current || request.current || reply.current || recognition.current) return;
    const mic = new Recognition();
    mic.lang = 'en-US'; mic.interimResults = true; mic.continuous = false;
    recognition.current = mic;
    let startedAt = 0;
    let heardSpeech = false;
    mic.onstart = () => {
      if (recognition.current !== mic) return;
      startedAt = Date.now();
      setStatus('Listening…');
    };
    mic.onresult = event => {
      if (recognition.current !== mic) return;
      const final = [];
      const partial = [];
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        (result.isFinal ? final : partial).push(result[0].transcript);
      }
      heardSpeech = true;
      const transcript = final.join(' ').trim();
      if (transcript) void send(transcript);
      else setInterim(partial.join(' '));
    };
    mic.onerror = event => {
      if (recognition.current !== mic || event.error === 'no-speech') return;
      stopConversation();
      setError(event.error === 'network' ? 'The browser could not connect to speech recognition. Try Google Chrome, or type below.' : event.error === 'not-allowed' || event.error === 'service-not-allowed' ? 'Microphone access was denied. Allow it in browser settings, or type below.' : `Speech recognition stopped (${event.error}). Start the conversation again or type below.`);
    };
    mic.onend = () => {
      if (recognition.current !== mic) return;
      recognition.current = null;
      setInterim('');
      emptyStarts.current = !heardSpeech && (!startedAt || Date.now() - startedAt < 1000)
        ? emptyStarts.current + 1 : 0;
      if (emptyStarts.current >= 3) {
        stopConversation();
        setError('Speech recognition stopped repeatedly. Try Google Chrome, or type below.');
      } else {
        resumeMic();
      }
    };
    try { mic.start(); } catch {
      stopConversation();
      setError('Could not start the microphone. Try again or type below.');
    }
  }

  function toggleConversation() {
    if (conversation.current) {
      if (request.current) request.current.allowSpeech = false;
      stopConversation();
      return;
    }
    stopReply();
    conversation.current = true;
    setConversationOn(true);
    emptyStarts.current = 0;
    setError('');
    setStatus('Getting the microphone ready…');
    openMic();
  }

  return <section data-demo-feature="voice" className="voice-agent" aria-label="NOSH voice assistant">
    <h2>Cook with NOSH</h2>
    <p>Start a conversation once, then ask cooking questions or say “next step” as you cook.</p>
    <div className="voice-controls">
      <button disabled={!Recognition || (!conversationOn && busy) || !window.isSecureContext} aria-pressed={conversationOn} onClick={toggleConversation}>
        {conversationOn ? <><LuSquare aria-hidden="true" /> Stop conversation</> : <><LuMic aria-hidden="true" /> Start conversation</>}
      </button>
      <button onClick={() => {
        if (reply.current) { stopReply(); resumeMic(); }
      }}>Stop speaking</button>
      <label><input type="checkbox" checked={spoken} onChange={event => {
        const checked = event.target.checked;
        latest.current.spoken = checked;
        setSpoken(checked);
        if (!checked && reply.current) { stopReply(); resumeMic(); }
      }} /> Speak replies</label>
    </div>
    {window.speechSynthesis && <div className="voice-controls">
      {voices.length > 0 && <label className="voice-selector-row">Reply voice
        <select value={voices.some(voice => voice.voiceURI === voiceURI) ? voiceURI : ''} onChange={event => {
          const value = event.target.value;
          setVoiceURI(value);
          latest.current.selectedVoice = voices.find(voice => voice.voiceURI === value) ?? voices[0];
          try { window.localStorage.setItem(VOICE_KEY, value); } catch { /* Use the selection for this visit. */ }
        }}>
          <option value="">Automatic ({voices[0].name})</option>
          {voices.map(voice => <option key={voice.voiceURI} value={voice.voiceURI}>{voice.name} ({voice.lang})</option>)}
        </select>
      </label>}
      <button disabled={busy} onClick={() => {
        if (!request.current) speakReply('Hi, I’m NOSH. When you’re ready, say next step and we’ll keep cooking.');
      }}>Preview voice</button>
    </div>}
    {busy && <button onClick={() => {
      if (request.current) {
        request.current.cancelled = true;
        request.current.abort();
      }
    }}>Cancel request</button>}
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
      {['Start cooking', 'Previous step', 'Next step', 'Repeat'].map(command => <button key={command} disabled={busy} onClick={() => void send(command)}>{command}</button>)}
    </div>
    {activeRecipe && <CookingFeedback key={activeRecipe} recipeTitle={activeRecipe.split("\n")[0].replace(/^Recipe Name:\s*/i, "").slice(0, 200)} />}
  </section>;
}
