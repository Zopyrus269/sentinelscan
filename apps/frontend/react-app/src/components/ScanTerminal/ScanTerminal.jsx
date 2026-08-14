import { useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import SpecularFrame from '../SpecularFrame/SpecularFrame.jsx'

// How long each newly-revealed word sits before the next one starts.
const WORD_REVEAL_INTERVAL_MS = 90

// The home page's caret spring (CARET_SPRING in
// placeholders-and-vanish-input.jsx: stiffness 500/damping 30/mass 0.5) is
// tuned to snap a 1px caret bar to a new character position -- a quick,
// near-critically-damped "pop". Applied to a whole word appearing, that
// pop read as rough/clicky. This softens the same spring family (lower
// stiffness, more damping) so each word eases in gently instead of
// popping -- same spring *feel*, tuned for this use.
const WORD_REVEAL_SPRING = { type: 'spring', stiffness: 220, damping: 26, mass: 0.6 }

// The vendored component's own banner spells "TERMINALLY" in the "ANSI
// Shadow" figlet font. This is that exact same font -- generated via
// `pyfiglet.Figlet(font='ansi_shadow')` rather than hand-edited, and
// verified to reproduce the pasted "TERMINALLY" banner byte-for-byte
// before regenerating for "SENTINEL SCAN" -- rather than hand-drawing two
// unseen letter glyphs (S, C) into a box-drawing font, which is exactly
// the kind of edit that silently drifts by one column. The word gap comes
// from the font's own space glyph (regenerated as two words), not a
// manually inserted run of spaces.
const ASCII_BANNER = [
  '███████╗███████╗███╗   ██╗████████╗██╗███╗   ██╗███████╗██╗         ███████╗ ██████╗ █████╗ ███╗   ██╗',
  '██╔════╝██╔════╝████╗  ██║╚══██╔══╝██║████╗  ██║██╔════╝██║         ██╔════╝██╔════╝██╔══██╗████╗  ██║',
  '███████╗█████╗  ██╔██╗ ██║   ██║   ██║██╔██╗ ██║█████╗  ██║         ███████╗██║     ███████║██╔██╗ ██║',
  '╚════██║██╔══╝  ██║╚██╗██║   ██║   ██║██║╚██╗██║██╔══╝  ██║         ╚════██║██║     ██╔══██║██║╚██╗██║',
  '███████║███████╗██║ ╚████║   ██║   ██║██║ ╚████║███████╗███████╗    ███████║╚██████╗██║  ██║██║ ╚████║',
  '╚══════╝╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝    ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝',
].join('\n')

// Ported from dashboard.js's SENTINELSCAN_STAGES / friendlyName / worker
// description tables -- dashboard.js is a plain non-module script (not an
// ES module), so this component can't import from it directly. Its own
// copies became dead code once the DOM regions that used them were removed
// (see dashboard.js's own trimmed-down renderScan()).
const STAGE_LABELS = {
  dns_lookup: 'DNS Lookup',
  reverse_dns_lookup: 'Reverse DNS Lookup',
  port_scan: 'Port Scan',
  ssl_check: 'SSL Check',
  http_headers: 'HTTP Headers',
  cookie_analysis: 'Cookie Analysis',
  robots_txt_parse: 'robots.txt Parser',
  sitemap_parse: 'Sitemap Parser',
  whois_lookup: 'WHOIS Lookup',
  ddos_resilience_check: 'Passive DDoS Resilience',
  calculate_cvss: 'CVSS Calculator',
  generate_report: 'Report Generator',
}

function friendlyName(value) {
  const aliases = {
    initializing: 'Initialization',
    initialization: 'Initialization',
    IN_PROGRESS: 'In Progress',
    COMPLETED: 'Completed',
    FAILED: 'Failed',
    ...STAGE_LABELS,
  }

  return (
    aliases[value] ||
    String(value || 'Waiting')
      .replaceAll('_', ' ')
      .replace(/\b\w/g, character => character.toUpperCase())
  )
}

// Same status -> color mapping dashboard.js's renderWorkers() used for the
// worker bento cards, now applied to the completion line instead.
function statusClassName(status) {
  const normalized = String(status || '').toUpperCase()
  if (normalized === 'COMPLETED') return 'text-emerald-400'
  if (['FAILED', 'TIMEOUT', 'UNREACHABLE'].includes(normalized)) return 'text-red-400'
  if (normalized === 'WARNING') return 'text-yellow-400'
  return 'text-gray-300'
}

// Reused verbatim from the pasted source -- this is what turns the report
// URL into a clickable link without the terminal accepting any text input.
function renderOutput(output, keyPrefix) {
  const urlRegex = /(https?:\/\/[^\s]+)/g
  const emailRegex = /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g

  let parts = output.split(urlRegex)
  parts = parts.flatMap(part => (urlRegex.test(part) ? [part] : part.split(emailRegex)))

  return parts.map((part, index) => {
    const key = `${keyPrefix}-${index}`
    if (urlRegex.test(part)) {
      return (
        <a
          key={key}
          href={part}
          className="text-cyan-400 hover:underline hover:text-cyan-300 transition-colors"
        >
          {part}
        </a>
      )
    }
    if (emailRegex.test(part)) {
      return (
        <a key={key} href={`mailto:${part}`} className="text-cyan-400 hover:underline hover:text-cyan-300 transition-colors">
          {part}
        </a>
      )
    }
    return <span key={key}>{part}</span>
  })
}

function formatDuration(startedAt, completedAt) {
  if (!startedAt) return '00:00'
  const start = new Date(startedAt).getTime()
  const end = completedAt ? new Date(completedAt).getTime() : Date.now()
  const totalSeconds = Math.max(0, Math.floor((end - start) / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

// This is a pure output console -- no <input>, no command history, no
// keyboard handling. It listens for the 'sentinelscan:scan-update' event
// that dashboard.js's existing poll loop dispatches on every tick (same
// bridge pattern main.jsx already uses to feed external data into a
// mounted component, e.g. SiteBackground's pointer forwarding), rather
// than running a second competing poll loop against the same endpoint.
export default function ScanTerminal() {
  const [lines, setLines] = useState([])
  const [typingLine, setTypingLine] = useState(null)
  const [scan, setScan] = useState(null)
  const seenEventCountRef = useRef(0)
  const announcedTargetRef = useRef(false)
  const announcedDoneRef = useRef(false)
  const lineIdRef = useRef(0)
  const queueRef = useRef([])
  const typingRef = useRef(null)
  const typingTimerRef = useRef(null)
  const scrollContainerRef = useRef(null)
  // Starts true (follow the newest output). Turns false the moment the
  // viewer scrolls away from the bottom -- e.g. to reread an earlier
  // line while typing is still going -- so the per-word re-renders below
  // stop yanking them back down. Turns true again once they scroll back
  // to the bottom themselves.
  const isPinnedToBottomRef = useRef(true)

  const handleTerminalScroll = () => {
    const el = scrollContainerRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    isPinnedToBottomRef.current = distanceFromBottom < 48
  }

  // Lines no longer land in the terminal all at once -- each one is queued
  // and revealed word by word (see startNextQueuedLine/tick below) so a
  // burst of worker events (several can arrive in the same 500ms poll
  // tick) still reads as one thing being typed at a time, not a wall of
  // text appearing in one frame.
  const enqueueLine = (text, className = 'text-gray-300') => {
    lineIdRef.current += 1
    queueRef.current.push({ id: lineIdRef.current, text, className })
    if (!typingRef.current) startNextQueuedLine()
  }

  const startNextQueuedLine = () => {
    const next = queueRef.current.shift()
    if (!next) return
    const words = next.text.split(' ')
    typingRef.current = { ...next, words, revealed: 0 }
    setTypingLine({ ...typingRef.current })
    tick()
  }

  const tick = () => {
    typingTimerRef.current = setTimeout(() => {
      const current = typingRef.current
      if (!current) return

      current.revealed += 1
      setTypingLine({ ...current })

      if (current.revealed >= current.words.length) {
        setLines(prev => [...prev, { id: current.id, text: current.text, className: current.className }])
        typingRef.current = null
        setTypingLine(null)
        startNextQueuedLine()
      } else {
        tick()
      }
    }, WORD_REVEAL_INTERVAL_MS)
  }

  useEffect(() => {
    return () => {
      if (typingTimerRef.current) clearTimeout(typingTimerRef.current)
    }
  }, [])

  useEffect(() => {
    const handleScanUpdate = event => {
      const nextScan = event.detail
      if (!nextScan) return

      if (!announcedTargetRef.current) {
        announcedTargetRef.current = true
        enqueueLine(`Target acquired: ${nextScan.target || 'unknown target'}`, 'text-white')
        enqueueLine(`Scan ID: ${nextScan.scan_id || ''}`, 'text-gray-500')
      }

      const events = nextScan.events || []
      for (let i = seenEventCountRef.current; i < events.length; i += 1) {
        const evt = events[i]
        if (!evt.tool_name) continue

        if (evt.phase === 'selected') {
          enqueueLine(
            `> ${friendlyName(evt.tool_name)} selected -- ${evt.reasoning || 'starting worker.'}`,
            'text-cyan-400',
          )
        } else if (evt.phase === 'completed') {
          const status = String(evt.worker_status || 'COMPLETED').toUpperCase()
          enqueueLine(
            `✓ ${friendlyName(evt.tool_name)} completed (${friendlyName(status)}) -- ${
              evt.summary || 'no summary provided.'
            }`,
            statusClassName(status),
          )
        }
      }
      seenEventCountRef.current = events.length

      if (nextScan.status === 'COMPLETED' && !announcedDoneRef.current) {
        announcedDoneRef.current = true
        const reportUrl = `${window.location.origin}/report?scan_id=${encodeURIComponent(
          nextScan.scan_id || '',
        )}`
        enqueueLine('Assessment complete. All workers finished.', 'text-emerald-400')
        enqueueLine(`Open the full report: ${reportUrl}`, 'text-gray-300')
      }

      if (nextScan.status === 'FAILED' && !announcedDoneRef.current) {
        announcedDoneRef.current = true
        enqueueLine(
          `Assessment failed: ${nextScan.error || 'unknown error.'}`,
          'text-red-400',
        )
      }

      setScan(nextScan)
    }

    window.addEventListener('sentinelscan:scan-update', handleScanUpdate)
    return () => window.removeEventListener('sentinelscan:scan-update', handleScanUpdate)
  }, [])

  useEffect(() => {
    const el = scrollContainerRef.current
    // An instant scrollTop jump, not scrollIntoView({behavior: 'smooth'}):
    // this effect re-runs on every word reveal (~every 55ms), and each
    // smooth-scroll call was restarting the browser's scroll animation
    // out from under the last one, which is what made following live
    // output look rough/stuttery. Snapping the already-pinned viewport to
    // the new bottom every tick reads as continuous instead.
    if (el && isPinnedToBottomRef.current) {
      el.scrollTop = el.scrollHeight
    }
  }, [lines, typingLine])

  const progress = scan ? Math.max(0, Math.min(100, Math.round(Number(scan.progress_percent || 0)))) : 0
  const eventCount = scan?.events?.length || 0
  // No scan data yet means no scan is actually running against this
  // terminal (nothing has ever dispatched a 'sentinelscan:scan-update'
  // event) -- showing "In Progress" here was misleading in that idle
  // state, since nothing is in progress.
  const statusLabel = scan ? friendlyName(scan.status || 'IN_PROGRESS') : 'Online'
  const statusDotClass =
    scan?.status === 'COMPLETED'
      ? 'text-emerald-400'
      : scan?.status === 'FAILED'
        ? 'text-red-400'
        : 'text-green-400'

  return (
    <SpecularFrame radius={8} className="w-full">
      <div className="w-full bg-black text-green-400 font-mono rounded-lg overflow-hidden shadow-2xl border border-white/10">
        {/* Terminal Header */}
        <div className="flex items-center gap-2 p-3 bg-black border-b border-white/10 text-xs text-gray-400">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <div className="w-3 h-3 rounded-full bg-yellow-500" />
            <div className="w-3 h-3 rounded-full bg-green-500" />
          </div>
          <div className="flex-1 text-center font-semibold">
            sentinelscan@scan:~$ | Live Assessment Terminal
          </div>
          <div className="text-xs">
            <span className={statusDotClass}>&#9679;</span> {statusLabel.toUpperCase()}
          </div>
        </div>

        {/* Terminal Output -- taller than the original 520px so the
            terminal reclaims roughly the vertical footprint the removed
            "Authorized Security Assessment" card used to occupy below it,
            rather than the page (and the terminal's apparent prominence
            in it) just getting shorter once that card was deleted. */}
        <div
          ref={scrollContainerRef}
          onScroll={handleTerminalScroll}
          className="h-[820px] overflow-y-auto p-4 space-y-3 bg-black cursor-text"
          style={{ scrollbarWidth: 'thin', scrollbarColor: '#10b981 #1f2937' }}
        >
          <pre className="text-white text-[10px] sm:text-xs leading-tight overflow-x-auto">
            {ASCII_BANNER}
          </pre>
          <div className="whitespace-pre-wrap text-gray-300 leading-relaxed">
            [SYSTEM INITIALIZED] - SentinelScan Live Terminal
            {'\n'}Output-only console. Streaming AI agent activity as the assessment runs.
          </div>

          {lines.map(line => (
            <div key={line.id} className={`whitespace-pre-wrap leading-relaxed ${line.className}`}>
              {renderOutput(line.text, `line-${line.id}`)}
            </div>
          ))}

          {typingLine && (
            <div className={`whitespace-pre-wrap leading-relaxed ${typingLine.className}`}>
              {typingLine.words.slice(0, typingLine.revealed).map((word, index) => (
                <span key={`${typingLine.id}-w-${index}`}>
                  <motion.span
                    initial={{ opacity: 0, y: 3 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={WORD_REVEAL_SPRING}
                    className="inline-block"
                  >
                    {word}
                  </motion.span>
                  {index < typingLine.revealed - 1 ? ' ' : ''}
                </span>
              ))}
              {typingLine.revealed < typingLine.words.length && (
                <span className="inline-block w-[0.5em] h-[1em] align-middle bg-current animate-pulse ml-0.5" />
              )}
            </div>
          )}

          {/* Pinned live status line -- absorbs the old Progress Card +
              Scan Summary without re-printing a new scrolling line on every
              500ms poll tick. */}
          <div className="whitespace-pre-wrap text-gray-400 border-t border-gray-800 pt-2">
            Progress: {progress}% | Current: {friendlyName(scan?.current_action || 'initialization')} | Duration:{' '}
            {formatDuration(scan?.started_at, scan?.completed_at)} | Events: {eventCount}
          </div>

          {/* Idle prompt cursor -- only shown before a scan has actually
              started. Once a scan is running this same line would read as
              a second, idle terminal blinking beneath the one actively
              streaming output above it. */}
          {!scan && (
            <div className="flex gap-2 items-center">
              <span className="text-cyan-400 font-semibold">sentinelscan@scan:~$</span>
              <span className="text-green-400 animate-pulse">&#9608;</span>
            </div>
          )}
        </div>

        {/* Terminal Footer */}
        <div className="bg-black px-4 py-2 text-xs text-gray-500 border-t border-white/10">
          <div className="flex justify-between items-center">
            <span>Output only -- this terminal does not accept input.</span>
            <span>{eventCount} event{eventCount === 1 ? '' : 's'} logged</span>
          </div>
        </div>
      </div>
    </SpecularFrame>
  )
}
