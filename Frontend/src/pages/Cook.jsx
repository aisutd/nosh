import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import RagCook from "./RagCook.jsx";

const API = `http://${window.location.hostname}:8000`;

function Cook() {
  const { id } = useParams();              // the id from the URL: /cook/<id>
  const [recipe, setRecipe] = useState(null);
  const [talking, setTalking] = useState(false);

  useEffect(() => {
    fetch(`${API}/recipes/${id}`)
      .then((res) => (res.ok ? res.json() : null))
      .then(setRecipe);
  }, [id]);

  // Voice Stuff
  function handleTalk() {
    setTalking((t) => !t);
    // Connect speech-to-text / text-to-speech
  }

  if (!recipe) return <main className="page"><p>Loading...</p></main>;

  if (recipe.kind === "rag") return <RagCook savedId={id} title={recipe.title} sourceRecipe={recipe} />;

  return (
    <main className="page cook">
      <h1 className="cook-title">{recipe.title}</h1>

      <div className={`blob ${talking ? "talking" : ""}`} aria-hidden="true">
        <span className="eye" /><span className="eye" />
      </div>
      <p>{talking ? "Listening..." : "Tap to cook hands-free."}</p>

      <button className="cta talk-btn" onClick={handleTalk}>
        {talking ? "Stop" : "Talk"}
      </button>

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