import { useId, useState } from "react";
import "./RecipeTabs.css";

export default function RecipeTabs({ ingredients, steps }) {
  const [active, setActive] = useState(0);
  const id = useId();
  const labels = ["Ingredients", "Steps"];
  function navigate(event, index) {
    let next;
    if (event.key === "ArrowRight") next = (index + 1) % 2;
    else if (event.key === "ArrowLeft") next = (index + 1) % 2;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = 1;
    else return;
    event.preventDefault();
    setActive(next);
    document.getElementById(`${id}-tab-${next}`)?.focus();
  }
  return <div className="recipe-tabs">
    <div className="recipe-tabs-bar" role="tablist" aria-label="Recipe details">
      {labels.map((label, index) => <button key={label} type="button"
        role="tab" id={`${id}-tab-${index}`} aria-controls={`${id}-panel-${index}`}
        aria-selected={active === index} tabIndex={active === index ? 0 : -1}
        onClick={() => setActive(index)} onKeyDown={(event) => navigate(event, index)}>
        {label}
      </button>)}
    </div>
    {[ingredients, steps].map((content, index) => <section key={labels[index]}
      role="tabpanel" id={`${id}-panel-${index}`} aria-labelledby={`${id}-tab-${index}`}
      hidden={active !== index} tabIndex={0} className="recipe-tab-panel">
      {content}
    </section>)}
  </div>;
}
