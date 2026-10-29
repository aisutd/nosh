import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { LuX, LuHeart } from "react-icons/lu";

const API = `http://${window.location.hostname}:8000`;

function Swipe({ recipes, onToggleSave, savedIds, ragSearch }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [browse, setBrowse] = useState([]);
  const [index, setIndex] = useState(0);
  const [dragX, setDragX] = useState(0);           // how far the card is dragged
  const [dragging, setDragging] = useState(false);
  const startX = useRef(0);                         // where the drag started

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
      <h1 className="swipe-title">Swipe</h1>
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
              <span className="stamp stamp-yes" style={{ opacity: Math.min(dragX / 100, 1) }}>YESSIR</span>
            )}
            {dragX < -40 && (
              <span className="stamp stamp-no" style={{ opacity: Math.min(-dragX / 100, 1) }}>HECKS NAH</span>
            )}
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