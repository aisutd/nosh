import { request } from '../lib/api';
import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { LuX, LuHeart } from "react-icons/lu";



function Swipe({ recipes, onToggleSave, savedIds, ragSearch }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [browseError, setBrowseError] = useState('');
  const [browse, setBrowse] = useState([]);
  const [index, setIndex] = useState(0);
  const [dragX, setDragX] = useState(0);           // how far the card is dragged
  const [dragging, setDragging] = useState(false);
  const startX = useRef(0);                         // where the drag started

  useEffect(() => {
    if (ragSearch || recipes.length > 0) return;
    const controller = new AbortController();
    request('/recipes/browse?limit=20', { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setBrowse(data); })
      .catch(err => { if (!controller.signal.aborted) setBrowseError(err.message); });
    return () => controller.abort();
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

  function onPointerDown(e) {
    e.currentTarget.setPointerCapture(e.pointerId); // keep tracking even if the pointer leaves the card
    startX.current = e.clientX;
    setDragging(true);
  }

  function onPointerMove(e) {
    if (dragging) setDragX(e.clientX - startX.current);
  }

  function onPointerUp() {
    if (!dragging) return;
    setDragging(false);
    const moved = dragX;
    setDragX(0);                                    // snap back
    if (moved > 100) like();                        // dragged right = save
    else if (moved < -100) next();                  // dragged left = skip
  }

  return (
    <main className="swipe">
      <h1 className="swipe-title">On the menu</h1>
      <p className="section-intro">Pick something you’d love to cook.</p>
      {browseError && <p role="alert">{browseError}</p>}
      {error && <p role="alert">{error}</p>}

      {recipe ? (
        <>
          <div
            className="swipe-card"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
            style={{
              transform: `translateX(${dragX}px) rotate(${dragX / 20}deg)`,   // slides and tilts
              transition: dragging ? "none" : "transform 0.2s",               // smooth snap-back
              touchAction: "pan-y",                                           // allow scrolling up/down, but not sideways
            }}
          > 
            {dragX > 40 && (
              <span className="stamp stamp-yes" style={{ opacity: Math.min(dragX / 100, 1) }}>SAVE</span>
            )}
            {dragX < -40 && (
              <span className="stamp stamp-no" style={{ opacity: Math.min(-dragX / 100, 1) }}>SKIP</span>
            )}
          <h2>{recipe.title}</h2>
            {ragSearch ? <>
              {recipe.image && /^https?:\/\//i.test(recipe.image) && <img src={recipe.image} alt={recipe.title} className="swipe-card-image" />}
              <p>{recipe.total_time || "Time not listed"}</p>
              <p>{recipe.ingredients}</p>
              {/^https?:\/\//i.test(recipe.source_url || "") && <a href={recipe.source_url} target="_blank" rel="noreferrer">Source recipe</a>}
              <Link className="recipe-cook-link" to={`/cook/rag/${encodeURIComponent(recipe.id)}`} state={{ ...ragSearch, title: recipe.title }} onPointerDown={event => event.stopPropagation()}>Cook this recipe →</Link>
              <p className="swipe-card-position">Option {index + 1} of {deck.length}</p>
            </> : <p>{recipe.ingredients.length} ingredients</p>}
          </div>
          <div className="swipe-actions">
            <button className="swipe-btn" onClick={next} disabled={saving} aria-label="Skip"><LuX size={28} /></button>
            <button className="swipe-btn swipe-like" onClick={like} disabled={saving} aria-label="Save"><LuHeart size={28} /></button>
          </div>
        </>
      ) : (
        <div><p>{deck.length === 0 ? (ragSearch ? ragSearch.message : browseError ? "Return to your pantry to try again." : "Loading recipe suggestions…") : "No more recipes."}</p>
          {deck.length > 0 && <button onClick={() => setIndex(0)}>Review options again</button>}
          <p><Link to="/pantry">Back to pantry</Link></p></div>
      )}
    </main>
  );
}

export default Swipe;