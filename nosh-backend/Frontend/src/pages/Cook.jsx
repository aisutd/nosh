import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { request } from '../lib/api';
import VoiceAgent from '../components/VoiceAgent.jsx';
import RagCook from './RagCook.jsx';

export default function Cook() {
  const { id } = useParams();
  const [recipe, setRecipe] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    request(`/recipes/${encodeURIComponent(id)}`, { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setRecipe(data); })
      .catch(err => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [id, attempt]);
  if (!recipe) return <main className="page"><Link to="/saved">← Saved recipes</Link>{error ? <div role="alert"><p>{error}</p><button onClick={() => setAttempt(value => value + 1)}>Try again</button></div> : <p role="status">Opening your recipe…</p>}</main>;
  if (recipe.kind === 'rag') return <RagCook savedId={id} title={recipe.title} />;
  const text = `${recipe.title}\nIngredients\n${recipe.ingredients.join('\n')}\nInstructions\n${recipe.directions.map((step, index) => `${index + 1}. ${step}`).join('\n')}`;
  return <main className="page cook"><Link to="/saved">← Saved recipes</Link><h1 className="cook-title">{recipe.title}</h1>
    <section className="recipe-sheet"><h2>Ingredients</h2><ul>{recipe.ingredients.map((item, index) => <li key={index}>{item}</li>)}</ul><h2>Method</h2><ol>{recipe.directions.map((step, index) => <li key={index}>{step}</li>)}</ol></section>
    <VoiceAgent key={id} ingredients={recipe.ingredients} recipe={text} />
  </main>;
}
