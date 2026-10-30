import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { LuMic, LuArrowLeft } from "react-icons/lu";
const API = `http://${window.location.hostname}:8000`;

export default function RagCook({ savedId = null, title = null, image = null, ingredients = [], sourceRecipe = null}) {
  const { id } = useParams();
  const { state: context } = useLocation();
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [talking, setTalking] = useState(false);
  const [cooked, setCooked] = useState(null);       // the consume result, once marked as cooked
  const [cooking, setCooking] = useState(false);
  const steps = (result?.recipe?.split(/^Steps:\s*$/m)[1] || "")
    .split("\n").map((s) => s.trim()).filter(Boolean)
    .map((s) => s.replace(/^\d+[.)]\s*/, ""));
  const substitutions = result?.recipes?.[0]?.substitutions || result?.substitutions || [];
  const rawIngredients = sourceRecipe?.ingredients || result?.recipes?.[0]?.ingredients || ingredients;
  const sourceIngredients = Array.isArray(rawIngredients) ? rawIngredients.join(", ") : rawIngredients;
  const consumptionIngredients = result?.inventory_ingredients ?? (substitutions.length ? null : ingredients);

  useEffect(() => {
    if (!savedId && !context?.ingredients) return;
    const controller = new AbortController();
    async function generate() {
      setLoading(true); setResult(null); setError(""); setCooked(null);
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
    if (cooking || cooked || !consumptionIngredients?.length) return;
    setCooking(true);
    try {
      const res = await fetch(`${API}/inventory/consume`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token") || ""}`,
        },
        body: JSON.stringify({ ingredients: consumptionIngredients }),
      });
      if (res.ok) setCooked(await res.json());
      else setError("Could not update your inventory. Are you logged in?");
    } catch {
      setError("Could not update your inventory. Please try again.");
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

    {sourceIngredients && <section aria-label="Source ingredients">
      <h3>Source ingredients</h3>
      <p>{sourceIngredients}</p>
    </section>}
    {substitutions.length > 0 && <section aria-label="Pantry substitutions">
      <h3>Pantry substitutions</h3>
      <ul className="cook-list">{substitutions.map((swap) => <li key={swap.ingredient}>
        <strong>{swap.ingredient} → {swap.replacement_ingredients.join(" + ")}</strong>
        {" "}{swap.instructions} {swap.limitations}
      </li>)}</ul>
    </section>}
    {!savedId && !context?.ingredients && <p>Please <Link to="/pantry">search from your pantry</Link> to choose a recipe.</p>}
    {loading && <p role="status">Preparing and validating instructions for your selected recipe…</p>}
    {error && <div role="alert"><p>{error}</p><button onClick={() => setAttempt(attempt + 1)}>Try again</button></div>}
    {result && (result.status === "ok" && result.recipe ? <>
      <ol className="cook-list">
        {steps.map((step, i) => <li key={i}>{step}</li>)}
      </ol>

      <div className="cook-actions">
        {substitutions.length > 0 && !consumptionIngredients && <p className="cook-warning">
          Please update inventory manually for this substitution; its quantities could not be converted reliably.
          {" "}<Link to="/inventory">View inventory</Link>
        </p>}
        {consumptionIngredients?.length > 0 && (
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
    </> : <div role="status"><p>{result.message}</p>
      {result.status === "failed_validation" && <button className="btn-primary" onClick={() => setAttempt(attempt + 1)}>Try instructions again</button>}
    </div>)}
  </main>;
}
