import { useEffect, useRef, useState } from 'react'
import { gsap } from 'gsap'
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

// ScrollReveal.jsx only ever reveals *in* -- dim/blurred toward fully sharp
// -- as an element scrolls up through the viewport, finishing at whatever
// `end` point is given. Pointed at 'center center' (the paragraph's own
// center aligning with the viewport's center), that's exactly "fully
// visible by the time it reaches the middle of the screen" -- but
// ScrollReveal has no matching reverse for the second half of the scroll:
// past center, the words would just stay fully revealed all the way until
// they've scrolled completely out of view, instead of dimming back down as
// they leave. CrawlParagraph (below) adds that missing second half as an
// independent GSAP ScrollTrigger on the same `.word` spans ScrollReveal
// already rendered -- ScrollReveal.jsx itself stays untouched; this only
// reads the words it split out and layers a mirrored exit tween on top, so
// the whole thing plays as reveal-toward-center, then fade-away-past-center,
// reversing cleanly in both directions since both halves are scrub-linked.
const ENTRANCE_END = { rotationEnd: 'center center', wordAnimationEnd: 'center center' }

// Shown instead of the five real paragraphs whenever there's no report data
// to reveal yet -- whether that's because no scan has been run at all, or
// the fetch simply hasn't resolved yet. Previously this slot showed five
// repeated "This section is loading." placeholders indefinitely whenever no
// scan_id was even present (report.js never calls loadReport() in that
// case, so the real update event never fires) -- one honest single-line
// prompt replaces that, revealed the same scroll-scrubbed way as real
// content instead of sitting visible above the fold immediately.
const EMPTY_PROMPT = 'Run a scan to see your report summary here.'

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

// Wraps one ScrollReveal instance in a plain div so the mirrored exit fade
// below can trigger off the exact same box ScrollReveal itself measures
// (the wrapper has no margin/padding of its own -- see
// .report-crawl-paragraph in ReportCrawl.css -- so its bounds match
// ScrollReveal's own <h2> exactly).
function CrawlParagraph({ text, containerClassName }) {
  const wrapperRef = useRef(null)

  useEffect(() => {
    const wrapper = wrapperRef.current
    if (!wrapper) return

    // ScrollReveal renders the `.word` spans synchronously as part of its
    // own JSX (a useMemo, not something built up in an effect), so they're
    // already in the DOM by the time this effect runs -- no race to wait out.
    const words = wrapper.querySelectorAll('.word')
    if (!words.length) return

    const exitTween = gsap.fromTo(
      words,
      { opacity: 1, filter: 'blur(0px)' },
      {
        ease: 'none',
        opacity: 0.12,
        filter: 'blur(3px)',
        stagger: 0.05,
        // fromTo() defaults immediateRender to true -- without this, the
        // instant this tween is created it immediately snaps `words` to its
        // "from" state (opacity 1, no blur) regardless of actual scroll
        // position, stomping on ScrollReveal's own entrance tween (created
        // moments earlier, same elements, same properties) which had
        // correctly rendered them dim/blurred at rest. That's the glitch:
        // every paragraph would flash fully visible/sharp right on mount,
        // for the first paragraph the visitor happened to open the page
        // near) -- confirmed via live-inspecting a fresh tab, only fixed
        // once real scrolling forced both tweens' scrub progress to
        // recompute and overwrite the bad snapshot. Both tweens are
        // scrub-linked to scroll position anyway, so neither one needs an
        // immediate render at creation time -- the correct value follows
        // from the actual scroll position the first time either updates.
        immediateRender: false,
        scrollTrigger: {
          trigger: wrapper,
          start: 'center center',
          end: 'bottom top',
          scrub: true,
        },
      },
    )

    return () => {
      exitTween.scrollTrigger?.kill()
      exitTween.kill()
    }
  }, [text])

  return (
    <div ref={wrapperRef} className="report-crawl-paragraph">
      <ScrollReveal
        containerClassName={containerClassName}
        textClassName="report-crawl-reveal-text"
        baseOpacity={0.12}
        baseRotation={2}
        blurStrength={3}
        {...ENTRANCE_END}
      >
        {text}
      </ScrollReveal>
    </div>
  )
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
      {loaded ? (
        TEXT_KEYS.map(textKey => (
          <CrawlParagraph
            key={`${textKey}-${loaded}`}
            text={text[textKey]}
            containerClassName="report-crawl-reveal"
          />
        ))
      ) : (
        <CrawlParagraph
          key="empty-prompt"
          text={EMPTY_PROMPT}
          containerClassName="report-crawl-reveal report-crawl-empty"
        />
      )}
    </div>
  )
}
