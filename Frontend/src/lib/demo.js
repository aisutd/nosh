export function emitDemo(kind, detail = {}) {
  if (window.parent === window) return;
  window.parent.postMessage({ type: 'nosh-demo', kind, ...detail }, window.location.origin);
}
export const notifyDemo = feature => emitDemo('action', { feature });
export const demoStatus = (operation, status, message = '') => emitDemo('status', { operation, status, message });
export const demoNavigation = path => emitDemo('navigation', { path });

export function featureForTarget(target) {
  return target.closest?.('[data-demo-feature]')?.dataset.demoFeature || null;
}
export function installDemoInteractions() {
  if (window.parent === window) return () => {};
  const handle = event => {
    // Only actual controls and explicit inspection buttons select a topic.
    if (!event.target.closest?.('button, input, select, textarea, summary')) return;
    const feature = featureForTarget(event.target);
    if (feature) notifyDemo(feature);
  };
  document.addEventListener('click', handle, true);
  document.addEventListener('change', handle, true);
  return () => {
    document.removeEventListener('click', handle, true);
    document.removeEventListener('change', handle, true);
  };
}

// Presentation commands are limited to showing the intro dashboard, never logging out.
export function onDemoIntroScreen(showIntro) {
  if (window.parent === window) return () => {};
  function handle(event) {
    if (event.origin !== window.location.origin || event.source !== window.parent) return;
    if (event.data?.type === 'nosh-demo-command' && event.data.command === 'show-intro') showIntro();
  }
  window.addEventListener('message', handle);
  return () => window.removeEventListener('message', handle);
}
