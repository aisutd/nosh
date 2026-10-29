import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { memoryRequest } from '../lib/api';
import './CookingMemory.css';

const defaults = { skill_level: 'beginner', dietary_preferences: [], avoided_ingredients: [], difficulties: [], guidance: 'balanced' };
const listFields = [['dietary_preferences', 'Dietary preferences', 'For example, vegetarian, dairy-free'], ['avoided_ingredients', 'Ingredients you prefer to avoid', 'For example, mushrooms, olives'], ['difficulties', 'Cooking skills you want help with', 'For example, chopping, timing multiple pans']];

function PreferencesForm({ initial, onSaved }) {
  const [values, setValues] = useState({ ...initial, ...Object.fromEntries(listFields.map(([key]) => [key, initial[key].join(', ')])) });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  async function save(event) {
    event.preventDefault(); setBusy(true); setNotice('');
    try {
      const preferences = { ...values, ...Object.fromEntries(listFields.map(([key]) => [key, values[key].split(',').map(item => item.trim()).filter(Boolean)])) };
      const data = await memoryRequest('/preferences', { method: 'PUT', body: JSON.stringify(preferences) });
      onSaved(data.preferences); setNotice('Preferences saved. Future recipe searches and cooking answers will use them.');
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  }
  return <form onSubmit={save} className="memory-form">
    <label>Cooking confidence<select value={values.skill_level} onChange={event => setValues({ ...values, skill_level: event.target.value })}>
      <option value="beginner">Beginner — explain the basics</option><option value="intermediate">Intermediate — some cooking experience</option><option value="confident">Confident — comfortable in the kitchen</option>
    </select></label>
    <label>Instruction detail<select value={values.guidance} onChange={event => setValues({ ...values, guidance: event.target.value })}>
      <option value="detailed">Detailed</option><option value="balanced">Balanced</option><option value="concise">Concise</option>
    </select></label>
    {listFields.map(([key, label, placeholder]) => <label key={key}>{label}<input value={values[key]} maxLength={1000} placeholder={placeholder} onChange={event => setValues({ ...values, [key]: event.target.value })} /><small>Separate items with commas.</small></label>)}
    <p>These preferences guide suggestions; they do not verify allergens or dietary suitability. Check the source ingredients and labels for your needs.</p>
    <button className="btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save preferences'}</button>
    <p role="status">{notice}</p>
  </form>;
}

export default function CookingMemory() {
  const [memory, setMemory] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [clearing, setClearing] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    memoryRequest('', { signal: controller.signal }).then(data => { if (!controller.signal.aborted) setMemory(data); }).catch(err => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, []);
  async function clear() {
    setBusy(true); setError('');
    try { setMemory(await memoryRequest('', { method: 'DELETE' })); setClearing(false); setNotice('Cooking memory cleared.'); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="cooking-memory">
    <h2>Your cooking memory</h2>
    <p>NOSH remembers only the preferences and session feedback you save here. Your latest eight sessions help tailor future instructions. You control your skill level as you grow.</p>
    {error && <p role="alert">{error}</p>}
    <p role="status">{notice}</p>
    {!memory && !error && <p role="status">Loading your cooking memory…</p>}
    {memory && <>
      <PreferencesForm key={JSON.stringify(memory.preferences)} initial={memory.preferences || defaults} onSaved={preferences => { setMemory(current => ({ ...current, preferences })); setNotice('Preferences saved. Future cooking sessions will use them.'); }} />
      <h3>Past cooking sessions</h3>
      {memory.sessions.length === 0 ? <p>No feedback saved yet. After cooking, use “How did cooking go?” on a recipe page.</p> : <ul className="memory-history">{[...memory.sessions].reverse().map(item => <li key={item.id}>
        <strong>{item.recipe_title}</strong> — {item.rating}/5 · {item.outcome.replaceAll('_', ' ')}<br />
        <small>{new Date(item.created_at).toLocaleDateString()}</small>
        {item.difficulty && <p>Needed help with: {item.difficulty}</p>}{item.feedback && <p>{item.feedback}</p>}
      </li>)}</ul>}
      <p>Up to 30 recent sessions are stored in your account. Logging out keeps them for your next visit.</p>
      {clearing ? <div><p>Clear your preferences and all saved session feedback?</p><button disabled={busy} onClick={clear}>Clear cooking memory</button> <button disabled={busy} onClick={() => setClearing(false)}>Cancel</button></div> : <button onClick={() => setClearing(true)}>Reset cooking memory</button>}
    </>}
  </section>;
}

export function CookingFeedback({ recipeTitle }) {
  const [values, setValues] = useState({ recipe_title: recipeTitle, outcome: 'completed', rating: 3, difficulty: '', feedback: '' });
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  if (!localStorage.getItem('access_token')) return <p><Link to="/auth">Log in</Link> to save cooking preferences and session feedback.</p>;
  async function submit(event) {
    event.preventDefault(); if (busy || saved) return;
    setBusy(true); setError('');
    try { await memoryRequest('/sessions', { method: 'POST', body: JSON.stringify(values) }); setSaved(true); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="cooking-memory"><h3>How did cooking go?</h3>
    <p>Save feedback so NOSH can help with past difficulties in future sessions.</p>
    {saved ? <p role="status">Feedback saved. View your history in <Link to="/profile">Profile</Link>.</p> : <form className="memory-form" onSubmit={submit}>
      <label>Recipe name<input required maxLength={200} value={values.recipe_title} onChange={event => setValues({ ...values, recipe_title: event.target.value })} /></label>
      <label>Session outcome<select value={values.outcome} onChange={event => setValues({ ...values, outcome: event.target.value })}><option value="completed">Completed</option><option value="needed_help">Needed help</option><option value="not_finished">Didn't finish</option></select></label>
      <label>How was the recipe?<select value={values.rating} onChange={event => setValues({ ...values, rating: Number(event.target.value) })}>{[1, 2, 3, 4, 5].map(rating => <option key={rating} value={rating}>{rating} / 5</option>)}</select></label>
      <label>What was difficult?<textarea maxLength={500} value={values.difficulty} onChange={event => setValues({ ...values, difficulty: event.target.value })} placeholder="For example, knowing when the pan was ready" /></label>
      <label>What should NOSH remember for next time?<textarea maxLength={1000} value={values.feedback} onChange={event => setValues({ ...values, feedback: event.target.value })} /></label>
      <button className="btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save session feedback'}</button>
      {error && <p role="alert">{error}</p>}
    </form>}
  </section>;
}
