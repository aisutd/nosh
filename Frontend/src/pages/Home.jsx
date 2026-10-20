import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

const API = `http://${window.location.hostname}:8000`;

function Home() {
  const [recipes, setRecipes] = useState([]);
  const rowRef = useRef(null);
  const pausedRef = useRef(false);

  useEffect(() => {
    const el = rowRef.current;
    if (!el || recipes.length === 0) return;
    const timer = setInterval(() => {
      if (pausedRef.current) return;
      el.scrollLeft += 1;                                   // move 1px
      if (el.scrollLeft >= el.scrollWidth / 2) el.scrollLeft = 0;   // loop back
    }, 30);
    return () => clearInterval(timer);
  }, [recipes]);

  useEffect(() => {
    fetch(`${API}/recipes/browse?limit=10`)
      .then((res) => res.json())
      .then(setRecipes)
      .catch(() => setRecipes([]));
  }, []);

  return (
    <div className="home">
      <header className="home-top">
        <h2 className="logo">nosh<span>.</span></h2>
        <Link to="/auth" className="signin-link">Sign in</Link>
      </header>
        <div className="blob" aria-hidden="true">
        <span className="eye" /><span className="eye" />
        </div>
      <h1 className="hero">Cook what's already in your fridge.</h1>
      <p className="hero-sub">Scan, swipe, and cook.</p>

      <h3 className="row-title">Trending tonight</h3>
        <div
        className="row"
        ref={rowRef}
        onMouseEnter={() => (pausedRef.current = true)}
        onMouseLeave={() => (pausedRef.current = false)}
        onTouchStart={() => (pausedRef.current = true)}
        onTouchEnd={() => (pausedRef.current = false)}
        >
        {[...recipes, ...recipes].map((r, i) => (
            <div className="card" key={`${r.id}-${i}`}>
            <div className="card-img" />
            <p className="card-title">{r.title}</p>
            </div>
        ))}
        </div>

        <Link to="/auth" className="cta">Get started</Link>
    </div>
  );
}

export default Home;