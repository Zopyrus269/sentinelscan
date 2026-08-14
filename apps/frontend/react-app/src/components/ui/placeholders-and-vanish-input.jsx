"use client";

import { AnimatePresence, motion, useMotionValue, useReducedMotion, useSpring } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

// Smooth caret, adapted from Skiper UI's Skiper106 ("Smooth Input"): only
// the caret-smoothing mechanism is taken from it (a spring-animated custom
// caret that glides between character positions instead of snapping like a
// native text-input caret) -- none of Skiper106's own input/wrapper markup
// or its "dialkit" dev-tuning panel. The native caret is hidden
// (caretColor: transparent on the input) and this measures the pixel width
// of the text before the caret on every keystroke/selection change to
// position a custom bar, whose x is driven through a spring so it eases
// into place rather than jumping.
export const CARET_SPRING = { stiffness: 500, damping: 30, mass: 0.5 };
const CARET_SPRING_REDUCED_MOTION = { stiffness: 10000, damping: 100, mass: 0.1 };

function useSmoothCaret(inputRef) {
  const containerRef = useRef(null);
  const measureRef = useRef(null);
  const caretX = useMotionValue(0);
  const caretOpacity = useMotionValue(0);
  const prefersReducedMotion = useReducedMotion();
  const springCaretX = useSpring(
    caretX,
    prefersReducedMotion ? CARET_SPRING_REDUCED_MOTION : CARET_SPRING,
  );

  const measurePrefixWidth = text => {
    const input = inputRef.current;
    const measureSpan = measureRef.current;
    if (!input || !measureSpan) return null;

    const styles = window.getComputedStyle(input);
    measureSpan.style.font = `${styles.fontStyle} ${styles.fontWeight} ${styles.fontSize} ${styles.fontFamily}`;
    measureSpan.style.letterSpacing = styles.letterSpacing;
    measureSpan.textContent = text;

    const paddingLeft = parseFloat(styles.paddingLeft) || 0;
    return text.length > 0 ? measureSpan.offsetWidth + paddingLeft : paddingLeft - 1;
  };

  const updateCaretFromInput = target => {
    const selectionStart = target.selectionStart ?? 0;
    const selectionEnd = target.selectionEnd ?? 0;
    const hasSelection = selectionStart !== selectionEnd;
    const caretIndex =
      selectionStart === selectionEnd
        ? selectionStart
        : target.selectionDirection === "backward"
          ? selectionStart
          : selectionEnd;

    const absoluteWidth = measurePrefixWidth(target.value.slice(0, caretIndex));
    if (absoluteWidth === null) return;

    const styles = window.getComputedStyle(target);
    const paddingRight = parseFloat(styles.paddingRight) || 0;
    const maxX = target.clientWidth - paddingRight;

    caretX.set(Math.min(absoluteWidth, maxX));
    caretOpacity.set(hasSelection ? 0 : 1);
  };

  const updateCaretRef = useRef(updateCaretFromInput);
  updateCaretRef.current = updateCaretFromInput;

  useEffect(() => {
    const input = inputRef.current;
    const container = containerRef.current;
    if (!input || !container) return;

    const updateCaretIfFocused = () => {
      if (document.activeElement === input) updateCaretRef.current(input);
    };

    const handleSelectionChange = () => {
      if (document.activeElement !== input) return;
      requestAnimationFrame(() => {
        if (document.activeElement === input) updateCaretRef.current(input);
      });
    };

    document.addEventListener("selectionchange", handleSelectionChange);
    document.fonts.addEventListener("loadingdone", updateCaretIfFocused);
    void document.fonts.ready.then(updateCaretIfFocused);

    const resizeObserver = new ResizeObserver(updateCaretIfFocused);
    resizeObserver.observe(container);

    return () => {
      document.removeEventListener("selectionchange", handleSelectionChange);
      document.fonts.removeEventListener("loadingdone", updateCaretIfFocused);
      resizeObserver.disconnect();
    };
  }, [inputRef]);

  return { containerRef, measureRef, springCaretX, caretOpacity, updateCaretRef };
}

export function PlaceholdersAndVanishInput({
  placeholders,
  onChange,
  onSubmit
}) {
  const [currentPlaceholder, setCurrentPlaceholder] = useState(0);

  const intervalRef = useRef(null);
  const startAnimation = () => {
    intervalRef.current = setInterval(() => {
      setCurrentPlaceholder((prev) => (prev + 1) % placeholders.length);
    }, 3000);
  };
  const handleVisibilityChange = () => {
    if (document.visibilityState !== "visible" && intervalRef.current) {
      clearInterval(intervalRef.current); // Clear the interval when the tab is not visible
      intervalRef.current = null;
    } else if (document.visibilityState === "visible") {
      startAnimation(); // Restart the interval when the tab becomes visible
    }
  };

  useEffect(() => {
    startAnimation();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [placeholders]);

  const canvasRef = useRef(null);
  const newDataRef = useRef([]);
  const inputRef = useRef(null);
  const [value, setValue] = useState("");
  const [animating, setAnimating] = useState(false);
  const { containerRef, measureRef, springCaretX, caretOpacity, updateCaretRef } =
    useSmoothCaret(inputRef);

  const draw = useCallback(() => {
    if (!inputRef.current) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = 800;
    canvas.height = 800;
    ctx.clearRect(0, 0, 800, 800);
    const computedStyles = getComputedStyle(inputRef.current);

    const fontSize = parseFloat(computedStyles.getPropertyValue("font-size"));
    ctx.font = `${fontSize * 2}px ${computedStyles.fontFamily}`;
    ctx.fillStyle = "#FFF";
    ctx.fillText(value, 16, 40);

    const imageData = ctx.getImageData(0, 0, 800, 800);
    const pixelData = imageData.data;
    const newData = [];

    for (let t = 0; t < 800; t++) {
      let i = 4 * t * 800;
      for (let n = 0; n < 800; n++) {
        let e = i + 4 * n;
        if (
          pixelData[e] !== 0 &&
          pixelData[e + 1] !== 0 &&
          pixelData[e + 2] !== 0
        ) {
          newData.push({
            x: n,
            y: t,
            color: [
              pixelData[e],
              pixelData[e + 1],
              pixelData[e + 2],
              pixelData[e + 3],
            ],
          });
        }
      }
    }

    newDataRef.current = newData.map(({ x, y, color }) => ({
      x,
      y,
      r: 1,
      color: `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${color[3]})`,
    }));
  }, [value]);

  useEffect(() => {
    draw();
  }, [value, draw]);

  const animate = (start) => {
    const animateFrame = (pos = 0) => {
      requestAnimationFrame(() => {
        const newArr = [];
        for (let i = 0; i < newDataRef.current.length; i++) {
          const current = newDataRef.current[i];
          if (current.x < pos) {
            newArr.push(current);
          } else {
            if (current.r <= 0) {
              current.r = 0;
              continue;
            }
            current.x += Math.random() > 0.5 ? 1 : -1;
            current.y += Math.random() > 0.5 ? 1 : -1;
            current.r -= 0.05 * Math.random();
            newArr.push(current);
          }
        }
        newDataRef.current = newArr;
        const ctx = canvasRef.current?.getContext("2d");
        if (ctx) {
          ctx.clearRect(pos, 0, 800, 800);
          newDataRef.current.forEach((t) => {
            const { x: n, y: i, r: s, color: color } = t;
            if (n > pos) {
              ctx.beginPath();
              ctx.rect(n, i, s, s);
              ctx.fillStyle = color;
              ctx.strokeStyle = color;
              ctx.stroke();
            }
          });
        }
        if (newDataRef.current.length > 0) {
          animateFrame(pos - 8);
        } else {
          setValue("");
          setAnimating(false);
        }
      });
    };
    animateFrame(start);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !animating) {
      vanishAndSubmit();
    }
  };

  const vanishAndSubmit = () => {
    setAnimating(true);
    caretOpacity.set(0);
    draw();

    const value = inputRef.current?.value || "";
    if (value && inputRef.current) {
      const maxX = newDataRef.current.reduce((prev, current) => (current.x > prev ? current.x : prev), 0);
      animate(maxX);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    vanishAndSubmit();
    onSubmit && onSubmit(e);
  };
  return (
    <form
      className={cn(
        "w-full relative max-w-xl mx-auto bg-white dark:bg-zinc-800 h-12 rounded-full overflow-hidden shadow-[0px_2px_3px_-1px_rgba(0,0,0,0.1),_0px_1px_0px_0px_rgba(25,28,33,0.02),_0px_0px_0px_1px_rgba(25,28,33,0.08)] transition duration-200",
        value && "bg-gray-50"
      )}
      onSubmit={handleSubmit}>
      <canvas
        className={cn(
          "absolute pointer-events-none  text-base transform scale-50 top-[20%] left-2 sm:left-8 origin-top-left filter invert dark:invert-0 pr-20",
          !animating ? "opacity-0" : "opacity-100"
        )}
        ref={canvasRef} />
      <div ref={containerRef} className="relative h-full w-full">
        <input
          onChange={(e) => {
            if (!animating) {
              setValue(e.target.value);
              onChange && onChange(e);
            }
            requestAnimationFrame(() => updateCaretRef.current(e.target));
          }}
          onKeyDown={handleKeyDown}
          onKeyUp={(e) => updateCaretRef.current(e.target)}
          onClick={(e) => updateCaretRef.current(e.target)}
          onFocus={(e) => updateCaretRef.current(e.target)}
          onBlur={() => caretOpacity.set(0)}
          ref={inputRef}
          value={value}
          type="text"
          style={{ caretColor: "transparent" }}
          className={cn(
            "w-full relative text-sm sm:text-base z-50 border-none dark:text-white bg-transparent text-black h-full rounded-full focus:outline-none focus:ring-0 pl-4 sm:pl-10 pr-20",
            animating && "text-transparent dark:text-transparent"
          )} />
        <span
          ref={measureRef}
          aria-hidden="true"
          className="pointer-events-none invisible absolute left-0 top-0 whitespace-pre" />
        <motion.div
          className="pointer-events-none absolute top-1/2 z-50 h-[1em] w-0.5 -translate-y-1/2 bg-black dark:bg-white"
          style={{ x: springCaretX, opacity: caretOpacity }} />
      </div>

      <button
        disabled={!value}
        type="submit"
        className="absolute right-2 top-1/2 z-50 -translate-y-1/2 h-8 w-8 rounded-full disabled:bg-gray-100 bg-black dark:bg-zinc-900 dark:disabled:bg-zinc-800 transition duration-200 flex items-center justify-center">
        <motion.svg
          xmlns="http://www.w3.org/2000/svg"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-gray-300 h-4 w-4">
          <path stroke="none" d="M0 0h24v24H0z" fill="none" />
          <motion.path
            d="M5 12l14 0"
            initial={{
              strokeDasharray: "50%",
              strokeDashoffset: "50%",
            }}
            animate={{
              strokeDashoffset: value ? 0 : "50%",
            }}
            transition={{
              duration: 0.3,
              ease: "linear",
            }} />
          <path d="M13 18l6 -6" />
          <path d="M13 6l6 6" />
        </motion.svg>
      </button>

      <div
        className="absolute inset-0 flex items-center rounded-full pointer-events-none">
        <AnimatePresence mode="wait">
          {!value && (
            <motion.p
              initial={{
                y: 5,
                opacity: 0,
              }}
              key={`current-placeholder-${currentPlaceholder}`}
              animate={{
                y: 0,
                opacity: 1,
              }}
              exit={{
                y: -15,
                opacity: 0,
              }}
              transition={{
                duration: 0.3,
                ease: "linear",
              }}
              className="dark:text-zinc-500 text-sm sm:text-base font-normal text-neutral-500 pl-4 sm:pl-12 text-left w-[calc(100%-2rem)] truncate">
              {placeholders[currentPlaceholder]}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </form>
  );
}
