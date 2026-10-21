import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LuX, LuHeart } from "react-icons/lu";

const API = `http://${window.location.hostname}:8000`;

function Swipe({ recipes, onToggleSave, savedIds, ragSearch }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [browse, setBrowse] = useState([]);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (ragSearch || recipes.length > 0) return;
    fetch(`${API}/recipes/browse?limit=20`)
      .then((res) => res.json())
      .then(setBrowse)
      .catch(() => setBrowse([]));
  }, [recipes, ragSearch]);

  const deck = ragSearch || recipes.length > 0 ? recipes : browse;

  const recipe = deck[index];
  const next = () => setIndex((i) => i + 1);

  async function like() {
    if (saving) return;
    setSaving(true); setError("");
    try {
      if (!savedIds.includes(recipe.id)) {
        const saved = await onToggleSave(recipe.id, ragSearch);
        if (saved === false) return;
      }
      next();
    } catch (err) { setError(err.message || "Could not save recipe."); }
    finally { setSaving(false); }
  }

  return (
    <main className="swipe">
      <h1 className="swipe-title">Swipe</h1>
      {error && <p role="alert">{error}</p>}

      {recipe ? (
        <>
          <div className="swipe-card">
            <h2>{recipe.title}</h2>
            {ragSearch ? <>
              {recipe.image && /^https?:\/\//i.test(recipe.image) && <img src={recipe.image} alt={recipe.title} className="swipe-card-image" />}
              <p>{recipe.total_time || "Time not listed"}</p>
              <p>{recipe.ingredients}</p>
              {/^https?:\/\//i.test(recipe.source_url || "") && <a href={recipe.source_url} target="_blank" rel="noreferrer">Source recipe</a>}
              <p className="swipe-card-position">Option {index + 1} of {deck.length}</p>
            </> : <p>{recipe.ingredients.length} ingredients</p>}
          </div>
          <div className="swipe-actions">
            <button className="swipe-btn" onClick={next} disabled={saving} aria-label="Skip"><LuX size={28} /></button>
            <button className="swipe-btn swipe-like" onClick={like} disabled={saving} aria-label="Save"><LuHeart size={28} /></button>
          </div>
        </>
      ) : (
        <div><p>{deck.length === 0 ? (ragSearch ? ragSearch.message : "Loading...") : "No more recipes."}</p>
          {deck.length > 0 && <button onClick={() => setIndex(0)}>Review options again</button>}
          <p><Link to="/pantry">Back to pantry</Link></p></div>
      )}
    </main>
  );
}

export default Swipe;