import { LuCheck, LuShoppingBasket, LuArrowRightLeft, LuLeaf } from "react-icons/lu";
import "./RecipeIngredients.css";

export default function RecipeIngredients({ availability }) {
  if (!availability) return null;
  const { available_ingredients: present = [], missing_ingredients: missing = [],
    unresolved_ingredients: unresolved = [], substitutions = [], assumed_staples: staples = [],
    pantry_match: pantryMatch, coverage } = availability;
  const required = availability.required_ingredients ?? [...new Set([...present, ...missing])];
  const percent = (value) => Number.isFinite(value) ? `${Math.floor(value * 100)}%` : "—";
  return <section className="recipe-availability" aria-label="Ingredient availability">
    <header className="ra-heading">
      <div><p className="ra-eyebrow">YOUR PANTRY & THIS RECIPE</p><h3>What you have. What you need.</h3></div>
      <div className="ra-matches">
        <span><strong>{percent(pantryMatch)}</strong> in pantry</span>
        <span><strong>{percent(coverage)}</strong> with substitutions</span>
      </div>
    </header>
    <div className="recipe-availability-grid">
      <section className="ra-panel ra-primary">
        <header><LuLeaf aria-hidden="true" /><h4>Primary ingredients</h4><span className="ra-count">{required.length}</span></header>
        <p className="ra-description">{present.length} of {required.length} in your pantry</p>
        {required.length ? <ul>{required.map((name) => <li className="ra-ingredient" key={name}>
          <span>{name}</span><span className={`ra-status ${present.includes(name) ? "ra-have" : "ra-missing"}`}>
            {present.includes(name) ? <><LuCheck aria-hidden="true" /> In pantry</> : "Missing"}
          </span>
        </li>)}</ul> : <p className="ra-empty">Only assumed staples are listed for this recipe.</p>}
      </section>
      <section className="ra-panel ra-needed">
        <header><LuShoppingBasket aria-hidden="true" /><h4>Missing items</h4><span className="ra-count">{missing.length}</span></header>
        <p className="ra-description">Check these before you start cooking.</p>
        {missing.length ? <ul>{missing.map((name) => <li key={name} className="ra-missing-item">
          <strong>{name}</strong><span className={`ra-status ${unresolved.includes(name) ? "ra-missing" : "ra-have"}`}>
            {unresolved.includes(name) ? "Still needed" : "Substitute available"}
          </span>
        </li>)}</ul> : <p className="ra-empty"><LuCheck aria-hidden="true" /> No missing items. Your pantry covers the primary ingredients.</p>}
      </section>
      <section className="ra-panel ra-swaps">
        <header><LuArrowRightLeft aria-hidden="true" /><h4>Smart substitutions</h4><span className="ra-count">{substitutions.length}</span></header>
        <p className="ra-description">Alternatives based on your pantry.</p>
        {substitutions.length ? <ul>{substitutions.map((swap, index) => <li key={`${swap.ingredient}-${index}`} className="ra-swap">
          <p className="ra-swap-from">Instead of <strong>{swap.ingredient}</strong></p>
          <p className="ra-swap-to">Use <strong>{swap.replacement_ingredients.join(" + ")}</strong></p>
          <p className="ra-method">{swap.instructions}</p>
          {swap.limitations && <p className="ra-caution">{swap.limitations}</p>}
        </li>)}</ul> : <p className="ra-empty">{missing.length ? "No suitable pantry substitutions found." : "No swaps needed for this recipe."}</p>}
      </section>
    </div>
    <footer className="ra-footnotes">
      {staples.length > 0 && <p><strong>Assumed staples:</strong> {staples.join(", ")}. Excluded from match percentages.</p>}
      <p>Availability checks ingredient presence, not quantities in stock. Check the source list for amounts.</p>
    </footer>
    {unresolved.length > 0 && <p className="ra-notice" role="status"><strong>Still needed:</strong> {unresolved.join(", ")}. Update your pantry and search again before cooking.</p>}
  </section>;
}
