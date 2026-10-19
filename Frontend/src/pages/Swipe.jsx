import { useEffect, useState } from "react";
import { LuX, LuHeart } from "react-icons/lu";

const API = `http://${window.location.hostname}:8000`;

function Swipe({ recipes, onToggleSave, savedIds }) {
  const [browse, setBrowse] = useState([]);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (recipes.length > 0) return;
    fetch(`${API}/recipes/browse?limit=20`)
      .then((res) => res.json())
      .then(setBrowse)
      .catch(() => setBrowse([]));
  }, [recipes]);

  const deck = recipes.length > 0 ? recipes : browse;

  const recipe = deck[index];
  const next = () => setIndex((i) => i + 1);

  function like() {
    if (!savedIds.includes(recipe.id)) onToggleSave(recipe.id);   // saves, or sends visitors to /auth
    next();
  }

  return (
    <main className="swipe">
      <h1 className="swipe-title">Swipe</h1>

      {recipe ? (
        <>
          <div className="swipe-card">
            <h2>{recipe.title}</h2>
            <p>{recipe.ingredients.length} ingredients</p>
          </div>
          <div className="swipe-actions">
            <button className="swipe-btn" onClick={next} aria-label="Skip"><LuX size={28} /></button>
            <button className="swipe-btn swipe-like" onClick={like} aria-label="Save"><LuHeart size={28} /></button>
          </div>
        </>
      ) : (
        <p>{deck.length === 0 ? "Loading..." : "No more recipes."}</p>
      )}
    </main>
  );
}

export default Swipe;