import { API } from '../lib/api';
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LuX, LuHeart, LuChevronUp, LuClock } from "react-icons/lu";
import RecipeIngredients from "../components/RecipeIngredients";



// split "3 lemons, 8 cups cold water, or as needed" into chips,
// keeping fragments like "or as needed" attached to the item before them
function splitIngredients(value) {
  const parts = Array.isArray(value) ? value : String(value || "").split(",");
  const out = [];
  for (const p of parts.map((s) => s.trim()).filter(Boolean)) {
  if (out.length && /^(or |plus |to taste|as needed|divided|for |optional|hulled|chopped|diced|sliced|minced|peeled|melted|softened|crushed|mashed|grated|cubed|halved|quartered|drained|rinsed|cut |finely |thinly |roughly |cooked|beaten|packed|sifted|trimmed|seeded|cored)/i.test(p)) {      out[out.length - 1] += ", " + p;
    } else {
      out.push(p);
    }
  }
  return out;
}

function Swipe({ recipes, onToggleSave, savedIds, ragSearch }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [index, setIndex] = useState(0);
  const [dragX, setDragX] = useState(0);            // how far the card is dragged
  const [dragging, setDragging] = useState(false);
  const startPoint = useRef(null);
  const didDrag = useRef(false);

  const deck = recipes;
  const recipe = deck[index];
  const rawSourceUrl =
    recipe?.source_url ||
    recipe?.url ||
    recipe?.link ||
    recipe?.metadata?.url ||
    "";

  const sourceUrl = rawSourceUrl
    ? /^https?:\/\//i.test(rawSourceUrl)
      ? rawSourceUrl
      : `https://${rawSourceUrl}`
    : "";
  const timingText = recipe?.metadata?.timing || recipe?.timing || "";
  const servingCount =
    recipe?.servings ??
    recipe?.metadata?.servings ??
    timingText.match(/servings:\s*(\d+)/i)?.[1];
  const next = () => setIndex((i) => i + 1);
  const items = splitIngredients(recipe?.ingredients);
  const rawSteps = Array.isArray(recipe?.directions)
    ? recipe.directions
    : String(recipe?.directions || "").split(/\n|(?<=\.)\s+(?=[A-Z])/);

  const cleaned = rawSteps
    .map((s) => String(s).trim().replace(/^\d+[.)]\s*/, ""))   // drop numbers already in the text
    .filter(Boolean);

  // the last item is often a byline ("Chef John"): real steps end with . ! ? or )
  const last = cleaned[cleaned.length - 1];
  const steps = last && !/[.!?)]["']?$/.test(last) ? cleaned.slice(0, -1) : cleaned;

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

  // ----- dragging the card -----
  function onPointerDown(e) {
    if (
      e.target instanceof Element &&
      e.target.closest("button, a, input, select, textarea")
    ) {
      return;
    }

    startPoint.current = { x: e.clientX, y: e.clientY };
    didDrag.current = false;
  }

  function onPointerMove(e) {
    if (!startPoint.current) return;

    const dx = e.clientX - startPoint.current.x;
    const dy = e.clientY - startPoint.current.y;

    // Let vertical movement scroll the page; only start a horizontal card drag.
    if (Math.abs(dy) > Math.abs(dx) || Math.abs(dx) < 8) return;

    if (!didDrag.current) {
      didDrag.current = true;
      e.currentTarget.setPointerCapture(e.pointerId);
    }

    setDragging(true);
    setDragX(dx);
  }

  function onPointerUp() {
    if (!startPoint.current) return;

    const moved = dragX;
    const wasDragged = didDrag.current;

    startPoint.current = null;
    didDrag.current = false;
    setDragging(false);
    setDragX(0);

    if (wasDragged && moved > 100) like();
    else if (wasDragged && moved < -100) next();
  }

  return (
    <main className="swipe">
      <h1 className="swipe-title">Recipes for you</h1>
      {ragSearch && recipe && (
        <div className="swipe-position">
          <span>Recipe</span>
          <strong>{index + 1}</strong>
          <span>of {deck.length}</span>
        </div>
      )}
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
              transform: `translateX(${dragX}px) rotate(${Math.max(-5, Math.min(5, dragX / 40))}deg)`,
              transition: dragging ? "none" : "transform 0.2s",
              touchAction: "pan-y",
              cursor: "default",
            }}
          >
          <div
            className="swipe-photo"
            style={{
              backgroundImage: recipe.image && /^https?:\/\//i.test(recipe.image)
                ? `linear-gradient(to top, rgba(0,0,0,.8), transparent 60%), url("${recipe.image}")`
                : "linear-gradient(135deg, #c34b61, #f5b8c2)",
              backgroundSize: "cover",
              backgroundPosition: "center",
            }}
          >
            {dragX > 40 && <span className="stamp stamp-yes">SAVE</span>}
            {dragX < -40 && <span className="stamp stamp-no">SKIP</span>}

            <div className="swipe-photo-caption">
              <h2>{recipe.title}</h2>
              <p>
                <LuClock /> {recipe.total_time || timingText || "Time not listed"}
                {servingCount && ` · ${servingCount} servings`}
              </p>
            </div>
          </div>

          <div className="swipe-details">
            <h3>Ingredients</h3>
            <div className="sheet-chips">
              {items.map((line, i) => (
                <span key={i} className="sheet-chip">{line}</span>
              ))}
            </div>

            {recipe.availability && (
              <RecipeIngredients availability={recipe.availability} />
            )}

            <h3>Directions</h3>
            {steps.length ? (
              <ol className="sheet-steps">
                {steps.map((step, i) => <li key={i}>{step}</li>)}
              </ol>
            ) : (
              <p>No source instructions available.</p>
            )}

            {sourceUrl && (
            <a
              className="sheet-source"
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => e.stopPropagation()}
            >
              Source recipe
            </a>
            )}
          </div>
        </div>

          <div className="swipe-actions">
            <button className="swipe-btn" onClick={next} disabled={saving} aria-label="Skip"><LuX size={28} /></button>
            <button className="swipe-btn swipe-like" onClick={like} disabled={saving} aria-label="Save"><LuHeart size={28} /></button>
          </div>
        </>
      ) : (
        <div><p>{deck.length === 0? (ragSearch?.message || "Choose ingredients in your pantry and tap Find Recipes."): "No more recipes."}</p>
          {deck.length > 0 && <button onClick={() => setIndex(0)}>Review options again</button>}
          <p><Link to="/pantry">Back to pantry</Link></p></div>
      )}
    </main>
  );
}

export default Swipe;
