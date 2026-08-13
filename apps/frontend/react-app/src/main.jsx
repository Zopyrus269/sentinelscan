import { StrictMode, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import FloatingLines from './components/FloatingLines/FloatingLines.jsx'
import IntroPreloader, { TIMING } from './components/IntroPreloader/IntroPreloader.jsx'
import ShinyText from './components/ShinyText/ShinyText.jsx'
import StaggeredMenu from './components/StaggeredMenu/StaggeredMenu.jsx'

// 1x1 transparent gif -- the shipped component always renders an <img>
// for its own logo slot, defaulting to a React Bits demo asset path that
// doesn't exist in this app (would 404). We don't want a second logo next
// to the "SentinelScan" brand text that's already in the static header, so
// the logo is visually hidden via CSS (see index.css) and this just avoids
// a broken-image network request for the hidden slot.
const TRANSPARENT_PIXEL =
  'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='

const NAV_ITEMS = [
  { label: 'Dashboard', link: '/dashboard', ariaLabel: 'Go to the dashboard' },
  { label: 'Reports', link: '/report', ariaLabel: 'Go to reports' },
  { label: 'Documentation', link: '/documentation', ariaLabel: 'Go to documentation' },
]

const INTRO_SEEN_KEY = 'sentinelscan_intro_seen'

// The inline head script (see each static HTML page) hides <html> before
// this bundle loads whenever the intro hasn't played yet this tab, to avoid
// a flash of page content behind the preloader. useLayoutEffect fires
// synchronously after the preloader is committed to the DOM but before the
// browser paints, so unhiding here is still flash-free.
function useRevealHtmlAfterFirstPaint() {
  useLayoutEffect(() => {
    document.documentElement.style.visibility = ''
  }, [])
}

function Intro({ onDone }) {
  const [stage, setStage] = useState('textIn')
  useRevealHtmlAfterFirstPaint()

  useEffect(() => {
    const toTextHold = setTimeout(() => setStage('textHold'), TIMING.textInMs)
    const toTextOut = setTimeout(
      () => setStage('textOut'),
      TIMING.textInMs + TIMING.textHoldMs,
    )
    const toOpen = setTimeout(
      () => setStage('open'),
      TIMING.textInMs + TIMING.textHoldMs + TIMING.textOutMs + TIMING.blackPauseMs,
    )
    const toDone = setTimeout(
      onDone,
      TIMING.textInMs + TIMING.textHoldMs + TIMING.textOutMs + TIMING.blackPauseMs + TIMING.openMs,
    )
    return () => {
      clearTimeout(toTextHold)
      clearTimeout(toTextOut)
      clearTimeout(toOpen)
      clearTimeout(toDone)
    }
  }, [onDone])

  return <IntroPreloader stage={stage} />
}

// FloatingLines listens for pointermove/pointerleave on its own <canvas>,
// which is correct for the React Bits demo where it's a normal top-level
// element. Here it's a fixed, z-index:-1 site-wide background, so the
// browser always routes real cursor events to whatever page content is
// visually on top -- the canvas never sees them. This bridges real cursor
// position into the canvas via dispatchEvent (which invokes listeners on
// the target directly, bypassing hit-testing) so the component's own,
// unmodified interactivity logic still fires correctly.
function SiteBackground() {
  const wrapperRef = useRef(null)

  useEffect(() => {
    const wrapper = wrapperRef.current
    if (!wrapper) return

    const getCanvas = () => wrapper.querySelector('canvas')

    const forward = (type, clientX, clientY) => {
      const canvas = getCanvas()
      if (!canvas) return
      canvas.dispatchEvent(new PointerEvent(type, { clientX, clientY, bubbles: false }))
    }

    const handlePointerMove = event => forward('pointermove', event.clientX, event.clientY)
    const handlePointerLeave = () => forward('pointerleave', 0, 0)

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('blur', handlePointerLeave)
    document.addEventListener('mouseleave', handlePointerLeave)

    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('blur', handlePointerLeave)
      document.removeEventListener('mouseleave', handlePointerLeave)
    }
  }, [])

  return (
    <div ref={wrapperRef} id="sentinelscan-react-bg">
      <FloatingLines />
    </div>
  )
}

// The background and the intro overlay are mounted as two independent React
// roots (rather than siblings in one tree) so that unmounting the intro can
// never affect the background's reconciliation, even indirectly -- the
// FloatingLines WebGL scene and its clock keep running the whole time and
// are never touched when the intro finishes.
const bgMountPoint = document.createElement('div')
document.body.insertBefore(bgMountPoint, document.body.firstChild)

createRoot(bgMountPoint).render(
  <StrictMode>
    <SiteBackground />
  </StrictMode>,
)

const navMenuMountPoint = document.createElement('div')
document.body.insertBefore(navMenuMountPoint, document.body.firstChild)

createRoot(navMenuMountPoint).render(
  <StrictMode>
    <StaggeredMenu
      className="sentinelscan-nav-menu"
      isFixed
      position="right"
      items={NAV_ITEMS}
      displaySocials={false}
      displayItemNumbering
      logoUrl={TRANSPARENT_PIXEL}
      colors={['#60a5fa', '#2563eb']}
      accentColor="#2563eb"
      menuButtonColor="#0f172a"
      openMenuButtonColor="#0f172a"
    />
  </StrictMode>,
)

const brandMountPoint = document.getElementById('sentinelscan-brand-shiny')
if (brandMountPoint) {
  createRoot(brandMountPoint).render(
    <StrictMode>
      <ShinyText text="SentinelScan" speed={3} />
    </StrictMode>,
  )
}

if (sessionStorage.getItem(INTRO_SEEN_KEY) !== '1') {
  const introMountPoint = document.createElement('div')
  document.body.insertBefore(introMountPoint, document.body.firstChild)

  const introRoot = createRoot(introMountPoint)
  introRoot.render(
    <StrictMode>
      <Intro
        onDone={() => {
          sessionStorage.setItem(INTRO_SEEN_KEY, '1')
          introRoot.unmount()
          introMountPoint.remove()
        }}
      />
    </StrictMode>,
  )
}
