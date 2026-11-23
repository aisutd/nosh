import { request } from '../lib/api';
import { demoStatus } from '../lib/demo';
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import RagCook from './RagCook.jsx';

export default function Cook() {
  const { id } = useParams();
  const [recipe, setRecipe] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    demoStatus('Open recipe', 'loading', 'Loading saved recipe');
    request(`/recipes/${encodeURIComponent(id)}`, { signal: controller.signal })
      .then(data => {
        if (!controller.signal.aborted) { setRecipe(data); demoStatus('Open recipe', 'success'); }
      }).catch(err => {
        if (!controller.signal.aborted) { setError(err.message); demoStatus('Open recipe', 'error', err.message); }
      });
    return () => controller.abort();
  }, [id, attempt]);
  if (error) return <main className="page"><p role="alert">{error}</p><button onClick={() => { setError(''); setAttempt(value => value + 1); }}>Retry opening recipe</button></main>;
  if (!recipe) return <main className="page"><p>Loading...</p></main>;
  return <RagCook key={id} savedId={id} title={recipe.title} image={recipe.image} ingredients={recipe.ingredients} sourceRecipe={recipe} />;
}
