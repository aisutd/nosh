import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LuX, LuHeart, LuChevronUp, LuChevronDown, LuClock } from "react-icons/lu";

const API = `http://${window.location.hostname}:8000`;

const STAPLES = ["water", "salt", "pepper", "ice"];   // always counted as "have it", same as the RAG side

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

function Swipe({ recipes, onToggleSave, savedIds, ragSearch, pantry = [] }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [browse, setBrowse] = useState([]);
  const [index, setIndex] = useState(0);
  const [open, setOpen] = useState(false);          // is the details sheet open?
  const [dragX, setDragX] = useState(0);            // how far the card is dragged
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
  const next = () => { setIndex((i) => i + 1); setOpen(false); };

  const items = splitIngredients(recipe?.ingredients);
  // "strawberries" -> "strawberry", "eggs" -> "egg", "tomatoes" -> "tomato"
  const stem = (w) => w.replace(/ies$/, "y").replace(/(es|s)$/, "");
  const norm = (s) => s.toLowerCase().split(/[^a-z]+/).filter(Boolean).map(stem).join(" ");

  const substituted = (line) => recipe?.substitutions?.some((swap) =>
    (` ${norm(line)} `).includes(` ${norm(swap.ingredient)} `));
  const haveIt = (line) => !substituted(line) && (
    STAPLES.some((s) => line.toLowerCase().includes(s)) ||
    pantry.some((p) => norm(line).includes(norm(p))));
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
    if (open) return;                               // sheet is open: no swiping
    e.currentTarget.setPointerCapture(e.pointerId);
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
      {ragSearch && recipe && <p className="swipe-position">Option {index + 1} of {deck.length}</p>}
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
              transform: `translateX(${dragX}px) rotate(${dragX / 20}deg)`,
              transition: dragging ? "none" : "transform 0.2s",
              touchAction: "pan-y",
              cursor: open ? "default" : "grab",      
              // the photo fills the whole card, with a dark fade at the bottom so the title is readable
              backgroundImage: recipe.image && /^https?:\/\//i.test(recipe.image)
                ? `linear-gradient(to top, rgba(0,0,0,0.85) 8%, transparent 55%), url("${recipe.image}")`
                : undefined,
              backgroundSize: "cover",
              backgroundPosition: "center",
            }}
          >
            {dragX > 40 && (
              <span className="stamp stamp-yes" style={{ opacity: Math.min(dragX / 100, 1) }}>YESSIR</span>
            )}
            {dragX < -40 && (
              <span className="stamp stamp-no" style={{ opacity: Math.min(-dragX / 100, 1) }}>HECKS NAH</span>
            )}

            {ragSearch ? <>
              <h2>{recipe.title}</h2>
              <p className="swipe-meta"><LuClock /> {recipe.total_time || "Time not listed"}</p>
            </> : <>
              <h2>{recipe.title}</h2>
              <p>{recipe.ingredients.length} ingredients</p>
            </>}

            <button
              className="sheet-toggle"
              onPointerDown={(e) => e.stopPropagation()}     // so tapping it doesn't start a drag
              onClick={() => setOpen((o) => !o)}
              aria-label="Details"
            >
              {open ? <LuChevronDown size={22} /> : <LuChevronUp size={22} />}
            </button>

            {open && (
              <div className="sheet" onPointerDown={(e) => e.stopPropagation()}>
                <h2>{recipe.title}</h2>
                  <p className="sheet-meta">
                    <LuClock /> {recipe.total_time || "Time not listed"}
                    {recipe.servings && <> · {recipe.servings} servings</>}
                  </p>                
                <h3>Ingredients</h3>
                <div className="sheet-chips">
                  {items.map((line, i) => (
                    <span key={i} className={`sheet-chip ${haveIt(line) ? "" : "missing"}`}>{line}</span>
                  ))}
                </div>
                {recipe.substitutions?.length > 0 && <>
                  <h3>Pantry substitutions</h3>
                  <ul className="sheet-steps">
                    {recipe.substitutions.map((swap) => <li key={swap.ingredient}>
                      <strong>{swap.ingredient} → {swap.replacement_ingredients.join(" + ")}</strong>
                      {" "}{swap.instructions} {swap.limitations}
                    </li>)}
                  </ul>
                  <p>Directions below are from the original recipe. Adapted instructions are prepared when you cook.</p>
                </>}
                  {steps.length > 0 && (
                    <>
                      <h3>Directions</h3>
                      <ol className="sheet-steps">
                        {steps.map((s, i) => <li key={i}>{s}</li>)}
                      </ol>
                    </>
                  )}
                {/^https?:\/\//i.test(recipe.source_url || "") && (
                  <a className="sheet-source" href={recipe.source_url} target="_blank" rel="noreferrer">Source recipe</a>
                )}
              </div>
            )}
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