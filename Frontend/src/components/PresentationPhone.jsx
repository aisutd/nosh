import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { RoundedBox } from "@react-three/drei";
import { Vector3 } from "three";

const SCREEN_WIDTH = 390;
const SCREEN_HEIGHT = 844;
const WORLD_WIDTH = 2.925;
const WORLD_HEIGHT = 6.33;

function projectScreen(camera, size, element) {
  if (!element || !size.width || !size.height) return;

  const corners = [
    [-WORLD_WIDTH / 2, WORLD_HEIGHT / 2],
    [WORLD_WIDTH / 2, WORLD_HEIGHT / 2],
    [WORLD_WIDTH / 2, -WORLD_HEIGHT / 2],
    [-WORLD_WIDTH / 2, -WORLD_HEIGHT / 2],
  ].map(([x, y]) => {
    const point = new Vector3(x, y, 0.17).project(camera);

    return {
      x: ((point.x + 1) * size.width) / 2,
      y: ((1 - point.y) * size.height) / 2,
    };
  });

  const [p0, p1, p2, p3] = corners;

  const dx1 = p1.x - p2.x;
  const dx2 = p3.x - p2.x;
  const dx3 = p0.x - p1.x + p2.x - p3.x;

  const dy1 = p1.y - p2.y;
  const dy2 = p3.y - p2.y;
  const dy3 = p0.y - p1.y + p2.y - p3.y;

  const denominator = dx1 * dy2 - dx2 * dy1;
  if (Math.abs(denominator) < 0.000001) return;

  const g = (dx3 * dy2 - dx2 * dy3) / denominator;
  const h = (dx1 * dy3 - dx3 * dy1) / denominator;

  const a = p1.x - p0.x + g * p1.x;
  const b = p3.x - p0.x + h * p3.x;
  const d = p1.y - p0.y + g * p1.y;
  const e = p3.y - p0.y + h * p3.y;

  element.style.transform = `matrix3d(
    ${a / SCREEN_WIDTH}, ${d / SCREEN_WIDTH}, 0, ${g / SCREEN_WIDTH},
    ${b / SCREEN_HEIGHT}, ${e / SCREEN_HEIGHT}, 0, ${h / SCREEN_HEIGHT},
    0, 0, 1, 0,
    ${p0.x}, ${p0.y}, 0, 1
  )`;

  element.style.visibility = "visible";
}

function PhoneScene({ screenRef, started }) {
  const progressRef = useRef(0);
  const previousStartedRef = useRef(false);
  const reducedMotionRef = useRef(
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );

  useFrame(({ camera, size }, delta) => {
    if (started && !previousStartedRef.current) {
      progressRef.current = 0;
    }

    previousStartedRef.current = started;

    if (!started) {
      progressRef.current = 0;
    } else {
      progressRef.current = Math.min(
        1,
        progressRef.current + delta / 1.1
      );
    }

    const progress = reducedMotionRef.current
      ? 1
      : progressRef.current;

    const remaining = Math.pow(1 - progress, 3);
    const angle = -0.15 * remaining;
    const distance = 12 + 0.6 * remaining;

    camera.position.set(
      Math.sin(angle) * distance,
      0.12 * remaining,
      Math.cos(angle) * distance
    );

    camera.lookAt(0, 0, 0);
    camera.updateMatrixWorld();

    const screen = screenRef.current;

    if (screen) {
      if (started) {
        projectScreen(camera, size, screen);
      } else {
        screen.style.visibility = "hidden";
      }

      screen.style.pointerEvents =
        started && progress >= 1 ? "auto" : "none";
    }
  });

  return (
    <>
      <ambientLight intensity={1.5} />

      <directionalLight position={[4, 6, 8]} intensity={3} />

      <directionalLight position={[-4, 1, -3]} intensity={2} />

      {/* Phone body */}
      <RoundedBox
        args={[3.13, 6.65, 0.28]}
        radius={0.13}
        smoothness={6}
      >
        <meshStandardMaterial
          color="#353231"
          metalness={0.65}
          roughness={0.3}
        />
      </RoundedBox>

      {/* Side button */}
      <RoundedBox
        args={[0.06, 0.65, 0.1]}
        position={[1.58, 0.9, 0]}
        radius={0.025}
      >
        <meshStandardMaterial
          color="#77716d"
          metalness={0.7}
          roughness={0.3}
        />
      </RoundedBox>
    </>
  );
}

export default function PresentationPhone({ frameRef, started }) {
  const screenRef = useRef(null);

  return (
    <div className="presentation-3d-phone">
      <div
        className="presentation-3d-stage"
        style={{
          position: "relative",
          width: "100%",
          flex: 1,
          minHeight: 0,
          isolation: "isolate",
          cursor: "auto",
        }}
      >
        <Canvas
          camera={{ position: [0, 0, 12], fov: 35 }}
          dpr={[1, 1.5]}
          frameloop="always"
          gl={{ alpha: true, antialias: true }}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            zIndex: 0,
          }}
          fallback={<p>3D graphics are unavailable.</p>}
        >
          <PhoneScene
            screenRef={screenRef}
            started={started}
          />
        </Canvas>

        {/* Live app stays mounted throughout the presentation. */}
        <div
          ref={screenRef}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: SCREEN_WIDTH,
            height: SCREEN_HEIGHT,
            margin: 0,
            padding: 0,
            overflow: "hidden",
            borderRadius: 32,
            background: "#fff7f7",
            transformOrigin: "0 0",
            visibility: "hidden",
            zIndex: 2,
            pointerEvents: "none",
          }}
        >
          <iframe
            ref={frameRef}
            src="/"
            title="NOSH live app"
            allow="camera; microphone"
            tabIndex={started ? 0 : -1}
            style={{
              display: "block",
              width: SCREEN_WIDTH,
              height: SCREEN_HEIGHT,
              margin: 0,
              padding: 0,
              border: 0,
              background: "#fff7f7",
            }}
          />
        </div>
      </div>
    </div>
  );
}