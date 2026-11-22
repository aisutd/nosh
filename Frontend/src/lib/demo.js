export function notifyDemo(feature) {
  if (window.parent === window) return;

  window.parent.postMessage(
    { type: "nosh-demo-feature", feature },
    window.location.origin
  );
}