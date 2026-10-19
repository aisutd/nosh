import { useState } from "react";

function Recipe({ recipe, saved, onToggleSave}) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <li className="recipe">
      <button className="recipe-title" onClick={() => setShowDetails(!showDetails)}>
        {recipe.title}
      </button>

      {showDetails && (
        <div className="recipe-details">
          <h4>Ingredients</h4>
          <ul>
            {recipe.ingredients.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>

          <h4>Directions</h4>
          <ol>
            {recipe.directions.map((step, index) => (
              <li key={index}>{step}</li>
            ))}
          </ol>

          <button className="btn-primary" onClick={onToggleSave}>
            {saved ? "Saved " : "Save"}
          </button>
          <p>
            <a href={recipe.link} target="_blank" rel="noopener noreferrer">
              View original recipe
            </a>
          </p>
        </div>
      )}
    </li>
  );
}

export default Recipe;

