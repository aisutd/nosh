import "./Presentation.css";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import PresentationPhone from "../components/PresentationPhone";

const presentationContent = {
  intro: {
    label: "NOSH · YOUR AI COOKING BUDDY",
    title: "Your ingredients. Your next meal.",
    description:
      "Turn what’s already in your kitchen into something worth cooking.",
    points: [
      "Scan ingredients",
      "Discover recipes",
      "Cook with voice guidance",
    ],
  },
  scan: {
    label: "COMPUTER VISION",
    title: "From your fridge to your pantry.",
    description:
      "NOSH uses a trained YOLO model to identify ingredients in an uploaded photo or video.",
    points: [
      "Detect ingredients and their locations",
      "Return ingredient names and confidence scores",
      "Use detections to help build your pantry",
    ],
  },
  rag: {
    label: "RECIPE RETRIEVAL · RAG",
    title: "Ingredients become meal ideas.",
    description:
      "NOSH retrieves relevant recipes and uses them as context to help generate cooking guidance.",
    points: [
      "Search recipes using your ingredients",
      "Ground suggestions in recipe data",
      "Adapt guidance to your cooking request",
    ],
  },
  voice: {
    label: "VOICE ASSISTANT",
    title: "Cooking help, hands free.",
    description:
      "Ask cooking questions and follow recipe steps through a voice conversation with NOSH.",
    points: [
      "Turn speech into a cooking question",
      "Use the current recipe as context",
      "Read responses aloud",
    ],
  },
  inventory: {
    label: "PANTRY & INVENTORY",
    title: "Keep track of what’s left.",
    description:
      "NOSH tracks ingredient quantities and can deduct recipe amounts when you finish cooking.",
    points: [
      "Manage ingredient quantities and units",
      "Identify low or empty ingredients",
      "Warn when recipe units cannot be converted",
    ],
  },
};

const pages = [
  "title",
  "intro",
  "scan",
  "rag",
  "voice",
  "inventory",
  "ending",
];

function isDemoPage(page) {
  return Object.hasOwn(presentationContent, page);
}

function reducedMotion() {
  return window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;
}

export default function Presentation() {
  const presentationRef = useRef(null);
  const layoutRef = useRef(null);
  const textRef = useRef(null);
  const coverRef = useRef(null);
  const frameRef = useRef(null);

  const pageRef = useRef("title");
  const previousPageRef = useRef("title");
  const busyRef = useRef(false);
  const mountedRef = useRef(false);
  const animationsRef = useRef([]);

  const [page, setPage] = useState("title");
  const [transitioning, setTransitioning] = useState(false);

  const showDemo = isDemoPage(page);
  const content = presentationContent[page];

  const cancelAnimations = useCallback(() => {
    animationsRef.current.forEach((animation) => {
      animation.cancel();
    });
    animationsRef.current = [];
  }, []);

  const changePage = useCallback(
    async (nextPage) => {
      if (!pages.includes(nextPage)) return;
      if (nextPage === pageRef.current || busyRef.current) return;

      busyRef.current = true;
      setTransitioning(true);
      cancelAnimations();

      const currentPage = pageRef.current;

      // Animate the phone out before showing a full-screen cover.
      if (
        isDemoPage(currentPage) &&
        !isDemoPage(nextPage) &&
        !reducedMotion()
      ) {
        const phone = layoutRef.current?.querySelector(
          ".presentation-3d-phone"
        );

        if (phone) {
          const exit = phone.animate(
            [
              {
                transform:
                  "perspective(1400px) translateY(0) rotateY(0deg)",
              },
              {
                transform:
                  "perspective(1400px) translateY(110dvh) rotateY(-10deg)",
              },
            ],
            {
              duration: 650,
              easing: "cubic-bezier(.55, 0, 1, .45)",
              fill: "forwards",
            }
          );

          animationsRef.current.push(exit);

          if (textRef.current) {
            const textExit = textRef.current.animate(
              [
                { opacity: 1, transform: "translateY(0)" },
                { opacity: 0, transform: "translateY(24px)" },
              ],
              {
                duration: 300,
                easing: "ease-in",
                fill: "forwards",
              }
            );

            animationsRef.current.push(textExit);
          }

          try {
            await exit.finished;
          } catch {
            busyRef.current = false;

            if (mountedRef.current) {
              setTransitioning(false);
            }

            return;
          }
        }
      }

      if (!mountedRef.current) return;

      previousPageRef.current = currentPage;
      pageRef.current = nextPage;
      setPage(nextPage);
    },
    [cancelAnimations]
  );

  useEffect(() => {
    mountedRef.current = true;
    presentationRef.current?.focus({ preventScroll: true });

    return () => {
      mountedRef.current = false;
      cancelAnimations();
    };
  }, [cancelAnimations]);

  useLayoutEffect(() => {
    cancelAnimations();

    const previousPage = previousPageRef.current;
    const enteringDemo = showDemo && !isDemoPage(previousPage);
    let entrance;

    if (!reducedMotion()) {
      if (enteringDemo && layoutRef.current) {
        // Phone and first text slide up together.
        entrance = layoutRef.current.animate(
          [
            { transform: "translateY(100dvh)" },
            { transform: "translateY(0)" },
          ],
          {
            duration: 750,
            easing: "cubic-bezier(.22, 1, .36, 1)",
            fill: "backwards",
          }
        );
      } else if (showDemo && textRef.current) {
        // The phone stays still when changing topics.
        entrance = textRef.current.animate(
          [
            { transform: "translateY(35px)", opacity: 0 },
            { transform: "translateY(0)", opacity: 1 },
          ],
          {
            duration: 400,
            easing: "cubic-bezier(.22, 1, .36, 1)",
            fill: "backwards",
          }
        );
      } else if (
        page !== previousPage &&
        coverRef.current
      ) {
        entrance = coverRef.current.animate(
          [
            { opacity: 0, transform: "translateY(20px)" },
            { opacity: 1, transform: "translateY(0)" },
          ],
          {
            duration: 450,
            easing: "ease-out",
            fill: "backwards",
          }
        );
      }
    }

    function finishTransition() {
      busyRef.current = false;

      if (mountedRef.current) {
        setTransitioning(false);
      }
    }

    if (entrance) {
      animationsRef.current.push(entrance);
      entrance.finished.then(
        finishTransition,
        finishTransition
      );
    } else {
      finishTransition();
    }

    return () => entrance?.cancel();
  }, [page, showDemo, cancelAnimations]);

  useEffect(() => {
    function handleKeyDown(event) {
      if (
        event.target instanceof Element &&
        event.target.closest(
          "input, textarea, select, button, [contenteditable]"
        )
      ) {
        return;
      }

      if (event.altKey || event.ctrlKey || event.metaKey) return;

      if (
        event.key !== "ArrowLeft" &&
        event.key !== "ArrowRight"
      ) {
        return;
      }

      event.preventDefault();

      if (event.repeat || busyRef.current) return;

      const direction = event.key === "ArrowRight" ? 1 : -1;
      const index = pages.indexOf(pageRef.current);
      const nextIndex = Math.max(
        0,
        Math.min(index + direction, pages.length - 1)
      );

      changePage(pages[nextIndex]);
    }

    function handleMessage(event) {
      if (!isDemoPage(pageRef.current)) return;
      if (busyRef.current) return;
      if (event.origin !== window.location.origin) return;
      if (event.source !== frameRef.current?.contentWindow) return;
      if (event.data?.type !== "nosh-demo-feature") return;

      if (isDemoPage(event.data.feature)) {
        changePage(event.data.feature);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("message", handleMessage);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("message", handleMessage);
    };
  }, [changePage]);

  function focusPresentation(event) {
    if (
      event.target.closest(
        ".presentation-3d-phone, button, input, select, textarea, a"
      )
    ) {
      return;
    }

    presentationRef.current?.focus({ preventScroll: true });
  }

  return (
    <main
      ref={presentationRef}
      className={`presentation${
        showDemo ? " presentation-started" : ""
      }`}
      tabIndex={-1}
      onClick={focusPresentation}
      aria-label="NOSH presentation. Use left and right arrow keys."
    >
      {page === "title" && (
        <section
          key="title"
          ref={coverRef}
          className="presentation-title-screen"
        >
          <span className="presentation-title-label">
            YOUR AI COOKING BUDDY
          </span>

          <h1 className="presentation-title-logo">
            nosh<span>.</span>
          </h1>

          <p className="presentation-title-tagline">
            Turn what’s in your kitchen
            <br />
            into your next meal.
          </p>
        </section>
      )}

      {page === "ending" && (
        <section
          key="ending"
          ref={coverRef}
          className="presentation-title-screen"
        >
          <span className="presentation-title-label">
            NOSH · YOUR AI COOKING BUDDY
          </span>

          <h1
            style={{
              display: "block",
              margin: "24px 0",
              color: "#6b5350",
              fontSize: "clamp(64px, 10vw, 150px)",
              fontWeight: 800,
              lineHeight: 1.05,
              letterSpacing: "-3px",
              textAlign: "center",
            }}
          >
            Thank you<span style={{ color: "#b74357" }}>.</span>
          </h1>

          <p className="presentation-title-tagline">
            Questions?
          </p>
        </section>
      )}

      {/* Preserve the live app when moving between screens. */}
      <div
        ref={layoutRef}
        className="presentation-layout"
        style={{
          visibility: showDemo ? "visible" : "hidden",
          pointerEvents:
            showDemo && !transitioning ? "auto" : "none",
        }}
        aria-hidden={!showDemo}
        inert={!showDemo || transitioning}
      >
        <PresentationPhone
          frameRef={frameRef}
          started={showDemo}
        />

        <section
          ref={textRef}
          className="presentation-content"
        >
          {content && (
            <>
              <span className="presentation-eyebrow">
                {content.label}
              </span>

              <h1>{content.title}</h1>

              <p className="presentation-description">
                {content.description}
              </p>

              <div className="presentation-features">
                {content.points.map((point) => (
                  <span key={point}>{point}</span>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}