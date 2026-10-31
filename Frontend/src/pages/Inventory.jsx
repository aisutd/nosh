import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LuPlus, LuMinus, LuTrash2 } from "react-icons/lu";

const API = `http://${window.location.hostname}:8000`;
const UNITS = ["count", "lb", "oz", "cup", "tbsp", "tsp", "can", "package", "bottle"];
function authHeaders() {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function Inventory({ user }) {
  const [items, setItems] = useState([]);
  const [name, setName] = useState("");
  const [qty, setQty] = useState(1);
  const [unit, setUnit] = useState("count");

  async function load() {
    const res = await fetch(`${API}/inventory`, { headers: authHeaders() });
    if (res.ok) setItems(await res.json());
  }

  // Save a row's quantity and unit, then update the list on screen
  async function saveRow(name, quantity, unit) {
    const response = await fetch(`${API}/inventory`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ name, quantity, unit }),
    });
    if (response.ok) {
      const saved = await response.json();
      setItems((prev) => prev.map((i) => (i.name === name ? saved : i)));
    }
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
/*
  async function remove(itemName) {
    await fetch(`${API}/inventory/${encodeURIComponent(itemName)}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    load();
  } 
*/
  function handleAdd(e) {
    e.preventDefault();
    if (!name.trim()) return;
    save({ name: name.trim().toLowerCase(), quantity: Number(qty), unit });
    setName("");
    setQty(1);
    setUnit("count");
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
      <h1>Inventory</h1>
      <ul className="inv-list">
        {items.map((item) => (
          <li key={item.name} className={`inv-item ${item.quantity <= 1 ? "low" : ""}`}>
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
      {items.length === 0 && <p>Nothing here yet. Add what you have above.</p>}
    </main>
  );
}

export default Inventory;