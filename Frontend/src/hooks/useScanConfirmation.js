import { useCallback, useEffect, useRef, useState } from 'react';

export default function useScanConfirmation() {
  const [confirmation, setConfirmation] = useState(null);
  const sequence = useRef(0);
  const dismiss = useCallback(() => setConfirmation(null), []);
  const confirm = useCallback((ingredients, media = null, simulated = false) => {
    const count = new Set(ingredients.map(name => name.trim().toLowerCase()).filter(Boolean)).size;
    const prefix = media === 'image' ? 'Image uploaded and scanned.'
      : media === 'video' ? 'Video uploaded and scanned.' : 'Scan complete.';
    const result = count ? `Found ${count} ingredient${count === 1 ? '' : 's'}.`
      : `No ingredients detected—try a clearer ${media === 'video' ? 'video' : media === 'image' ? 'photo' : 'image or video'}.`;
    setConfirmation({ id: ++sequence.current, message: `${simulated ? 'Simulated: ' : ''}${prefix} ${result}` });
  }, []);
  useEffect(() => {
    if (!confirmation) return;
    const timer = setTimeout(dismiss, 5000);
    return () => clearTimeout(timer);
  }, [confirmation, dismiss]);
  return { confirmation, confirm, dismiss };
}
