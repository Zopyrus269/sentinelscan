import { motion, AnimatePresence } from 'framer-motion'

// Per-character "shutter" slice animation, lifted as-is from the
// 21st.dev "Hero Shutter Text" component (daiv09/hero-shutter-text):
// same delay/duration/easing values and the same three clipPath slice
// bands per character. Everything else from that component (the demo
// background grid, corner accents, and the click-to-re-shutter button
// + its remount-on-click state) was demo scaffolding, not the
// animation itself, and is intentionally not carried over here.
//
// Font size is the one animation-adjacent value that had to change: the
// source component hardcodes text-[15vw] per character, sized for a
// single short word ("IMMERSE") filling a full-viewport demo. For a real
// multi-word heading that both runs the word count much higher and must
// stay on one line (flex-nowrap, no wrap), so font-size is pure vw
// (scales with the viewport instead of a fixed rem ceiling) capped with
// `min()` so it can't blow past the site's own heading scale on very
// wide screens -- that keeps the whole phrase's total width proportional
// to the viewport at every breakpoint instead of wrapping.
const CHAR_FONT_SIZE = 'text-[min(3.1vw,3rem)]'

// `start` gates the reveal rather than gating the mount: every span's
// `animate` target collapses to its own `initial` values while
// start=false, so the characters sit blurred/off-slice and inert. When
// the caller flips `start` to true, framer-motion transitions from
// that held state to the real reveal targets using the same per-character
// delays below -- i.e. the reveal plays out at whatever moment the
// caller decides "now", rather than the instant this component mounts.
export default function ShutterText({ text, start = true, className = '' }) {
  const characters = text.split('')
  // Each character's box height comes from the main span's own
  // leading-none (line-height: 1) line box, which is tighter than this
  // font's descender depth -- letters like "y" had their descender leg
  // clipped by the wrapper's overflow. The horizontal clip is still
  // needed (it contains the slice layers' left/right sweep so they don't
  // visually bleed into neighboring characters), so only the x-axis stays
  // clipped. It's `overflow-x-clip`, not `-hidden`: per the CSS overflow
  // spec, pairing `hidden` on one axis with `visible` on the other gets
  // silently promoted to `auto` on the visible axis, which still clips
  // passively (no scrollbar ever appears to reveal it) -- `clip` is the
  // one value that doesn't trigger that pairing rule, so overflow-y
  // actually stays `visible` and descenders render in full.

  return (
    <div className={`relative w-full ${className}`}>
      <AnimatePresence mode="wait">
        <motion.div className="flex flex-nowrap justify-center items-center w-full">
          {characters.map((char, i) => (
            <div key={i} className="relative px-[0.1vw] overflow-x-clip overflow-y-visible">
              {/* Main Character */}
              <motion.span
                initial={{ opacity: 0, filter: 'blur(10px)' }}
                animate={start ? { opacity: 1, filter: 'blur(0px)' } : { opacity: 0, filter: 'blur(10px)' }}
                transition={{ delay: i * 0.04 + 0.3, duration: 0.8 }}
                className={`${CHAR_FONT_SIZE} leading-none font-black text-zinc-900 dark:text-white tracking-tighter`}
              >
                {char === ' ' ? ' ' : char}
              </motion.span>

              {/* Top Slice Layer */}
              <motion.span
                initial={{ x: '-100%', opacity: 0 }}
                animate={start ? { x: '100%', opacity: [0, 1, 0] } : { x: '-100%', opacity: 0 }}
                transition={{ duration: 0.7, delay: i * 0.04, ease: 'easeInOut' }}
                className={`${CHAR_FONT_SIZE} absolute inset-0 font-black text-indigo-600 dark:text-emerald-400 z-10 pointer-events-none`}
                style={{ clipPath: 'polygon(0 0, 100% 0, 100% 35%, 0 35%)' }}
              >
                {char}
              </motion.span>

              {/* Middle Slice Layer */}
              <motion.span
                initial={{ x: '100%', opacity: 0 }}
                animate={start ? { x: '-100%', opacity: [0, 1, 0] } : { x: '100%', opacity: 0 }}
                transition={{ duration: 0.7, delay: i * 0.04 + 0.1, ease: 'easeInOut' }}
                className={`${CHAR_FONT_SIZE} absolute inset-0 font-black text-zinc-800 dark:text-zinc-200 z-10 pointer-events-none`}
                style={{ clipPath: 'polygon(0 35%, 100% 35%, 100% 65%, 0 65%)' }}
              >
                {char}
              </motion.span>

              {/* Bottom Slice Layer */}
              <motion.span
                initial={{ x: '-100%', opacity: 0 }}
                animate={start ? { x: '100%', opacity: [0, 1, 0] } : { x: '-100%', opacity: 0 }}
                transition={{ duration: 0.7, delay: i * 0.04 + 0.2, ease: 'easeInOut' }}
                className={`${CHAR_FONT_SIZE} absolute inset-0 font-black text-indigo-600 dark:text-emerald-400 z-10 pointer-events-none`}
                style={{ clipPath: 'polygon(0 65%, 100% 65%, 100% 100%, 0 100%)' }}
              >
                {char}
              </motion.span>
            </div>
          ))}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
