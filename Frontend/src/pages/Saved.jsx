import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LuTrash2, LuClock, LuHeart, LuUtensils, LuArrowRight } from "react-icons/lu";
import "./Saved.css";

function isQuickRecipe(recipe) {
  const numeric = recipe.total_time_minutes;
  if (typeof numeric === "number" && Number.isFinite(numeric)) return numeric > 0 && numeric <= 30;
  const value = String(recipe.total_time ?? "").trim().toLowerCase();
  // Require explicit units and a fully understood duration; unknown times stay in All.
  const parts = [...value.matchAll(/(\d+(?:\.\d+)?)\s*(days?|d|hours?|hrs?|h|minutes?|mins?|m)\b/g)];
  if (!parts.length || value.replace(/(\d+(?:\.\d+)?)\s*(days?|d|hours?|hrs?|h|minutes?|mins?|m)\b/g, "").replace(/[,\s]/g, "")) return false;
  const minutes = parts.reduce((sum, part) => sum + Number(part[1]) * (part[2].startsWith("d") ? 1440 : part[2].startsWith("h") ? 60 : 1), 0);
  return minutes > 0 && minutes <= 30;
}

const API = `http://${window.location.hostname}:8000`;

function authHeaders() {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function RecipePhoto({ image }) {
  const [failed, setFailed] = useState(false);
  return image && /^https?:\/\//i.test(image) && !failed
    ? <img src={image} alt="" loading="lazy" onError={() => setFailed(true)} />
    : <span className="saved-photo-placeholder"><LuUtensils aria-hidden="true" /></span>;
}

export default function Saved({ user, savedIds, onToggleSave }) {
  const [filter, setFilter] = useState("all");
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [removing, setRemoving] = useState([]);
  const [removeError, setRemoveError] = useState("");

  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setRecipes([]);
      setError("");
      try {
        const res = await fetch(`${API}/recipes/saved`, { headers: authHeaders(), signal: controller.signal });
        if (!res.ok) throw new Error("Could not load your saved recipes.");
        const data = await res.json();
        if (!Array.isArray(data)) throw new Error("Could not load your saved recipes.");
        if (!controller.signal.aborted) setRecipes(data);
      } catch (err) {
        if (!controller.signal.aborted) setError(err.message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [user, attempt]);

  async function remove(recipe) {
    if (removing.includes(recipe.id)) return;
    setRemoving((ids) => [...ids, recipe.id]);
    setRemoveError("");
    try {
      const result = await onToggleSave(recipe.id);
      if (result === false) throw new Error("Could not remove this recipe. Please try again.");
    } catch (err) {
      setRemoveError(err.message || "Could not remove this recipe. Please try again.");
    } finally {
      setRemoving((ids) => ids.filter((id) => id !== recipe.id));
    }
  }

  const saved = recipes.filter((recipe) => savedIds.includes(recipe.id));
  const shown = filter === "quick" ? saved.filter(isQuickRecipe) : saved;
  return <main className="saved-page">
    <header className="saved-heading">
      <span className="saved-eyebrow">YOUR PERSONAL COOKBOOK</span>
      <h1>My Recipes</h1>
      <p>A little inspiration, saved for later.</p>
    </header>
    {!user ? <section className="saved-empty">
      <LuHeart aria-hidden="true" /><h2>Your favorites belong here</h2>
      <p>Log in to keep your recipes in one place.</p>
      <Link className="saved-cta" to="/auth">Log in <LuArrowRight aria-hidden="true" /></Link>
    </section> : <>
      <div className="saved-collection-label">
        <div className="saved-filters" role="group" aria-label="Filter saved recipes">
          <button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}><LuHeart aria-hidden="true" /> All</button>
          <button type="button" aria-pressed={filter === "quick"} onClick={() => setFilter("quick")}><LuClock aria-hidden="true" /> Quick · ≤30 min</button>
        </div>
        {!loading && !error && <p role="status">{shown.length} {shown.length === 1 ? "recipe" : "recipes"}</p>}
      </div>
      {removeError && <p className="saved-error" role="alert">{removeError}</p>}
      {loading ? <p className="saved-empty" role="status">Loading your cookbook…</p>
        : error ? <div className="saved-empty" role="alert"><p>{error}</p><button className="saved-cta" onClick={() => setAttempt((value) => value + 1)}>Try again</button></div>
        : shown.length ? <ul className="saved-list">
          {shown.map((recipe) => <li className="saved-card" key={recipe.id}>
            <Link className="saved-recipe-link" to={`/cook/${encodeURIComponent(recipe.id)}`}>
              <div className="saved-photo"><RecipePhoto image={recipe.image} /></div>
              <div className="saved-details"><h2>{recipe.title}</h2>
                {recipe.total_time && <p className="saved-time"><LuClock aria-hidden="true" /> {recipe.total_time}</p>}
                <span className="saved-open">View recipe <LuArrowRight aria-hidden="true" /></span>
              </div>
            </Link>
            <button type="button" className="saved-remove" onClick={() => remove(recipe)}
              disabled={removing.includes(recipe.id)} aria-label={`Remove ${recipe.title} from saved recipes`}>
              <LuTrash2 aria-hidden="true" />
            </button>
          </li>)}
        </ul> : filter === "quick" && saved.length > 0 ? <section className="saved-empty">
          <LuClock aria-hidden="true" /><h2>No quick recipes saved yet</h2>
          <p>Quick recipes take 30 minutes or less in total. Recipes without a known time appear under All.</p>
          <button type="button" className="saved-cta" onClick={() => setFilter("all")}>Show all saved recipes</button>
        </section> : <section className="saved-empty"><LuHeart aria-hidden="true" />
          <h2>Your next favorite is waiting</h2><p>Save a recipe while browsing and find it here whenever you’re ready to cook.</p>
          <Link className="saved-cta" to="/swipe">Explore recipes <LuArrowRight aria-hidden="true" /></Link>
        </section>}
    </>}
  </main>;
}
