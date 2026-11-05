// Display the approved recipe without altering quantities, text, or step order.
export default function RecipeInstructions({ text }) {
  const match = /(?:^|\n)Steps:\s*\n([\s\S]*)/i.exec(text);
  const steps = match ? match[1].split(/\n(?=\s*\d+[.)]\s)/).map(step => step.replace(/^\s*\d+[.)]\s*/, '').trim()).filter(Boolean) : [];
  return <section className="recipe-sheet" aria-label="Recipe instructions"><h2>Method</h2>
    {steps.length ? <ol>{steps.map((step, index) => <li key={index}>{step}</li>)}</ol> : <p className="recipe-text">{text}</p>}
  </section>;
}
