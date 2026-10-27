import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

const API = `http://${window.location.hostname}:8000`;

export default function RagCook({ savedId = null, title = null, sourceRecipe = null }) {
  const { id } = useParams();
  const { state: context } = useLocation();
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!savedId && !context?.ingredients) return;
    const controller = new AbortController();
    async function generate() {
      setLoading(true); setResult(null); setError("");
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

  const source = sourceRecipe || result?.recipes?.[0];
  const rawIngredients = source?.ingredients || source?.metadata?.ingredients;
  const sourceIngredients = Array.isArray(rawIngredients) ? rawIngredients.join(", ") : rawIngredients;
  const substitutions = result?.recipes?.[0]?.substitutions || result?.substitutions || [];

  return <main className="page cook">
    <Link to={savedId ? "/saved" : "/swipe"}>{savedId ? "Back to saved recipes" : "Back to recipe options"}</Link>
    <h1>{title || context?.title || "Selected recipe"}</h1>
    {sourceIngredients && <section aria-label="Source ingredients">
      <h2>Source ingredients</h2>
      <p>{sourceIngredients}</p>
      <p>These are the original recipe ingredients, before pantry substitutions.</p>
    </section>}
    {substitutions.length > 0 && <section aria-label="Suggested substitutions">
      <h2>Suggested substitutions</h2>
      <ul>{substitutions.map((swap) => <li key={swap.ingredient}>
        {swap.ingredient} → {swap.replacement_ingredients.join(" + ")}. {swap.instructions} {swap.limitations}
      </li>)}</ul>
    </section>}
    {!savedId && !context?.ingredients && <p>Please <Link to="/pantry">search from your pantry</Link> to choose a recipe.</p>}
    {loading && <p role="status">Preparing and validating instructions for your selected recipe…</p>}
    {error && <div role="alert"><p>{error}</p><button onClick={() => setAttempt(attempt + 1)}>Try again</button></div>}
    {result && (result.status === "ok" && result.recipe ? <>
      <p style={{ whiteSpace: "pre-wrap" }}>{result.recipe}</p>
      {/^https?:\/\//i.test(result.source_url || "") && <a href={result.source_url} target="_blank" rel="noreferrer">Source recipe</a>}
    </> : <div role="status">
      <p>{result.message}</p>
      {result.status === "failed_validation" && <button onClick={() => setAttempt(attempt + 1)}>Try instructions again</button>}
    </div>)}
  </main>;
}
