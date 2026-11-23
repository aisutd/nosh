// Content adapted from the team's Nosh presentation; goals are not measured results.
export const presentationContent = {
  intro: {
    nav: 'Overview', label: 'NOSH · YOUR AI COOKING BUDDY',
    title: 'Your ingredients. Your next meal.',
    description: 'Scan or enter ingredients, discover a recipe, adjust servings, and cook with voice guidance. Click inside the phone to explore the story behind each feature.',
    points: ['Scan → Find recipes → Cook', 'Live web app · Expo Go on mobile', 'Inventory updates after cooking'],
  },
  problem: {
    nav: 'Why NOSH', label: 'THE PROBLEM', title: 'Learning to cook has a high barrier to entry.',
    description: 'Lessons can be expensive, not everyone has someone to teach them, and a fridge full of random ingredients can still lead to takeout.',
    points: ['Costly lessons', 'No one to teach', '“What can I make?”', 'Ingredients spoil before use'],
    note: 'The deck cites a 2020 Penn State analysis: 31.9% of food purchased by U.S. households goes uneaten, about $1,866 per household annually.',
  },
  scan: {
    nav: 'Scan', label: 'COMPUTER VISION', title: 'From your fridge to your pantry.',
    description: 'A trained YOLO model finds ingredients in photos or video. Detections include ingredient labels, bounding boxes, and confidence scores.',
    points: ['Upload a photo or video', 'Review detected ingredients', 'Add ingredients to your pantry'],
    related: ['training', 'video'],
  },
  training: {
    nav: 'Training', label: 'MODEL DEVELOPMENT', title: 'Train. Evaluate. Improve. Repeat.',
    description: 'Collect 8–12 photos per ingredient across angles and lighting, label them in Roboflow, and train in Google Colab. Review weak ingredients and improve photos or labels.',
    points: ['Collect → Annotate → Train', 'Evaluate on unseen test photos', 'Fix weak links and expand the dataset'],
    note: '85–95% accuracy is the deck’s goal, not a reported result. Near-perfect scores on a small dataset can indicate memorization.',
    related: ['scan', 'video'],
  },
  video: {
    nav: 'Video', label: 'VIDEO INFERENCE', title: 'Track ingredients across frames.',
    description: 'YOLO detects ingredients and boxes. ByteTrack links detections across frames with tracking IDs, which help group detections into quantity estimates.',
    points: ['Upload → YOLO → ByteTrack', 'Group tracks to estimate quantities', 'Generate an annotated video'],
    note: 'Quantities are estimates, not guaranteed counts.', related: ['scan', 'training'],
  },
  rag: {
    nav: 'Recipes', label: 'RETRIEVAL-AUGMENTED GENERATION', title: 'Real recipes ground the suggestions.',
    description: 'Retrieve matching recipes, augment them with your ingredients, then generate tailored cooking steps. Real recipe context helps reduce unsupported suggestions.',
    points: ['Retrieve matching recipes', 'Augment with pantry context', 'Generate custom steps'],
    related: ['substitutions', 'servings'],
  },
  substitutions: {
    nav: 'Substitutions', label: 'PANTRY ALTERNATIVES', title: 'Make the most of what you have.',
    description: 'Compare required ingredients with your pantry and review available alternatives, instructions, and limitations before cooking.',
    points: ['See missing ingredients', 'Review pantry-based replacements', 'Check limitations before substituting'],
    note: 'Sean’s challenge: correct ingredient substitutions. Future work: expand alternatives and preferences.', related: ['rag'],
  },
  servings: {
    nav: 'Servings', label: 'SERVING-SIZE SCALER', title: 'A meal for one. Or a few.',
    description: 'Choose the number of servings to adapt recipe quantities and cooking guidance to the meal you actually need.',
    points: ['Choose a serving count', 'Scale recipe quantities', 'Keep cooking and inventory amounts aligned'],
    note: 'Aakash’s challenge: integrating the serving-size scaler cleanly.', related: ['inventory'],
  },
  voice: {
    nav: 'Voice', label: 'VOICE AGENT', title: 'Cooking help, hands free.',
    description: 'Speak a question, interpret it in the current cooking context, use recipe information, and hear the reply. Follow-up questions keep the conversation going.',
    points: ['Speak → Understand → RAG → Reply', 'Step-by-step guidance and follow-ups', 'Hands-free help while cooking'],
    note: 'Rishi’s challenge: reducing response delay while maintaining accuracy.',
  },
  inventory: {
    nav: 'Inventory', label: 'PANTRY & INVENTORY', title: 'Keep track of what’s left.',
    description: 'Manage quantities and units, then mark a recipe as cooked to deduct its ingredients. Review warnings when amounts cannot be converted reliably.',
    points: ['Manage ingredient quantities', 'Adjust amounts after cooking', 'Check low or empty ingredients'],
    related: ['servings'],
  },
  account: {
    nav: 'Personalization', label: 'ACCOUNTS & PREFERENCES', title: 'Cooking that remembers you.',
    description: 'Accounts connect saved recipes, pantry inventory, and cooking preferences. Password hashing and signed tokens support authenticated access.',
    points: ['Save recipes for later', 'Set preferences and guidance level', 'Record cooking feedback'],
    note: 'Bao’s challenge: understanding password hashing and signed token authentication.',
  },
  challenges: {
    nav: 'Challenges', label: 'LESSONS FROM THE TEAM', title: 'What challenged us.',
    description: 'The work spanned model quality, recipe adaptation, authentication, and communication across the team.',
    points: ['Bao · Password hashing & signed tokens', 'Rishi · Voice delay vs. accuracy', 'Lakshana · False positives & missed detections', 'Sean · Correct substitutions', 'Joshua · Role clarity & communication', 'Aakash · Serving-size integration'],
  },
  future: {
    nav: 'Next steps', label: 'FUTURE IMPLEMENTATION', title: 'Where NOSH goes next.',
    description: 'Broaden ingredient coverage and make cooking support more reliable and personal.',
    points: ['Expand the dataset', 'Improve ingredient detection', 'Improve conversation & pronunciation', 'Expand alternatives & preferences', 'Add automatic checks'],
    note: 'These are planned improvements from the deck, not completed features.',
  },
};

presentationContent.saving = {
  nav: 'Save & open', label: 'YOUR PERSONAL COOKBOOK', title: 'Keep a recipe worth cooking.',
  description: 'Save a recipe from your results, open Saved, and select it to prepare your cooking instructions.',
  points: ['Save a recipe', 'Open Saved', 'Select your recipe'],
};
export const chapters = [
  { id: 'introduction', label: 'Introduction', sections: ['intro', 'problem'] },
  { id: 'scanning', label: 'Scanning', sections: ['scan', 'training', 'video'] },
  { id: 'recipes', label: 'Recipes', sections: ['rag', 'substitutions', 'saving'] },
  { id: 'cooking', label: 'Cooking', sections: ['servings', 'voice'] },
  { id: 'inventory', label: 'Inventory', sections: ['inventory'] },
  { id: 'wrapup', label: 'Wrap-up', sections: ['challenges', 'future', 'ending'] },
];
export const nextStory = { title: 'intro', intro: 'problem', scan: 'training', training: 'video', rag: 'substitutions', inventory: 'challenges', challenges: 'future', future: 'ending' };
export const nextAction = {
  problem: 'When you’re ready, tap Find recipes on the dashboard, then Scan fridge to begin the walkthrough.',
  video: 'Upload a photo or video, review the ingredients, then tap Find Recipes.',
  rag: 'Press → to explain substitutions, then save a recipe you want to cook.',
  substitutions: 'Save a recipe, open Saved, and select it.',
  saving: 'Open Saved, select your recipe, then adjust Servings.',
  servings: 'Open Steps, then use a voice control or send a cooking question.',
  voice: 'Mark as cooked, then open My inventory to show what remains.',
  inventory: 'Review the quantities, then press → to discuss team challenges.',
};
export const chapterFor = page => chapters.find(chapter => chapter.sections.includes(page));
// Only meaningful app actions change topics. Navigation never resets the story.
export function topicForEvent(event) {
  if (event.kind === 'navigation') return event.path === '/inventory' ? 'inventory' : null;
  if (event.kind !== 'action') return null;
  return ['scan', 'video', 'rag', 'substitutions', 'saving', 'servings', 'voice'].includes(event.feature) ? event.feature : null;
}
