import { useCallback, useEffect, useRef, useState } from 'react';
import { Routes, Route, Link, useNavigate, useLocation } from 'react-router-dom';
import { BiFoodMenu, BiX, BiPlus } from 'react-icons/bi';
import { LuCamera } from 'react-icons/lu';
import { request, authHeaders } from './lib/api';
import './App.css';
import Auth from './pages/Auth.jsx';
import Saved from './pages/Saved.jsx';
import NavBar from './components/NavBar.jsx';
import Home from './pages/Home.jsx';
import Profile from './pages/Profile.jsx';
import Cook from './pages/Cook.jsx';
import Swipe from './pages/Swipe.jsx';
import RagCook from './pages/RagCook.jsx';
import GenerateRecipe from './components/GenerateRecipe.jsx';
import VoiceAgent from './components/VoiceAgent.jsx';

export default function App() {
  const [input, setInput] = useState('');
  const [ingredients, setIngredients] = useState([]);
  const [ragSearch, setRagSearch] = useState(null);
  const [recipes, setRecipes] = useState([]);
  const [user, setUser] = useState(null);
  const [savedIds, setSavedIds] = useState([]);
  const [checking, setChecking] = useState(!!localStorage.getItem('access_token'));
  const [scanning, setScanning] = useState(false);
  const [pantryBusy, setPantryBusy] = useState(false);
  const [error, setError] = useState('');
  const fileInput = useRef(null);
  const mutation = useRef(false);
  const account = useRef(0);
  const navigate = useNavigate();
  const location = useLocation();
  const hideNav = location.pathname === '/auth' || (location.pathname === '/' && !user);

  async function handleLogin(token) {
    const data = await request('/me', { headers: { Authorization: `Bearer ${token}` } });
    account.current++;
    localStorage.setItem('access_token', token);
    setUser(data.username); setError('');
  }
  function handleLogout() {
    account.current++;
    localStorage.removeItem('access_token');
    setUser(null); setIngredients([]); setRecipes([]); setRagSearch(null); setSavedIds([]); setError('');
  }
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    const controller = new AbortController();
    request('/me', { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setUser(data.username); })
      .catch(err => {
        if (controller.signal.aborted) return;
        if (err.status === 401) localStorage.removeItem('access_token');
        setError(err.status === 401 ? 'Your session expired. Please log in again.' : err.message);
      }).finally(() => { if (!controller.signal.aborted) setChecking(false); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    request('/ingredients', { headers: authHeaders(), signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setIngredients(data.ingredients); })
      .catch(err => { if (!controller.signal.aborted) setError(err.message); });
    request('/recipes/saved-ids', { headers: authHeaders(), signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setSavedIds(data.saved); })
      .catch(err => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [user]);

  const addItems = useCallback(async items => {
    if (!Array.isArray(items) || !items.every(item => typeof item === 'string')) throw new Error('Could not read ingredients. Please add them by hand.');
    const clean = [...new Set(items.map(item => item.trim().toLowerCase()).filter(Boolean))];
    const version = account.current;
    if (!user) { setIngredients(previous => [...new Set([...previous, ...clean])]); return; }
    for (const item of clean) {
      if (version !== account.current) return;
      const data = await request(`/ingredients/add?ingredient=${encodeURIComponent(item)}`, { method: 'POST', headers: authHeaders() });
      if (version === account.current) setIngredients(data.ingredients);
    }
  }, [user]);
  useEffect(() => {
    const onScan = event => { addItems(event.detail).catch(err => setError(err.message)); };
    window.addEventListener('nosh-scan', onScan);
    return () => window.removeEventListener('nosh-scan', onScan);
  }, [addItems]);

  async function handleAdding(event) {
    event.preventDefault();
    if (!input.trim() || mutation.current) return;
    mutation.current = true; setPantryBusy(true); setError('');
    try { await addItems([input]); setInput(''); }
    catch (err) { setError(err.message); }
    finally { mutation.current = false; setPantryBusy(false); }
  }
  async function handleRemoving(item) {
    if (mutation.current) return;
    mutation.current = true; setPantryBusy(true); setError('');
    const version = account.current;
    try {
      if (user) {
        const data = await request(`/ingredients/remove?ingredient=${encodeURIComponent(item)}`, { method: 'POST', headers: authHeaders() });
        if (version === account.current) setIngredients(data.ingredients);
      } else setIngredients(previous => previous.filter(value => value !== item));
    } catch (err) { setError(err.message); }
    finally { mutation.current = false; setPantryBusy(false); }
  }
  async function handleToggleSave(recipeId, context = null) {
    if (!user) { navigate('/auth'); return false; }
    const version = account.current;
    const action = savedIds.includes(recipeId) ? 'unsave' : 'save';
    const data = await request(`/recipes/${action}/${encodeURIComponent(recipeId)}`, {
      method: 'POST', headers: { ...authHeaders(), ...(context ? { 'Content-Type': 'application/json' } : {}) },
      ...(context ? { body: JSON.stringify(context) } : {}),
    });
    if (version !== account.current) return false;
    setSavedIds(data.saved); return true;
  }
  function handleScanClick() {
    if (!user) { navigate('/auth'); return; }
    if (window.ReactNativeWebView) window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'scan', token: localStorage.getItem('access_token') }));
    else fileInput.current.click();
  }
  async function handleScan(event) {
    const picker = event.target;
    const file = picker.files[0];
    if (!file || mutation.current) return;
    const version = account.current;
    mutation.current = true; setScanning(true); setError('');
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error('Choose a photo smaller than 10 MB.');
      const form = new FormData(); form.append('image', file);
      const data = await request('/scan', { method: 'POST', headers: authHeaders(), body: form, timeout: 90000 });
      if (version === account.current) await addItems(data.ingredients);
    } catch (err) { setError(err.message); }
    finally { mutation.current = false; setScanning(false); picker.value = ''; }
  }

  const home = <main className="page pantry">
    <div className="topbar">{user ? <span>Hi, {user}</span> : <Link to="/auth" className="login-link">Log in</Link>}<span className="eyebrow">YOUR KITCHEN, SORTED</span></div>
    <header className="page-heading"><h1><BiFoodMenu /> Your pantry</h1><p>A good meal starts with what you have.</p></header>
    <section className="pantry-card" aria-label="Pantry ingredients">
      <input type="file" accept="image/*" capture="environment" ref={fileInput} onChange={handleScan} hidden />
      <button className="scan-box" disabled={scanning || pantryBusy} onClick={handleScanClick}><LuCamera size={28} /><span>{scanning ? 'Reading your photo…' : 'Add ingredients from a photo'}</span><small>Or add them one at a time below.</small></button>
      <form onSubmit={handleAdding} className="add-row"><input aria-label="Ingredient" value={input} maxLength={200} onChange={event => setInput(event.target.value)} placeholder="Try lemon, rice, or spinach" disabled={pantryBusy || scanning} /><button type="submit" className="btn-primary" disabled={pantryBusy || scanning || !input.trim()}>{pantryBusy ? 'Adding…' : <>Add <BiPlus /></>}</button></form>
      <ul className="chips">{ingredients.map(item => <li key={item} className="chip">{item}<button aria-label={`Remove ${item}`} disabled={pantryBusy || scanning} onClick={() => handleRemoving(item)}><BiX /></button></li>)}</ul>
      {ingredients.length === 0 && <p className="empty-hint">Your pantry is empty. Add a few ingredients to find something to cook.</p>}
    </section>
    <GenerateRecipe key={JSON.stringify([user, ingredients])} ingredients={ingredients} onOptions={(data, context) => { setRecipes(data.recipes); setRagSearch({ ...context, message: data.message }); navigate('/swipe'); }} />
    <VoiceAgent key={user || 'visitor'} ingredients={ingredients} />
  </main>;

  return <>
    {error && <div className="app-notice" role="alert"><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss message">×</button></div>}
    {checking ? <main className="page"><p role="status">Opening your kitchen…</p></main> : <Routes>
      <Route path="/" element={user ? home : <Home />} />
      <Route path="/pantry" element={home} />
      <Route path="/auth" element={<Auth onLogin={handleLogin} />} />
      <Route path="/saved" element={<Saved key={user || 'visitor'} user={user} savedIds={savedIds} onToggleSave={handleToggleSave} />} />
      <Route path="/profile" element={<Profile user={user} onLogout={handleLogout} />} />
      <Route path="/cook/rag/:id" element={<RagCook key={`${user}:${location.pathname}`} />} />
      <Route path="/cook/:id" element={<Cook key={`${user}:${location.pathname}`} />} />
      <Route path="/swipe" element={<Swipe key={JSON.stringify([recipes, ragSearch])} ragSearch={ragSearch} recipes={recipes} onToggleSave={handleToggleSave} savedIds={savedIds} />} />
      <Route path="*" element={<main className="page"><h1>Lost your place?</h1><p>Let’s get back to your kitchen.</p><Link className="cta" to="/pantry">Back to pantry</Link></main>} />
    </Routes>}
    {!hideNav && <NavBar user={user} />}
  </>;
}
