import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LuArrowLeft } from "react-icons/lu";

const API = `http://${window.location.hostname}:8000`;
const UNITS = ["count", "lb", "oz", "cup", "tbsp", "tsp", "can", "package", "bottle"];
// stock groups for the summary cards
function authHeaders() {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function Inventory({ user }) {
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("name");        // "name" or "low"
  const [filter, setFilter] = useState("all");      // "all", "low" or "out"
  const outItems = items.filter((i) => i.quantity <= 0);
  const lowItems = items.filter((i) => i.quantity > 0 && i.quantity <= 1);
  // which rows to show for the chosen tab
  // start from the chosen tab, then apply search, then sort
  const base =
    filter === "low" ? lowItems :
    filter === "out" ? outItems :
    items;

  const shown = base
    .filter((i) => i.name.includes(search.trim().toLowerCase()))
    .slice()                                       // copy, so we don't reorder the real list
    .sort((a, b) =>
      sort === "low"  ? a.quantity - b.quantity :
      sort === "high" ? b.quantity - a.quantity :
      a.name.localeCompare(b.name)
    );

  async function load() {
    const res = await fetch(`${API}/inventory`, { headers: authHeaders() });
    if (res.ok) setItems(await res.json());
  }

  useEffect(() => {
    if (user) load();
  }, [user]);

  // add a new item, or set the quantity of an existing one
  async function save(item) {
    await fetch(`${API}/inventory`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(item),
    });
    load();
  }

  if (!user) {
    return (
      <main className="page">
        <h1>Inventory</h1>
        <p>Log in to track what you have.</p>
        <Link to="/auth" className="cta">Log in</Link>
      </main>
    );
  }

  return (
    <main className="page">
      <Link to="/profile" className="inv-back" aria-label="Back to profile">
        <LuArrowLeft size={24} />
      </Link>
      <h1>Inventory</h1>
      {(lowItems.length > 0 || outItems.length > 0) && (
        <div className="inv-alert">
          {outItems.length > 0 && (
            <p><strong>Out:</strong> {outItems.map((i) => i.name).join(", ")}</p>
          )}
          {lowItems.length > 0 && (
            <p><strong>Running low:</strong> {lowItems.map((i) => i.name).join(", ")}</p>
          )}
        </div>
      )}
      <div className="inv-tools">
        <input
          className="inv-search"
          placeholder="Search items"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="inv-sort" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="name">A to Z</option>
          <option value="low">Low to high</option>
          <option value="high">High to low</option>
        </select>
      </div>
      <section className="inv-summary">
        <button
          className={`inv-stat ${filter === "all" ? "active" : ""}`}
          onClick={() => setFilter("all")}
        >
          <strong>{items.length}</strong>
          <span>Items</span>
        </button>
        <button
          className={`inv-stat low ${filter === "low" ? "active" : ""}`}
          onClick={() => setFilter(filter === "low" ? "all" : "low")}
        >
          <strong>{lowItems.length}</strong>
          <span>Low</span>
        </button>
        <button
          className={`inv-stat out ${filter === "out" ? "active" : ""}`}
          onClick={() => setFilter(filter === "out" ? "all" : "out")}
        >
          <strong>{outItems.length}</strong>
          <span>Out</span>
        </button>
      </section>
      <ul className="inv-list">
        {shown.map((item) => (
          <li
            key={item.name}
            className={`inv-item ${item.quantity <= 0 ? "out" : item.quantity <= 1 ? "low" : ""}`}
          >            
          <span className="inv-name">{item.name}</span>
            <input
              className="inv-edit"
              type="number"
              min="0"
              step="any"
              defaultValue={item.quantity}
              onBlur={(e) => save({ ...item, quantity: Number(e.target.value) })}
              onKeyDown={(e) => e.key === "Enter" && e.target.blur()}
            />
            <select
              className="inv-unit-edit"
              value={item.unit}
              onChange={(e) => save({ ...item, unit: e.target.value })}
            >
              {UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>            
          </li>
        ))}
      </ul>
      {shown.length === 0 && <p>Nothing here{filter === "all" ? " yet. Add ingredients in your pantry." : "."}</p>}    </main>
  );
}

export default Inventory;