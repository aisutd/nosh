import ScanConfirmation from './ScanConfirmation';
import useScanConfirmation from '../hooks/useScanConfirmation';
import { useEffect, useState } from 'react';
import { notifyDemo, demoNavigation, demoStatus, onDemoIntroScreen } from '../lib/demo';
import RecipeIngredients from './RecipeIngredients';
import RecipeTabs from './RecipeTabs';
import '../Theme.css';
import './SampleDemo.css';

const availability = { required_ingredients: ['pasta', 'tomato', 'fresh basil'], available_ingredients: ['pasta', 'tomato'], missing_ingredients: ['fresh basil'], unresolved_ingredients: [], pantry_match: 2 / 3, coverage: 1,
  substitutions: [{ ingredient: 'fresh basil', replacement_ingredients: ['dried basil'], instructions: 'Use 1 tsp dried basil in place of 1 tbsp fresh basil.', limitations: 'Add dried herbs earlier; flavor and texture differ.' }] };
const initialStock = { pasta: 500, tomato: 800, 'dried basil': 6 };
const units = { pasta: 'g', tomato: 'g', 'dried basil': 'tsp' };

export default function SampleDemo() {
  const { confirmation, confirm, dismiss } = useScanConfirmation();
  const [screen, setScreen] = useState('pantry');
  const [scanned, setScanned] = useState(false);
  const [saved, setSaved] = useState(false);
  const [servings, setServings] = useState(2);
  const [stock, setStock] = useState(initialStock);
  const [cooked, setCooked] = useState(false);
  const [reply, setReply] = useState('');
  const [step, setStep] = useState(0);
  useEffect(() => onDemoIntroScreen(() => setScreen('intro')), []);
  useEffect(() => { demoNavigation(screen === 'inventory' ? '/inventory' : `/sample/${screen}`); }, [screen]);
  function scan(video) {
    dismiss();
    notifyDemo(video ? 'video' : 'scan');
    setScanned(true);
    confirm(['pasta', 'tomato', 'dried basil'], video ? 'video' : 'image', true);
    demoStatus('Scan', 'success', 'Sample ingredients loaded');
  }
  function cook() {
    if (cooked) return;
    setStock(current => ({ pasta: current.pasta - 100 * servings, tomato: current.tomato - 150 * servings, 'dried basil': current['dried basil'] - .5 * servings }));
    setCooked(true);
    demoStatus('Inventory update', 'success');
  }
  function speak(command) {
    notifyDemo('voice');
    const instructions = ['Boil the pasta in salted water.', 'Simmer tomatoes with dried basil, then toss with pasta.', 'Serve the tomato pasta warm.'];
    if (command === 'Can I use dried basil?') setReply('Yes. Use 1 tsp dried basil per 2 servings and add it while the sauce simmers.');
    else {
      const next = command === 'Next step' ? Math.min(step + 1, 2) : 0;
      setStep(next); setReply(instructions[next]);
    }
  }
  return <main className="sample-demo">
    <ScanConfirmation confirmation={confirmation} onDismiss={dismiss} />
    <header><strong>SAMPLE DEMO · SIMULATED</strong><p>Fixed example. No account changes or live AI requests.</p></header>
    {screen === 'intro' && <section className="home">
      <h2 className="logo">nosh<span>.</span></h2>
      <div className="blob" aria-hidden="true"><span className="eye" /><span className="eye" /></div>
      <h1 className="hero">Your AI cooking buddy.</h1>
      <p className="hero-sub">Good food starts with what’s already in your kitchen.</p>
      <button className="sample-primary" onClick={() => setScreen('pantry')}>Find recipes</button>
      <button onClick={() => setScreen('saved')}>My recipes</button>
    </section>}
    {screen !== 'intro' && <nav aria-label="Sample app navigation"><button onClick={() => setScreen('pantry')}>Pantry</button><button onClick={() => setScreen('saved')}>Saved</button><button onClick={() => setScreen('profile')}>Me</button></nav>}
    {screen === 'pantry' && <section><h1>What’s cooking?</h1><p>Try a simulated scan of a tomato-pasta pantry.</p>
      <button className="sample-primary" onClick={() => { notifyDemo('scan'); setScreen('scan'); }}>Scan fridge</button>
      {scanned && <><h2>Your ingredients</h2><p>Pasta · Tomato · Dried basil</p><button className="sample-primary" onClick={() => { notifyDemo('rag'); setScreen('recipes'); }}>Find Recipes</button></>}
    </section>}
    {screen === 'scan' && <section><h1>Sample scan</h1><p>These preset results simulate detection; no image or video is analyzed.</p>
      <button onClick={() => scan(false)}>Simulate photo scan</button><button onClick={() => scan(true)}>Simulate video scan</button>
      {scanned && <><h2>Detected ingredients</h2><p>Pasta · Tomato · Dried basil</p><button className="sample-primary" onClick={() => setScreen('pantry')}>Review pantry</button></>}
    </section>}
    {screen === 'recipes' && <section><h1>Recipes for you</h1><article><h2>Tomato basil pasta</h2><p>20 minutes · 2 servings</p>
      <RecipeIngredients availability={availability} />
      <button className="sample-primary" onClick={() => { notifyDemo('saving'); setSaved(true); }}>{saved ? 'Recipe saved' : 'Save recipe'}</button>
      <p>Open Saved to select your recipe.</p></article></section>}
    {screen === 'saved' && <section><h1>My Recipes</h1>{saved ? <button className="sample-primary" onClick={() => setScreen('cook')}>Open tomato basil pasta</button> : <p>Save a recipe from your results first.</p>}</section>}
    {screen === 'cook' && <section><h1>Tomato basil pasta</h1><label>Servings <select value={servings} disabled={cooked} onChange={event => { notifyDemo('servings'); setServings(Number(event.target.value)); }}>
      {[1, 2, 3, 4].map(n => <option key={n}>{n}</option>)}</select></label>
      <RecipeTabs ingredients={<><p>{100 * servings} g pasta · {150 * servings} g tomato · {.5 * servings} tsp dried basil</p><RecipeIngredients availability={availability} /></>}
        steps={<><ol><li>Boil pasta.</li><li>Simmer tomatoes with basil; combine.</li><li>Serve warm.</li></ol>
          <h2>Voice guidance · simulated</h2><p>Choose a scripted question. This does not use your microphone or live speech recognition.</p>
          {['Start cooking', 'Next step', 'Can I use dried basil?'].map(command => <button key={command} onClick={() => speak(command)}>{command}</button>)}
          {reply && <p role="status">Sample NOSH reply: {reply}</p>}
          <button className="sample-primary" disabled={cooked} onClick={cook}>{cooked ? 'Inventory updated' : 'Mark as cooked'}</button>
          <button onClick={() => setScreen('inventory')}>My inventory</button>
        </>} />
    </section>}
    {screen === 'profile' && <section><h1>My kitchen</h1><p>Sample account · no real sign-in</p><button className="sample-primary" onClick={() => setScreen('inventory')}>My inventory</button></section>}
    {screen === 'inventory' && <section><h1>Inventory</h1><p>{cooked ? `Sample amounts after cooking ${servings} servings.` : 'Starting sample quantities.'}</p>
      <ul>{Object.entries(stock).map(([name, amount]) => <li key={name}>{name}: {amount} {units[name]}</li>)}</ul>
    </section>}
  </main>;
}
