import { useId, useState } from "react";
import { LuTrash2, LuSearch, LuLeaf } from "react-icons/lu";
import "./PantryIngredients.css";

export default function PantryIngredients({ ingredients, onRemove }) {
  const listId = useId();
  const [editing, setEditing] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [selected, setSelected] = useState([]);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmClear, setConfirmClear] = useState(false);
  const current = selected.filter((name) => ingredients.includes(name));
  const shown = ingredients.filter((name) => name.toLowerCase().includes(query.trim().toLowerCase()));
  const searching = query.trim().length > 0;
  const visible = editing || expanded || searching ? shown : shown.slice(0, 6);
  const allVisibleSelected = shown.length > 0 && shown.every((name) => current.includes(name));

  async function remove(names) {
    if (busy) return;
    setBusy(true); setError(""); setConfirmClear(false);
    const failed = [];
    // Sequential updates avoid older API responses overwriting newer pantry state.
    for (const name of names) {
      try { await onRemove(name); }
      catch { failed.push(name); }
    }
    setSelected(failed);
    setError(failed.length ? `Could not remove: ${failed.join(", ")}. Please try again.` : "");
    setBusy(false);
  }

  return <section className="pantry-ingredients" aria-label="Your pantry ingredients" aria-busy={busy}>
    <header><div><h2>Your ingredients <span>{ingredients.length}</span></h2>
      <p>{editing ? "Select ingredients to remove them together." : "Everything you have, ready for your next recipe."}</p></div>
      {ingredients.length > 0 ? <button type="button" className="pantry-edit-toggle" aria-pressed={editing} disabled={busy}
        onClick={() => { setEditing(!editing); setSelected([]); setConfirmClear(false); setError(""); }}>
        {editing ? "Done" : "Edit ingredients"}
      </button> : <LuLeaf aria-hidden="true" />}</header>
    {ingredients.length > 0 ? <>
      <label className="pantry-filter"><LuSearch aria-hidden="true" /><input aria-label="Search pantry ingredients" placeholder="Find an ingredient…" value={query} onChange={(e) => setQuery(e.target.value)} disabled={busy} /></label>
      {editing && <div className="pantry-selection-tools">
        <button type="button" disabled={busy || !shown.length} onClick={() => setSelected(allVisibleSelected ? current.filter((name) => !shown.includes(name)) : [...new Set([...current, ...shown])])}>
          {allVisibleSelected ? "Deselect shown" : query ? "Select shown" : "Select all"}
        </button>
        <span role="status">{current.length} selected</span>
        <button type="button" disabled={busy} onClick={() => setConfirmClear(true)}>Clear all</button>
      </div>}
      <ul id={listId} className={`pantry-ingredient-grid${editing ? "" : " pantry-preview-grid"}`}>{visible.map((name) => <li key={name}>
        {editing ? <label className={current.includes(name) ? "pantry-ingredient selected" : "pantry-ingredient"}>
          <input type="checkbox" checked={current.includes(name)} disabled={busy}
            onChange={(e) => setSelected(e.target.checked ? [...current, name] : current.filter((item) => item !== name))} />
          <span>{name}</span>
        </label> : <div className="pantry-ingredient pantry-preview-item"><span>{name}</span></div>}
      </li>)}</ul>
      {!editing && !searching && ingredients.length > 6 && <button type="button" className="pantry-expand" aria-expanded={expanded} aria-controls={listId} onClick={() => setExpanded(!expanded)}>
        {expanded ? "Show less" : `Show all (${ingredients.length})`}
      </button>}
      {!shown.length && <p className="pantry-empty">No ingredients match your search.</p>}
      {editing && current.length > 0 && <button type="button" className="btn-primary pantry-remove-selected" disabled={busy} onClick={() => remove(current)}><LuTrash2 aria-hidden="true" /> {busy ? "Removing…" : `Remove selected (${current.length})`}</button>}
      {editing && confirmClear && <div className="pantry-clear-confirm" role="group" aria-label="Confirm clearing pantry">
        <p>Remove all {ingredients.length} pantry ingredients and their inventory entries? This includes ingredients hidden by search.</p>
        <button type="button" className="btn-primary" onClick={() => remove([...ingredients])}>Yes, clear pantry</button>
        <button type="button" onClick={() => setConfirmClear(false)}>Cancel</button>
      </div>}
    </> : <p className="pantry-empty">Your pantry is ready for a fresh start. Scan a photo or add an ingredient above.</p>}
    {busy && <p role="status">Updating your pantry…</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
