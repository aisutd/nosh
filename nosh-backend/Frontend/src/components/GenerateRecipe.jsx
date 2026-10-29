import { authHeaders } from '../lib/api';
import { useEffect, useRef, useState } from "react";

const API = `http://${window.location.hostname}:8000`;

export default function GenerateRecipe({ ingredients, onOptions }) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const activeRequest = useRef(null);

  useEffect(() => () => activeRequest.current?.abort(), []);

  async function generate(event) {
    event.preventDefault();
    if (activeRequest.current || ingredients.length === 0) return;
    const controller = new AbortController();
    activeRequest.current = controller;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${API}/recipes/options`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ ingredients, user_query: query }),
        signal: controller.signal,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = data?.detail;
        throw new Error(typeof detail === "string" ? detail : "Could not generate a recipe. Please try again.");
      }
      if (!data?.status) throw new Error("The server returned an unexpected recipe response.");
      onOptions(data, { ingredients: [...ingredients], user_query: query });
    } catch (err) {
      if (err.name !== "AbortError") setError(err.message || "Could not reach the recipe service.");
    } finally {
      activeRequest.current = null;
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  const safeSource = /^https?:\/\//i.test(result?.source_url || "") ? result.source_url : null;

  return (
    <section className="generated-recipe">
      <form onSubmit={generate}>
        <label htmlFor="cooking-request">What would you like to make? (optional)</label>
        <input
          id="cooking-request"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="For example, make lemonade"
          disabled={loading}
          style={{ display: "block", width: "100%", boxSizing: "border-box", margin: "12px 0", padding: "12px" }}
        />
        <button className="btn-primary" type="submit" disabled={loading || ingredients.length === 0}>
          {loading ? "Finding a recipe…" : "Find Recipes"}
        </button>
      </form>
      {loading && <p role="status">Finding recipes that match your pantry. This may take a moment.</p>}
      {error && <p role="alert">{error}</p>}
      <div aria-live="polite">
        {result?.status === "ok" && result.recipe ? (
          <>
            <h2>{result.source_recipe || "Your recipe"}</h2>
            <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{result.recipe}</p>
            {safeSource && <a href={safeSource} target="_blank" rel="noreferrer">View source recipe</a>}
          </>
        ) : result && <p>{result.message || "No recipe could be generated. Try adjusting your ingredients or request."}</p>}
      </div>
    </section>
  );
}
