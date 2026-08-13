import { motion } from 'framer-motion'

const COLUMN_COUNT = 8
const OPEN_STAGGER = 0.1
const OPEN_DURATION = 1.1
const EXPO_OUT = [0.16, 1, 0.3, 1]

export const TIMING = {
  textInMs: 1300,
  textHoldMs: 2200,
  textOutMs: 800,
  blackPauseMs: 300,
  openMs: (COLUMN_COUNT - 1) * OPEN_STAGGER * 1000 + OPEN_DURATION * 1000,
}

const columns = Array.from({ length: COLUMN_COUNT })

// Double-stairs reveal: the overlay starts fully covering the screen (no
// entrance animation -- matches the source component, which is already
// solid black on mount). Only the exit is animated: each column's top and
// bottom half slide off in opposite directions, staggered left-to-right so
// the leading edge reads as a diagonal staircase.
function StairColumn({ index, open }) {
  const transition = { duration: OPEN_DURATION, delay: index * OPEN_STAGGER, ease: EXPO_OUT }

  return (
    <div className="relative h-full w-full overflow-hidden">
      <motion.div
        className="absolute inset-x-0 top-0 h-1/2 bg-black"
        initial={false}
        animate={{ y: open ? '-100%' : '0%' }}
        transition={transition}
      />
      <motion.div
        className="absolute inset-x-0 bottom-0 h-1/2 bg-black"
        initial={false}
        animate={{ y: open ? '100%' : '0%' }}
        transition={transition}
      />
    </div>
  )
}

// stage: 'textIn' -> 'textHold' -> 'textOut' -> 'open'
export default function IntroPreloader({ stage }) {
  const textVisible = stage === 'textIn' || stage === 'textHold'
  const open = stage === 'open'

  return (
    <div className="fixed inset-0 z-[9999] flex" aria-hidden="true">
      {columns.map((_, index) => (
        <StairColumn key={index} index={index} open={open} />
      ))}
      <motion.span
        className="pointer-events-none absolute inset-0 flex items-center justify-center px-8 text-center font-['Inter'] text-[clamp(2rem,6vw,4.5rem)] leading-none font-bold tracking-[-0.02em] text-white"
        initial={{ opacity: 0, y: 16 }}
        animate={
          textVisible
            ? { opacity: 1, y: 0 }
            : { opacity: 0, y: stage === 'textOut' || open ? -12 : 16 }
        }
        transition={{
          duration: (stage === 'textIn' ? TIMING.textInMs : TIMING.textOutMs) / 1000,
          ease: EXPO_OUT,
        }}
      >
        SentinelScan
      </motion.span>
    </div>
  )
}
