import { useState, useEffect, useRef} from 'react'
import { Routes, Route, Link, useNavigate, useLocation } from 'react-router-dom'
import './App.css'
import Recipe from './components/Recipe.jsx'
import Auth from './pages/Auth.jsx'
import Saved from "./pages/Saved.jsx";
import NavBar from "./components/NavBar.jsx";
import Home from "./pages/Home.jsx";
import Profile from "./pages/Profile.jsx";
import Cook from "./pages/Cook.jsx";
import Swipe from "./pages/Swipe.jsx";
import { BiFoodMenu, BiSearch, BiX, BiPlus } from "react-icons/bi";
import { LuCamera } from "react-icons/lu";

const API = `http://${window.location.hostname}:8000`;

function authHeaders() {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function App() {
  const [input, setInput] = useState("");
  const [ingredients, setIngredients] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  const [savedIds, setSavedIds] = useState([]);
  const fileInput = useRef(null);
  const [scanning, setScanning] = useState(false);
  const location = useLocation();
  const hideNav =
    location.pathname === "/auth" ||
    (location.pathname === "/" && !user);
  const [browseRecipes, setBrowseRecipes] = useState([]);



async function fetchMe(token) {
  const response = await fetch(`${API}/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Not logged in");
  const data = await response.json();
  return data.username;
}

async function handleLogin(token) {
  localStorage.setItem("access_token", token);
  setUser(await fetchMe(token));
}

function handleLogout() {
  localStorage.removeItem("access_token");
  setUser(null);
  setIngredients([]);
  setRecipes([]);
  setSavedIds([]);
}

useEffect(() => {
  async function restoreUser() {
    const token = localStorage.getItem("access_token");
    if (!token) return;
    try {
      setUser(await fetchMe(token));
    } catch {
      localStorage.removeItem("access_token");   // expired or invalid token
      setUser(null);
    }
  }
  restoreUser();
}, []);

useEffect(() => {
  async function loadIngredients() {
    if (!user) return;                      // visitors have no saved list
    const response = await fetch(`${API}/ingredients`, { headers: authHeaders() });
    if (response.ok) {
      const data = await response.json();
      setIngredients(data.ingredients);
    }
  }
  loadIngredients();
}, [user]);                                 // run again whenever user changes

useEffect(() => {
  async function loadSaved() {
    if (!user) return;
    const response = await fetch(`${API}/recipes/saved-ids`, { headers: authHeaders() });
    if (response.ok) setSavedIds((await response.json()).saved);
  }
  loadSaved();
}, [user]);

useEffect(() => {
  function onScanResult(e) {
    addItems(e.detail);          // e.detail is the list of ingredients
  }
  window.addEventListener("nosh-scan", onScanResult);
  return () => window.removeEventListener("nosh-scan", onScanResult);
}, [user, ingredients]);

useEffect(() => {
  fetch(`${API}/recipes/browse?limit=20`)
    .then((res) => res.json())
    .then(setBrowseRecipes)
    .catch(() => setBrowseRecipes([]));
}, []);

async function handleAdding(e) {
  e.preventDefault();
  const item = input.trim().toLowerCase();
  if (!item) return;

  if (user) {
    // logged in: save to this user's account
    const response = await fetch(
      `${API}/ingredients/add?ingredient=${encodeURIComponent(item)}`,
      { method: "POST", headers: authHeaders() }
    );
    if (response.ok) setIngredients((await response.json()).ingredients);
  } else {
    // visitor: keep it in the page only
    setIngredients((prev) => (prev.includes(item) ? prev : [...prev, item]));
  }
  setInput("");
}

async function handleToggleSave(recipeId) {
  if (!user) {
    navigate("/auth");                 // visitors must log in to save
    return;
  }
  const action = savedIds.includes(recipeId) ? "unsave" : "save";
  const response = await fetch(`${API}/recipes/${action}/${recipeId}`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (response.ok) setSavedIds((await response.json()).saved);
}

async function handleRemoving(ingredient) {
  if (user) {
    const response = await fetch(
      `${API}/ingredients/remove?ingredient=${encodeURIComponent(ingredient)}`,
      { method: "POST", headers: authHeaders() }
    );
    if (response.ok) setIngredients((await response.json()).ingredients);
  } else {
    setIngredients((prev) => prev.filter((i) => i !== ingredient));
  }
}

async function handleFindingRecipe() {
  if (ingredients.length === 0) return;      // nothing to match yet
  const response = await fetch(`${API}/recipes/find`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ingredients }),
  });
  if (response.ok) {
    setRecipes(await response.json());
    navigate("/swipe");                       // go straight to the cards
  }
}

async function addItems(items) {
  if (user) {
    let latest = ingredients;
    for (const item of items) {
      const response = await fetch(
        `${API}/ingredients/add?ingredient=${encodeURIComponent(item)}`,
        { method: "POST", headers: authHeaders() }
      );
      if (response.ok) latest = (await response.json()).ingredients;
    }
    setIngredients(latest);
  } else {
    setIngredients((prev) => [...new Set([...prev, ...items])]);
  }
}

function handleScanClick() {
  if (!user) {
    navigate("/auth");            // scanning needs an account
    return;
  }
  if (window.ReactNativeWebView) {
    // pass the login token to the phone app
    window.ReactNativeWebView.postMessage(
      JSON.stringify({ type: "scan", token: localStorage.getItem("access_token") })
    );
  } else {
    fileInput.current.click();
  }
}

async function handleScan(e) {
  const file = e.target.files[0];
  if (!file) return;
  setScanning(true);
  const form = new FormData();
  form.append("image", file);              // the name must match `image` in the backend
  const response = await fetch(`${API}/scan`, { method: "POST", headers: authHeaders(), body: form });
  if (response.ok) {
    const data = await response.json();
    await addItems(data.ingredients);
  }
  setScanning(false);
  e.target.value = "";                   // lets you pick the same photo again
}

  const home = (
  <main className="page">
    <div className="topbar">
      {user ? (
        <>
          <span>Hi, {user}</span>
        </>
      ) : (
        <Link to="/auth" className="login-link">Log in</Link>
      )}
    </div>

    <h1><BiFoodMenu /> Nosh</h1>
      <p>The Best Cooking Assistant App frfr</p>
      <input
        type="file"
        accept="image/*"
        capture="environment"
        ref={fileInput}
        onChange={handleScan}
        hidden
      />
      <button className="scan-box" onClick={handleScanClick}>
        <LuCamera size={28} />
        <span>{scanning ? "Scanning..." : "Scan fridge"}</span>
      </button>
      <form onSubmit={handleAdding} className="add-row">
        <input value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter an ingredient..."
        />
        <button type="submit" className="btn-primary">Add <BiPlus /></button>
      </form>
        <ul className="chips">
          {ingredients.map((ingredient) => (
            <li key={ingredient} className="chip">
              {ingredient}
              <button onClick={() => handleRemoving(ingredient)}><BiX /></button>
            </li>
          ))}
        </ul>
        <button className="btn-primary" onClick={handleFindingRecipe}>
          Find Recipes <BiSearch />
        </button>
    </main>
  )  
    const browse = (
    <main className="page">
      <h1>Browse recipes</h1>
      <ul className="recipe-list">
        {browseRecipes.map((recipe) => (
          <Recipe
            key={recipe.id}
            recipe={recipe}
            saved={savedIds.includes(recipe.id)}
            onToggleSave={() => handleToggleSave(recipe.id)}
          />
        ))}
      </ul>
    </main>
  );
  return (    
    <>               
      <Routes>
        <Route path="/" element={user ? home : <Home />} />
        <Route path="/pantry" element={home} />
        <Route path="/auth" element={<Auth onLogin={handleLogin} />} />
        <Route
          path="/saved"
          element={<Saved user={user} savedIds={savedIds} onToggleSave={handleToggleSave} />}
        />
        <Route path="/profile" element={<Profile user={user} onLogout={handleLogout} />} />
        <Route path="/browse" element={browse} />
        <Route path="/cook/:id" element={<Cook />} />
        <Route path="/swipe" element={<Swipe recipes={recipes} onToggleSave={handleToggleSave} savedIds={savedIds} />} />
      </Routes>
      {!hideNav && <NavBar user={user} />}
    </>
  )
}    

export default App
