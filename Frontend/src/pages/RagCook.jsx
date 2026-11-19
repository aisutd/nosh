import VoiceAgent from '../components/VoiceAgent.jsx';
import { API, authHeaders } from '../lib/api';
import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { LuArrowLeft, LuUtensils, LuClock } from "react-icons/lu";
import RecipeTabs from "../components/RecipeTabs";
import RecipeIngredients from "../components/RecipeIngredients";
import "./RagCook.css";


export default function RagCook({ savedId = null, title = null, image = null, ingredients = [], sourceRecipe = null}) {
  const { id } = useParams();
  const { state: context } = useLocation();
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [cooked, setCooked] = useState(null);       // the consume result, once marked as cooked
  const [cooking, setCooking] = useState(false);
  const [servings, setServings] = useState(null);   // null = original serving size
  const steps = (result?.recipe?.split(/^Steps:\s*$/m)[1] || "")
    .split("\n").map((s) => s.trim()).filter(Boolean)
    .map((s) => s.replace(/^\d+[.)]\s*/, ""));
  const availability = result?.recipes?.[0]?.availability;
  const substitutions = result?.recipes?.[0]?.substitutions || result?.substitutions || [];
  const rawIngredients = result?.recipes?.[0]?.ingredients || sourceRecipe?.ingredients || ingredients;
  const sourceIngredients = Array.isArray(rawIngredients) ? rawIngredients.join(", ") : rawIngredients;
  const consumptionIngredients = result?.inventory_ingredients ?? (substitutions.length ? null : ingredients);



  useEffect(() => {
    if (!savedId && !context?.ingredients) return;
    const controller = new AbortController();
    async function generate() {
      setLoading(true); setResult(null); setError(""); setCooked(null);
      try {
        const savedUrl = `${API}/recipes/saved-generate/${encodeURIComponent(savedId)}${servings ? `?servings=${servings}` : ""}`;
        const response = await fetch(savedId ? savedUrl : `${API}/recipes/generate-selected`, {
          method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() },
          body: savedId ? undefined : JSON.stringify({ recipe_id: id, ingredients: context.ingredients, user_query: context.user_query, ...(servings ? { servings } : {}) }),
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
  }, [id, context, attempt, savedId, servings]);

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

  return <main className="page cook recipe-detail">
    <div className="recipe-detail-hero">
      <div className="recipe-detail-placeholder" aria-hidden="true"><LuUtensils /></div>
      {photo && /^https?:\/\//i.test(photo) && <img key={photo} src={photo} alt={title || context?.title || "Selected recipe"}
        onError={(event) => { event.currentTarget.style.display = "none"; }} />}
      <Link className="recipe-detail-back" to={savedId ? "/saved" : "/swipe"}>
        <LuArrowLeft aria-hidden="true" /> {savedId ? "My Recipes" : "Back"}
      </Link>
    </div>
    <div className="recipe-detail-content">
      <h1>{title || context?.title || result?.source_recipe || "Selected recipe"}</h1>
      {(sourceRecipe?.total_time || context?.total_time) && <p className="recipe-detail-time">
        <LuClock aria-hidden="true" /> {sourceRecipe?.total_time || context?.total_time}
      </p>}

    {!savedId && !context?.ingredients && <p>Please <Link to="/pantry">search from your pantry</Link> to choose a recipe.</p>}

    <div className="servings-selector">
      <label htmlFor="servings-select">Servings</label>
      <select
        id="servings-select"
        value={servings ?? ""}
        onChange={(e) => { setServings(e.target.value ? Number(e.target.value) : null); setResult(null); }}
      >
        <option value="">Original ({result?.original_servings ?? context?.servings ?? "?"})</option>
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((n) => (
          <option key={n} value={n}>{n}</option>
        ))}
      </select>
    </div>

    {loading && <p role="status" className="rag-cook-loading">
      <span className="rag-cook-spinner" aria-hidden="true" />
      {servings ? `Scaling recipe to ${servings} serving(s)…` : "Preparing and validating instructions for your selected recipe…"}
    </p>}
    {error && <div role="alert"><p>{error}</p><button onClick={() => setAttempt(attempt + 1)}>Try again</button></div>}
    <RecipeTabs key={savedId || id} ingredients={<>
    {sourceIngredients && <section className="recipe-source-ingredients" aria-label="Source ingredients">
      <header><LuUtensils aria-hidden="true" /><h3>Source ingredients</h3></header>
      <p className="recipe-source-note">Original recipe quantities, before pantry substitutions.</p>
      {Array.isArray(rawIngredients) ? <ul>{rawIngredients.map((line, index) => <li key={index}>{line}</li>)}</ul>
        : <p className="recipe-source-text">{sourceIngredients}</p>}
    </section>}
    {availability && <RecipeIngredients availability={availability} />}
    {!availability && substitutions.length > 0 && <section aria-label="Pantry substitutions">
      <h3>Pantry substitutions</h3>
      <ul className="cook-list">{substitutions.map((swap) => <li key={swap.ingredient}>
        <strong>{swap.ingredient} → {swap.replacement_ingredients.join(" + ")}</strong>
        {" "}{swap.instructions} {swap.limitations}
      </li>)}</ul>
    </section>}
      {!sourceIngredients && !availability && <p>{loading ? "Loading ingredient details…" : "Ingredient details are not available."}</p>}
    </>} steps={<>
      {!result && <p>{loading ? "Your steps will appear here once generation finishes." : "No cooking instructions available yet."}</p>}
    {result && (result.status === "ok" && result.recipe ? <>
      <div className="recipe-steps-heading">
        <h2>Let’s get cooking</h2>
      </div>
      <ol className="cook-list recipe-numbered-steps">
        {steps.map((step, i) => <li key={i}>{step}</li>)}
      </ol>

      <VoiceAgent
        key={result.recipe}
        recipe={result.recipe}
        ingredients={context?.ingredients || ingredients}
      />
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
    </>} />
    </div>
  </main>;
}
