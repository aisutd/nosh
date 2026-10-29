import VoiceAgent from '../components/VoiceAgent.jsx';
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import RagCook from "./RagCook.jsx";

const API = `http://${window.location.hostname}:8000`;

function Cook() {
  const { id } = useParams();              // the id from the URL: /cook/<id>
  const [recipe, setRecipe] = useState(null);


  useEffect(() => {
    fetch(`${API}/recipes/${id}`)
      .then((res) => (res.ok ? res.json() : null))
      .then(setRecipe);
  }, [id]);

  if (!recipe) return <main className="page"><p>Loading...</p></main>;

  if (recipe.kind === "rag") return <RagCook savedId={id} title={recipe.title} />;

  return (
    <main className="page cook">
      <h1 className="cook-title">{recipe.title}</h1>

      <VoiceAgent key={id} ingredients={recipe.ingredients} recipe={`${recipe.title}\nIngredients\n${recipe.ingredients.join('\n')}\nInstructions\n${recipe.directions.map((step, i) => `${i + 1}. ${step}`).join('\n')}`} />

      <h3>Ingredients</h3>
      <ul className="cook-list">
        {recipe.ingredients.map((item, i) => <li key={i}>{item}</li>)}
      </ul>

      <h3>Steps</h3>
      <ol className="cook-list">
        {recipe.directions.map((step, i) => <li key={i}>{step}</li>)}
      </ol>
    </main>
  );
}

export default Cook;