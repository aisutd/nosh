import RecipeInstructions from '../components/RecipeInstructions.jsx';
import { request } from '../lib/api';
import { authHeaders } from '../lib/api';
import VoiceAgent from '../components/VoiceAgent.jsx';
import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";



export default function RagCook({ savedId = null, title = null }) {
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
        const data = await request(savedId ? `/recipes/saved-generate/${encodeURIComponent(savedId)}` : '/recipes/generate-selected', {
          method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: savedId ? undefined : JSON.stringify({ recipe_id: id, ingredients: context.ingredients, user_query: context.user_query }),
          signal: controller.signal, timeout: 180000,
        });
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

  return <main className="page cook">
    <Link to={savedId ? "/saved" : "/swipe"}>{savedId ? "Back to saved recipes" : "Back to recipe options"}</Link>
    <h1>{title || context?.title || "Selected recipe"}</h1>
    {!savedId && !context?.ingredients && <p>Please <Link to="/pantry">search from your pantry</Link> to choose a recipe.</p>}
    {loading && <p role="status">Getting your recipe ready. This can take a minute…</p>}
    {error && <div role="alert"><p>{error}</p><button onClick={() => setAttempt(attempt + 1)}>Try again</button></div>}
    {result && (result.status === "ok" && result.recipe ? <>
      <RecipeInstructions text={result.recipe} />
      <VoiceAgent key={result.recipe} recipe={result.recipe} ingredients={context?.ingredients || []} />
      {/^https?:\/\//i.test(result.source_url || "") && <a href={result.source_url} target="_blank" rel="noreferrer">Source recipe</a>}
    </> : <p>{result.message}</p>)}
  </main>;
}
