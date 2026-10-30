import "./RecipeIngredients.css";

export default function RecipeIngredients({ availability }) {
  const { available_ingredients: present, missing_ingredients: missing,
    unresolved_ingredients: unresolved, substitutions, assumed_staples: staples,
    pantry_match: pantryMatch, coverage } = availability;
  const percent = (value) => `${Math.floor(value * 100)}%`;
  return <section className="recipe-availability" aria-label="Ingredient availability">
    <p><strong>{percent(pantryMatch)} in pantry</strong> · {percent(coverage)} covered with substitutions</p>
    <div className="recipe-availability-grid">
      <section>
        <h3>Available ingredients</h3>
        {present.length ? <ul>{present.map((name) => <li key={name}>{name}</li>)}</ul> : <p>None</p>}
      </section>
      <section>
        <h3>Missing ingredients</h3>
        {missing.length ? <ul>{missing.map((name) => <li key={name}>
          {name} — {unresolved.includes(name) ? "needed" : "substitute available"}
        </li>)}</ul> : <p>None</p>}
      </section>
      <section>
        <h3>Smart substitutions</h3>
        {substitutions.length ? <ul>{substitutions.map((swap) => <li key={swap.ingredient}>
          <strong>{swap.ingredient} → {swap.replacement_ingredients.join(" + ")}</strong>
          <p>{swap.instructions} {swap.limitations}</p>
        </li>)}</ul> : <p>No substitutions suggested.</p>}
      </section>
    </div>
    {staples.length > 0 && <p>Assumed staples (excluded from match): {staples.join(", ")}.</p>}
    <p>Based on ingredient presence, not quantities in stock.</p>
    {unresolved.length > 0 && <p role="status">Still needed: {unresolved.join(", ")}. Update your pantry and search again before cooking.</p>}
  </section>;
}
