import { useState, useEffect, useRef} from 'react'
import { Routes, Route, Link, useNavigate, useLocation } from 'react-router-dom'
import './App.css'
import Auth from './pages/Auth.jsx'
import Saved from "./pages/Saved.jsx";
import NavBar from "./components/NavBar.jsx";
import Home from "./pages/Home.jsx";
import Profile from "./pages/Profile.jsx";
import Cook from "./pages/Cook.jsx";
import Swipe from "./pages/Swipe.jsx";
import { BiFoodMenu, BiX, BiPlus } from "react-icons/bi";
import { LuCamera } from "react-icons/lu";
import RagCook from "./pages/RagCook.jsx";
import GenerateRecipe from "./components/GenerateRecipe.jsx";

// Backend address. Uses whatever host the page was opened from, so it works on localhost and on the LAN IP
const API = `http://${window.location.hostname}:8000`;

// Adds the login token to a request so the backend knows who you are
function authHeaders() {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};   // visitors send no header
}

function App() {
  // ----- state: values that make the screen update when they change -----
  const [input, setInput] = useState("");              // text typed in the ingredient box
  const [ingredients, setIngredients] = useState([]);  // the pantry list
  const [ragSearch, setRagSearch] = useState(null);
  const [recipes, setRecipes] = useState([]);          // results from "Find Recipes" (shown in Swipe)
  const [user, setUser] = useState(null);              // username, or null if logged out
  const navigate = useNavigate();                      // lets us change pages from code
  const [savedIds, setSavedIds] = useState([]);        // ids of the recipes this user saved
  const fileInput = useRef(null);                      // points at the hidden file picker
  const [scanning, setScanning] = useState(false);     // true while the scan is running
  const location = useLocation();                      // which page we're on
  const hideNav =                                      // hide the nav bar on login and on the visitor landing page
    location.pathname === "/auth" ||
    (location.pathname === "/" && !user);


// ----- login / logout -----

// Asks the backend who owns this token (returns the username)
async function fetchMe(token) {
  const response = await fetch(`${API}/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Not logged in");
  const data = await response.json();
  return data.username;
}

// Called by Auth.jsx after a successful login: store the token and set the user
async function handleLogin(token) {
  localStorage.setItem("access_token", token);
  setUser(await fetchMe(token));
}

// Forget the token and clear everything that belongs to the user
function handleLogout() {
  localStorage.removeItem("access_token");
  setUser(null);
  setIngredients([]);
  setRecipes([]);
  setRagSearch(null);
  setSavedIds([]);
}

// ----- effects: code that runs automatically -----

// On page load: if a token is saved, log the user back in
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
}, []);                                     // [] = only once, when the app first loads

// When the user logs in, load their saved ingredients
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

// When the user logs in, load the ids of their saved recipes (for the heart icons)
useEffect(() => {
  async function loadSaved() {
    if (!user) return;
    const response = await fetch(`${API}/recipes/saved-ids`, { headers: authHeaders() });
    if (response.ok) setSavedIds((await response.json()).saved);
  }
  loadSaved();
}, [user]);

// Phone app only: Mobile/App.js sends the scan result as a "nosh-scan" event
useEffect(() => {
  function onScanResult(e) {
    addItems(e.detail);          // e.detail is the list of ingredients
  }
  window.addEventListener("nosh-scan", onScanResult);
  return () => window.removeEventListener("nosh-scan", onScanResult);   // cleanup so we don't add duplicate listeners
}, [user, ingredients]);


// ----- pantry actions -----

// "Add" button: logged-in users save to the database, visitors just keep it on the page
async function handleAdding(e) {
  e.preventDefault();                        // stop the form from reloading the page
  const item = input.trim().toLowerCase();   // clean the text
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
    setIngredients((prev) => (prev.includes(item) ? prev : [...prev, item]));   // skip duplicates
  }
  setInput("");                              // clear the text box
}

// Heart button: save or unsave a recipe (login required)
async function handleToggleSave(recipeId, context = null) {
  if (!user) {
    navigate("/auth");                 // visitors must log in to save
    return false;
  }
  const action = savedIds.includes(recipeId) ? "unsave" : "save";   // already saved? then unsave
  const response = await fetch(`${API}/recipes/${action}/${recipeId}`, {
    method: "POST",
    headers: { ...authHeaders(), ...(context ? { "Content-Type": "application/json" } : {}) },
    ...(context ? { body: JSON.stringify(context) } : {}),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(typeof data?.detail === "string" ? data.detail : "Could not update saved recipes.");
  }
  if (response.ok) setSavedIds((await response.json()).saved);      // backend returns the updated list
  return true;
}

// X on a chip: remove an ingredient
async function handleRemoving(ingredient) {
  if (user) {
    const response = await fetch(
      `${API}/ingredients/remove?ingredient=${encodeURIComponent(ingredient)}`,
      { method: "POST", headers: authHeaders() }
    );
    if (response.ok) setIngredients((await response.json()).ingredients);
  } else {
    setIngredients((prev) => prev.filter((i) => i !== ingredient));   // keep everything except this one
  }
}

// ----- scanning -----

// Adds several ingredients at once (used by scan results)
async function addItems(items) {
  if (user) {
    let latest = ingredients;
    for (const item of items) {              // one request per item
      const response = await fetch(
        `${API}/ingredients/add?ingredient=${encodeURIComponent(item)}`,
        { method: "POST", headers: authHeaders() }
      );
      if (response.ok) latest = (await response.json()).ingredients;
    }
    setIngredients(latest);
  } else {
    setIngredients((prev) => [...new Set([...prev, ...items])]);   // Set removes duplicates
  }
}

// Scan box clicked: phone app opens its camera, a normal browser opens the file picker
function handleScanClick() {
  if (!user) {
    navigate("/auth");            // scanning needs an account
    return;
  }
  if (window.ReactNativeWebView) {
    // inside the phone app: pass the login token to it
    window.ReactNativeWebView.postMessage(
      JSON.stringify({ type: "scan", token: localStorage.getItem("access_token") })
    );
  } else {
    fileInput.current.click();    // clicks the hidden <input type="file">
  }
}

// A photo was picked in the browser: upload it to /scan and add the ingredients found
async function handleScan(e) {
  const file = e.target.files[0];
  if (!file) return;
  setScanning(true);                       // shows "Scanning..."
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

  // ----- the Pantry page (used at "/" when logged in, and at "/pantry") -----
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

      {/* hidden file picker, opened by the scan box on a normal browser */}
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

      {/* type an ingredient by hand */}
      <form onSubmit={handleAdding} className="add-row">
        <input value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter an ingredient..."
        />
        <button type="submit" className="btn-primary">Add <BiPlus /></button>
      </form>

        {/* the pantry list: one chip per ingredient */}
        <ul className="chips">
          {ingredients.map((ingredient) => (
            <li key={ingredient} className="chip">
              {ingredient}
              <button onClick={() => handleRemoving(ingredient)}><BiX /></button>
            </li>
          ))}
        </ul>
        <GenerateRecipe
          key={JSON.stringify([user, ingredients])}
          ingredients={ingredients}
          onOptions={(data, context) => {
            setRecipes(data.recipes);
            setRagSearch({ ...context, message: data.message });
            navigate("/swipe");
          }}
        />
    </main>
  )  

  // ----- which page shows at which URL -----
  return (    
    <>               
      <Routes>
        <Route path="/" element={user ? home : <Home />} />   {/* logged in: pantry, visitor: landing page */}
        <Route path="/pantry" element={home} />
        <Route path="/auth" element={<Auth onLogin={handleLogin} />} />
        <Route
          path="/saved"
          element={<Saved user={user} savedIds={savedIds} onToggleSave={handleToggleSave} />}
        />
        <Route path="/profile" element={<Profile user={user} onLogout={handleLogout} />} />
        <Route path="/cook/rag/:id" element={<RagCook />} />
        <Route path="/cook/:id" element={<Cook />} />          {/* :id = the recipe id from the URL */}
        <Route path="/swipe" element={<Swipe key={JSON.stringify([recipes, ragSearch])} ragSearch={ragSearch} recipes={recipes} onToggleSave={handleToggleSave} savedIds={savedIds} />} />
      </Routes>
      {!hideNav && <NavBar user={user} />}                     {/* bottom nav bar, hidden on login/landing */}
    </>
  )
}    

export default App