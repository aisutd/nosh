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
return <RagCook savedId={id} title={recipe.title} image={recipe.image} ingredients={recipe.ingredients} sourceRecipe={recipe} />;
}

export default Cook;