import { useEffect, useState } from 'react'
import ScrollReveal from '../ScrollReveal/ScrollReveal.jsx'
import './ReportCrawl.css'

// Five short paragraphs -- Assessment Findings, CVSS Scoring, Worker
// Findings, Sentinel AI Recommendations, Raw Report Data, in that order --
// each revealed word-by-word (blur -> sharp, opacity 0 -> 1) as it scrolls
// through the viewport, using ScrollReveal (React Bits) completely
// unmodified. No card grid, no boxed panel, no per-section
// label/icon/heading chrome -- just plain running prose, one paragraph
// after another, the same way an article would read.
const TEXT_KEYS = ['findingsText', 'cvssText', 'workerText', 'recommendationsText', 'rawJsonText']

const LOADING_TEXT = 'This section is loading.'

// report.js's fetches can resolve fast enough that dispatchReportCrawl()
// runs and dispatches before this component's own useEffect below has
// attached its listener -- confirmed live: with six nested ScrollReveal/
// GSAP instances to mount, this component's effect flush lands measurably
// later than the simpler score/risk-summary listeners elsewhere, so it can
// end up listening for an event that already fired. report.js latches its
// last dispatch on window for exactly this case; reading it synchronously
// here (in addition to listening for future live events) means a missed
// event is recovered on mount instead of leaving the paragraphs stuck on
// "this section is loading" forever.
function readLatchedCrawlData() {
  return typeof window !== 'undefined' ? window.__sentinelscanReportCrawl : undefined
}

export default function ReportCrawl() {
  const [text, setText] = useState({})
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    // The lazy useState initializer alone isn't enough -- it only runs at
    // the exact instant this component first renders, which is typically
    // still before report.js's fetches resolve. This effect runs slightly
    // later (after mount), so the latch may be populated by now even
    // though it wasn't yet at that first render; checking again here
    // catches that window without waiting for a live event that may
    // already have come and gone.
    const latched = readLatchedCrawlData()
    if (latched) {
      setText(latched)
      setLoaded(true)
    }

    const handleUpdate = event => {
      if (!event.detail) return
      setText(event.detail)
      setLoaded(true)
    }
    window.addEventListener('sentinelscan:report-crawl-update', handleUpdate)
    return () => window.removeEventListener('sentinelscan:report-crawl-update', handleUpdate)
  }, [])

  return (
    <div className="report-crawl">
      {/* GSAP quirk, confirmed by live-inspecting this exact page in
          Chrome: the very first ScrollTrigger created on a page gets its
          start/end measured before the rest of that render's layout has
          settled, and it stays wrong afterwards -- ScrollTrigger.refresh()
          does not correct it. Every other instance scrubs correctly in
          both directions; only whichever one happens to be first does not.
          This hidden, zero-size instance exists purely to be that "first"
          one instead of the real first paragraph -- it owns the bug so
          Assessment Findings doesn't. */}
      <div aria-hidden="true">
        <ScrollReveal key={`warmup-${loaded}`} containerClassName="report-crawl-warmup" textClassName="report-crawl-warmup">
          {' '}
        </ScrollReveal>
      </div>
      {TEXT_KEYS.map(textKey => (
        <ScrollReveal
          key={`${textKey}-${loaded}`}
          containerClassName="report-crawl-reveal"
          textClassName="report-crawl-reveal-text"
          baseOpacity={0.12}
          baseRotation={2}
          blurStrength={3}
        >
          {loaded ? text[textKey] : LOADING_TEXT}
        </ScrollReveal>
      ))}
    </div>
  )
}
