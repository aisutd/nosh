import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LuTrash2 } from "react-icons/lu";

const API = `http://${window.location.hostname}:8000`;

function authHeaders() {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function Saved({ user, savedIds, onToggleSave }) {
  const [recipes, setRecipes] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    if (!user) return;
    fetch(`${API}/recipes/saved`, { headers: authHeaders() })
      .then((res) => (res.ok ? res.json() : []))
      .then(setRecipes);
  }, [user]);

  if (!user) {
    return (
      <main className="page">
        <h1>Liked</h1>
        <p>Log in to see your saved recipes.</p>
        <Link to="/auth" className="cta">Log in</Link>
      </main>
    );
  }

  // only show recipes that are still saved, so removing one disappears instantly
  const shown = recipes.filter((r) => savedIds.includes(r.id));

  return (
    <main className="liked">
      <h1 className="liked-title">Liked</h1>
      <p className="liked-sub">{shown.length} saved recipes</p>

      <div className="liked-grid">
        {shown.map((r) => (
          <div className="liked-card" key={r.id} onClick={() => navigate(`/cook/${r.id}`)}>
            <div
              className="liked-img"
              style={r.image ? { backgroundImage: `url("${r.image}")` } : undefined}>
              <button
                className="liked-trash"
                aria-label="Remove from saved"
                onClick={(e) => {
                  e.stopPropagation();       // don't open the recipe when tapping the trash
                  onToggleSave(r.id);
                }}
              >
                <LuTrash2 size={16} />
              </button>
            </div>
            <p className="liked-name">{r.title}</p>
          </div>
        ))}
      </div>
    </main>
  );
}

export default Saved;