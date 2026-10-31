import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { LuMic, LuArrowLeft } from "react-icons/lu";
const API = `http://${window.location.hostname}:8000`;

export default function RagCook({ savedId = null, title = null, image = null, ingredients = []}) {
  const { id } = useParams();
  const { state: context } = useLocation();
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [talking, setTalking] = useState(false);
  const [cooked, setCooked] = useState(null);       // the consume result, once marked as cooked
  const [cooking, setCooking] = useState(false);
  const steps = (result?.recipe || "")
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean)
    // drop the header lines and the "- none" under Changes
    .filter((s) => !/^(recipe name|changes|steps)\s*:/i.test(s) && !/^-\s*none/i.test(s))
    // remove numbers the model added itself ("1. ", "2) ")
    .map((s) => s.replace(/^\d+[.)]\s*/, ""));

  useEffect(() => {
    if (!savedId && !context?.ingredients) return;
    const controller = new AbortController();
    setLoading(true); setResult(null); setError("");
    async function generate() {
      try {
        const response = await fetch(savedId ? `${API}/recipes/saved-generate/${encodeURIComponent(savedId)}` : `${API}/recipes/generate-selected`, {
          method: "POST", headers: { "Content-Type": "application/json", ...(savedId ? { Authorization: `Bearer ${localStorage.getItem("access_token") || ""}` } : {}) },
          body: savedId ? undefined : JSON.stringify({ recipe_id: id, ingredients: context.ingredients, user_query: context.user_query }),
          signal: controller.signal,
        });
        const data = await response.json().catch(() => null);
        if (!response.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Could not generate instructions.");
        if (!data?.result?.status) throw new Error("Unexpected recipe response.");
        if (!controller.signal.aborted) setResult(data.result);
      } catch (err) {
        if (!controller.signal.aborted) setError(err.message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    // Defer to avoid duplicate generation during React StrictMode's effect check.
    const timer = setTimeout(generate, 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [id, context, attempt, savedId]);

  const photo = image || context?.image;

  // tell the backend this recipe is done, so it subtracts the ingredients from the inventory
  async function handleCooked() {
    setCooking(true);
    try {
      const res = await fetch(`${API}/inventory/consume`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token") || ""}`,
        },
        body: JSON.stringify({ ingredients }),
      });
      if (res.ok) setCooked(await res.json());
      else setError("Could not update your inventory. Are you logged in?");
    } finally {
      setCooking(false);
    }
  }

  return <main className="page cook">
    <Link className="back-link" to={savedId ? "/saved" : "/swipe"}>
      <LuArrowLeft /> {savedId ? "Saved" : "Back"}
    </Link>
    <div className="cook-hero" style={photo ? { backgroundImage: `url("${photo}")` } : undefined}>
      <h1 className="cook-hero-title">{title || context?.title || "Selected recipe"}</h1>
    </div>

    <div className={`blob ${talking ? "talking" : ""}`} aria-hidden="true">
      <span className="eye" /><span className="eye" />
    </div>
    <p>{talking ? "Listening..." : "Tap to cook hands-free with Nosh."}</p>

    <button className="cta talk-btn" onClick={() => setTalking((t) => !t)}>
      <LuMic /> {talking ? "Stop" : "Talk to Nosh"}
    </button>

    {!savedId && !context?.ingredients && <p>Please <Link to="/pantry">search from your pantry</Link> to choose a recipe.</p>}
    {loading && <p role="status">Preparing and validating instructions for your selected recipe…</p>}
    {error && <div role="alert"><p>{error}</p><button onClick={() => setAttempt(attempt + 1)}>Try again</button></div>}
    {result && (result.status === "ok" && result.recipe ? <>
      <ol className="cook-list">
        {steps.map((step, i) => <li key={i}>{step}</li>)}
      </ol>

      <div className="cook-actions">
        {ingredients.length > 0 && (
          cooked ? (
            <div className="cook-done">
              <p>Inventory updated.</p>
              {cooked.warnings.map((w, i) => <p key={i} className="cook-warning">{w}</p>)}
              <Link to="/inventory">View inventory</Link>
            </div>
          ) : (
            <button className="btn-primary" onClick={handleCooked} disabled={cooking}>
              {cooking ? "Updating..." : "Mark as cooked"}
            </button>
          )
        )}

        {/^https?:\/\//i.test(result.source_url || "") && (
          <a href={result.source_url} target="_blank" rel="noreferrer">Source recipe</a>
        )}
      </div>
    </> : <p>{result.message}</p>)}
  </main>;
}
