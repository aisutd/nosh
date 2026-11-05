import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { LuTrash2 } from 'react-icons/lu';
import { request, authHeaders } from '../lib/api';

export default function Saved({ user, savedIds, onToggleSave }) {
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [removing, setRemoving] = useState(null);
  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    async function load() {
      setLoading(true); setError('');
      try { const data = await request('/recipes/saved', { headers: authHeaders(), signal: controller.signal }); if (!controller.signal.aborted) setRecipes(data); }
      catch (err) { if (!controller.signal.aborted) setError(err.message); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load();
    return () => controller.abort();
  }, [user, attempt, savedIds]);
  async function remove(id) {
    setRemoving(id); setError('');
    try { await onToggleSave(id); } catch (err) { setError(err.message); }
    finally { setRemoving(null); }
  }
  if (!user) return <main className="page"><h1>Saved recipes</h1><p>Keep your next meal close at hand.</p><Link to="/auth" className="cta">Log in to see saved recipes</Link></main>;
  const shown = recipes.filter(recipe => savedIds.includes(recipe.id));
  return <main className="liked">
    <h1 className="liked-title">Saved recipes</h1><p className="liked-sub">A little inspiration for your next meal.</p>
    {loading && <p role="status">Loading your recipes…</p>}
    {error && <div role="alert"><p>{error}</p><button onClick={() => setAttempt(value => value + 1)}>Try again</button></div>}
    {!loading && !error && shown.length === 0 && <div className="empty-state"><h2>Your recipe collection starts here.</h2><p>Find a recipe you like and save it for later.</p><Link className="cta" to="/pantry">Find something to cook</Link></div>}
    <div className="liked-grid">{shown.map(recipe => <article className="liked-card" key={recipe.id}>
      <div className="liked-img" style={/^https?:\/\//i.test(recipe.image || '') ? { backgroundImage: `url("${recipe.image}")` } : undefined}>
        <button className="liked-trash" disabled={removing !== null} aria-label={`Remove ${recipe.title} from saved`} onClick={() => remove(recipe.id)}><LuTrash2 size={16} /></button>
      </div>
      <Link className="liked-name" to={`/cook/${encodeURIComponent(recipe.id)}`}>{recipe.title}<span>Start cooking →</span></Link>
    </article>)}</div>
  </main>;
}
