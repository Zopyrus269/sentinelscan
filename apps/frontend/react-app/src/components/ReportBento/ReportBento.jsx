import { useEffect, useRef, useState } from 'react'
import {
  ParticleCard,
  GlobalSpotlight,
  useMobileDetection,
  DEFAULT_PARTICLE_COUNT,
  DEFAULT_SPOTLIGHT_RADIUS,
} from '../MagicBento/MagicBento.jsx'
import CountUp from '../CountUp/CountUp.jsx'
import TextType from '../TextType/TextType.jsx'
import SpecularButton from '../SpecularButton/SpecularButton.jsx'
import '../MagicBento/MagicBento.css'
import './ReportBento.css'

// SentinelScan's own primary blue (Tailwind config's `primary`: #2563eb /
// `primary-container`) rather than MagicBento's stock purple -- same glow
// mechanics (GlobalSpotlight + the card's --glow-color custom property),
// just recolored to match the report page's own palette instead of
// clashing with it.
const GLOW_COLOR = '37, 99, 235'

// A single MagicBento grid (spotlight + particle cards), reused for each of
// the three report sections that get the ReactBits treatment. Every prop
// here is one of MagicBento's own defaults (see MagicBento.jsx) -- nothing
// about the animation itself is changed, only the cards' content and the
// grid's own layout classes (passed in per-section) differ from the demo.
function Bento({ className, cardClassName, cards }) {
  const gridRef = useRef(null)
  const isMobile = useMobileDetection()

  return (
    <div className={`bento-section ${className || ''}`} ref={gridRef}>
      <GlobalSpotlight
        gridRef={gridRef}
        disableAnimations={isMobile}
        enabled
        spotlightRadius={DEFAULT_SPOTLIGHT_RADIUS}
        glowColor={GLOW_COLOR}
      />
      {cards.map((card, index) => (
        <ParticleCard
          key={card.key ?? index}
          className={`magic-bento-card magic-bento-card--border-glow ${cardClassName || ''} ${card.className || ''}`}
          style={{ backgroundColor: '#120F17', '--glow-color': GLOW_COLOR, ...card.style }}
          disableAnimations={isMobile}
          particleCount={DEFAULT_PARTICLE_COUNT}
          glowColor={GLOW_COLOR}
          enableTilt={false}
          clickEffect
          enableMagnetism
        >
          {card.content}
        </ParticleCard>
      ))}
    </div>
  )
}

// Blocking-notice-before-any-report-loads case -- SpecularButton (React
// Bits), used completely unmodified, in place of report.js's old
// plain-textContent #reportError box for these specific cases (that box
// still handles every other error report.js can hit once a report load is
// actually in progress -- failed fetch, incomplete scan, etc.). Covers both
// "no scan ID was provided" (destination: the landing page, to start a new
// scan) and "historical report data not found" (destination: the
// dashboard's history tab, where View Report actually populates the data
// this page needs) -- report.js's dispatchNoScanIdNotice() sends the
// message and which of those two destinations applies for the button's
// click.
function ReportNoScanNotice() {
  const [notice, setNotice] = useState(null)

  useEffect(() => {
    const handleUpdate = event => {
      const detail = event.detail
      setNotice(detail?.message ? { message: detail.message, href: detail.href || '/' } : null)
    }
    window.addEventListener('sentinelscan:no-scan-id', handleUpdate)
    return () => window.removeEventListener('sentinelscan:no-scan-id', handleUpdate)
  }, [])

  if (!notice) return null

  return (
    <div className="flex justify-center">
      <SpecularButton className="report-no-scan-button" onClick={() => { window.location.href = notice.href }}>
        {notice.message}
      </SpecularButton>
    </div>
  )
}

export { ReportNoScanNotice }

// Report Metadata -- Target / Scan ID / Completed / Status. IDs are read
// and written by report.js's renderScanMetadata() (setText by
// getElementById), so they're kept exactly as the static markup had them;
// only the surrounding card chrome changes.
function MetaCard({ label, id, nowrap }) {
  return (
    <>
      <div className="magic-bento-card__header">
        <span className="magic-bento-card__label">{label}</span>
      </div>
      <div className="magic-bento-card__content">
        <p
          id={id}
          className={`magic-bento-card__title font-mono-md text-white ${nowrap ? 'whitespace-nowrap overflow-x-auto' : 'break-all'}`}
        >
          Loading...
        </p>
      </div>
    </>
  )
}

// "Completed" and "Status" used to round this out to four cards -- both
// were full-size dark bento cards spent on one short value, while Scan ID's
// long ID got squeezed into the same size box and wrapped. Dropped both
// (report.js's setText calls for "reportCompletedAt"/"reportStatus" are
// now no-ops -- setText already guards on the element being found) and let
// Target/Scan ID split the row evenly, each taller to fill the space the
// other two cards used to occupy (see ReportBento.css).
export function ReportMetaBento() {
  const cards = [
    { key: 'target', content: <MetaCard label="Target" id="reportTarget" nowrap /> },
    { key: 'scan-id', content: <MetaCard label="Scan ID" id="reportScanId" nowrap /> },
  ]
  return <Bento className="report-bento-meta" cardClassName="report-bento-meta-card" cards={cards} />
}

// Security Assessment Report -- the score gauge and the executive summary,
// kept at the same 4/8-column ratio the static section used
// (lg:col-span-4 / lg:col-span-8), just as two magic-bento-cards instead of
// two plain divs.
// Listens for the score report.js's renderSecurityScore() now dispatches
// (see report.js) instead of writing textContent into a "securityScore"
// element directly, and animates 0 -> score with CountUp every time a new
// value comes in -- e.g. a score of 85 counts up from 0 to 85 rather than
// snapping straight to 85.
function SecurityScoreValue() {
  const [score, setScore] = useState(0)

  useEffect(() => {
    const handleUpdate = event => setScore(Number(event.detail?.score) || 0)
    window.addEventListener('sentinelscan:security-score-update', handleUpdate)
    return () => window.removeEventListener('sentinelscan:security-score-update', handleUpdate)
  }, [])

  return <CountUp to={score} from={0} duration={3.2} className="text-display font-display text-white" />
}

function ScoreCardContent() {
  return (
    <div className="flex flex-col items-center justify-center text-center h-full">
      <h2 className="text-label-sm font-label-sm uppercase tracking-widest text-white/60 mb-md">
        Overall Security Score
      </h2>

      <div className="relative w-40 h-40 flex items-center justify-center">
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 192 192" aria-label="Overall security score">
          <circle className="text-white/10" cx="96" cy="96" fill="transparent" r="88" stroke="currentColor" strokeWidth="12" />
          <circle
            id="securityGauge"
            className="text-primary gauge-ring"
            cx="96"
            cy="96"
            fill="transparent"
            r="88"
            stroke="currentColor"
            strokeDasharray="552.92"
            strokeDashoffset="552.92"
            strokeLinecap="round"
            strokeWidth="12"
          />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <SecurityScoreValue />
          <span className="text-label-md font-label-md text-white/60">/ 100</span>
        </div>
      </div>

      <div id="riskLabel" className="mt-md text-primary font-label-md flex items-center gap-base">
        <span className="material-symbols-outlined text-sm">shield</span>
        Awaiting score
      </div>

      <p id="scoreMappingLabel" className="mt-xs text-body-sm text-white/60">
        CVSS N/A &rarr; 100/100
      </p>
    </div>
  )
}

// Mirrors SecurityScoreValue for the Max CVSS Exposure figure, listening
// for report.js's renderMaximumCvss() dispatch. Per the brief, the count-up
// only plays once a score above zero actually comes in -- the N/A / 0.0
// resting state stays a plain static value, not an animation counting up
// to zero.
function MaxCvssValue() {
  const [state, setState] = useState({ value: 0, hasScore: false })

  useEffect(() => {
    const handleUpdate = event => {
      const detail = event.detail || {}
      setState({ value: Number(detail.value) || 0, hasScore: Boolean(detail.hasScore) })
    }
    window.addEventListener('sentinelscan:max-cvss-update', handleUpdate)
    return () => window.removeEventListener('sentinelscan:max-cvss-update', handleUpdate)
  }, [])

  if (!state.hasScore) {
    return <span className="text-headline-sm font-headline-sm">0.0</span>
  }

  return <CountUp to={state.value} from={0} duration={1.2} className="text-headline-sm font-headline-sm" />
}

// Executive Summary text -- TextType (React Bits), used exactly as the
// site's hero subtitle already uses it (as='p', loop={false}) rather than
// a plain textContent write. Listens for report.js's renderExecutiveSummary()
// dispatch (see report.js) instead of owning an "executiveSummary" id
// itself. Keyed by the summary string so a genuinely new summary (a
// different scan) retypes from scratch instead of silently no-op'ing.
function ExecutiveSummaryText() {
  const [summary, setSummary] = useState(null)

  useEffect(() => {
    const handleUpdate = event => setSummary(event.detail?.summary || null)
    window.addEventListener('sentinelscan:executive-summary-update', handleUpdate)
    return () => window.removeEventListener('sentinelscan:executive-summary-update', handleUpdate)
  }, [])

  if (!summary) {
    return <p className="text-body-md text-white/70 leading-relaxed">SentinelScan is preparing the executive summary.</p>
  }

  return (
    <TextType
      key={summary}
      as="p"
      text={summary}
      loop={false}
      typingSpeed={38}
      className="text-body-md text-white/70 leading-relaxed"
    />
  )
}

function ExecutiveSummaryCardContent() {
  return (
    <div className="h-full flex flex-col">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-md gap-md">
        <div>
          <h1 className="text-headline-lg font-headline-lg text-white">Security Assessment Report</h1>
          <p id="reportIdLabel" className="text-body-sm text-white/60 font-mono-md mt-xs">
            REPORT_ID: Loading...
          </p>
        </div>

        <div
          id="maxCvssCard"
          className="text-white px-md py-sm rounded-lg flex items-center gap-sm border"
          style={{ backgroundColor: '#120F17', borderColor: `rgba(${GLOW_COLOR}, 0.35)` }}
        >
          <span className="material-symbols-outlined" style={{ color: `rgb(${GLOW_COLOR})` }}>
            priority_high
          </span>
          <div>
            <div className="text-label-sm font-label-sm text-white/60">MAX CVSS EXPOSURE</div>
            <div className="text-headline-sm font-headline-sm">
              <MaxCvssValue />
            </div>
            <div id="maxCvssSeverity" className="text-label-sm font-label-sm mt-1 text-white/70">
              NONE
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-white/10 pt-md flex-1">
        <h2 className="text-label-md font-label-md text-white mb-sm">Executive Summary</h2>
        <ExecutiveSummaryText />
      </div>

      <div className="mt-lg flex flex-col sm:flex-row gap-sm">
        <button
          id="downloadPdfButton"
          type="button"
          disabled
          className="flex items-center justify-center gap-xs px-md py-sm border border-white/20 rounded-lg text-white hover:bg-white/10 transition-colors font-label-md disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span className="material-symbols-outlined">picture_as_pdf</span>
          Download PDF
        </button>

        <button
          id="downloadJsonButton"
          type="button"
          disabled
          className="flex items-center justify-center gap-xs px-md py-sm border border-white/20 rounded-lg text-white hover:bg-white/10 transition-colors font-label-md disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span className="material-symbols-outlined">code</span>
          Download JSON
        </button>

        <button
          id="backToDashboardButton"
          type="button"
          className="flex items-center justify-center gap-xs px-md py-sm border border-white/20 rounded-lg text-white hover:bg-white/10 transition-colors font-label-md"
        >
          <span className="material-symbols-outlined">dashboard</span>
          Back to Dashboard
        </button>
      </div>
    </div>
  )
}

export function ReportSummaryBento() {
  const cards = [
    { key: 'score', className: 'report-bento-score-card', content: <ScoreCardContent /> },
    { key: 'summary', className: 'report-bento-summary-card', content: <ExecutiveSummaryCardContent /> },
  ]
  return <Bento className="report-bento-summary" cards={cards} />
}

// Risk Summary -- Critical / High / Medium / Low / Informational counts.
// One shared listener for report.js's renderRiskSummary() dispatch (all
// five numbers land in a single event), each count animated 0 -> value
// with the same CountUp component used for the score/CVSS values above --
// e.g. 5 critical findings counts up from 0 to 5 rather than snapping.
const RISK_KEYS = ['critical', 'high', 'medium', 'low', 'informational']

function useRiskSummary() {
  const [counts, setCounts] = useState({ critical: 0, high: 0, medium: 0, low: 0, informational: 0 })

  useEffect(() => {
    const handleUpdate = event => {
      const detail = event.detail || {}
      setCounts({
        critical: Number(detail.critical) || 0,
        high: Number(detail.high) || 0,
        medium: Number(detail.medium) || 0,
        low: Number(detail.low) || 0,
        informational: Number(detail.informational) || 0,
      })
    }
    window.addEventListener('sentinelscan:risk-summary-update', handleUpdate)
    return () => window.removeEventListener('sentinelscan:risk-summary-update', handleUpdate)
  }, [])

  return counts
}

function RiskCard({ label, count, accent }) {
  return (
    <>
      <div className="magic-bento-card__header">
        <span className="magic-bento-card__label uppercase">{label}</span>
      </div>
      <div className="magic-bento-card__content" style={{ color: accent }}>
        <CountUp to={count} from={0} duration={1} className="text-headline-lg font-headline-lg mt-xs" />
      </div>
    </>
  )
}

export function ReportRiskBento() {
  const counts = useRiskSummary()
  const cards = [
    { key: 'critical', content: <RiskCard label="Critical" count={counts.critical} accent="#EF4444" /> },
    { key: 'high', content: <RiskCard label="High" count={counts.high} accent="#ba1a1a" /> },
    { key: 'medium', content: <RiskCard label="Medium" count={counts.medium} accent="#F59E0B" /> },
    { key: 'low', content: <RiskCard label="Low" count={counts.low} accent={`rgb(${GLOW_COLOR})`} /> },
    { key: 'informational', content: <RiskCard label="Informational" count={counts.informational} accent="rgba(255,255,255,0.7)" /> },
  ]
  return <Bento className="report-bento-risk" cardClassName="report-bento-risk-card" cards={cards} />
}
