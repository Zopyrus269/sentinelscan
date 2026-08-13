import { StrictMode, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import FloatingLines from './components/FloatingLines/FloatingLines.jsx'
import IntroPreloader, { TIMING } from './components/IntroPreloader/IntroPreloader.jsx'
import ShinyText from './components/ShinyText/ShinyText.jsx'
import StaggeredMenu from './components/StaggeredMenu/StaggeredMenu.jsx'
import ShutterText from './components/ShutterText/ShutterText.jsx'
import TextType from './components/TextType/TextType.jsx'
import CircularText from './components/CircularText/CircularText.jsx'
import { Link000, Link001 } from './components/ui/skiper-ui/skiper40.jsx'
import { PlaceholdersAndVanishInput } from './components/ui/placeholders-and-vanish-input.jsx'
import SplashCursor from './components/SplashCursor.jsx'

// 1x1 transparent gif -- the shipped component always renders an <img>
// for its own logo slot, defaulting to a React Bits demo asset path that
// doesn't exist in this app (would 404). We don't want a second logo next
// to the "SentinelScan" brand text that's already in the static header, so
// the logo is visually hidden via CSS (see index.css) and this just avoids
// a broken-image network request for the hidden slot.
const TRANSPARENT_PIXEL =
  'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='

const NAV_ITEMS = [
  { label: 'Home', link: '/', ariaLabel: 'Go to the home page' },
  { label: 'Dashboard', link: '/dashboard', ariaLabel: 'Go to the dashboard' },
  { label: 'Reports', link: '/report', ariaLabel: 'Go to reports' },
  { label: 'Documentation', link: '/documentation', ariaLabel: 'Go to documentation' },
]

const INTRO_SEEN_KEY = 'sentinelscan_intro_seen'
const INTRO_REVEAL_EVENT = 'sentinelscan:intro-reveal-start'

// Gates the hero ShutterText reveal on the intro preloader instead of
// letting it play immediately at mount. On a first-time visit this
// component mounts (and framer-motion evaluates its `initial` state)
// while the intro overlay is still fully covering the page, so an
// ungated reveal finishes underneath the overlay and visitors only ever
// see the settled final text once the intro uncovers it.
//
// The event this waits for fires the moment the intro's stairs *start*
// uncovering the page (stage 'open'), not when they finish -- starting
// the shutter animation in step with the curtains opening, rather than
// after, is what sells the "site booted up instantly" effect. Returning
// visitors within the same tab session never see the intro at all
// (INTRO_SEEN_KEY already set), so this starts true for them and the
// reveal plays immediately on mount as before.
function useIntroRevealStarted() {
  const [started, setStarted] = useState(() => sessionStorage.getItem(INTRO_SEEN_KEY) === '1')

  useEffect(() => {
    if (started) return
    const handleStart = () => setStarted(true)
    window.addEventListener(INTRO_REVEAL_EVENT, handleStart)
    return () => window.removeEventListener(INTRO_REVEAL_EVENT, handleStart)
  }, [started])

  return started
}

function HeroShutterSection() {
  const revealStarted = useIntroRevealStarted()
  return <ShutterText text="AI-Powered Website Security Scanner" start={revealStarted} />
}

// TextType has no `start`/hold prop like ShutterText's -- it begins typing
// as soon as it mounts. So instead of a prop, this gates the *mount itself*
// on the same useIntroRevealStarted() hook/event as HeroShutterSection
// above, which fires at the same moment (the instant the intro's stairs
// begin opening). Both components therefore start their animations in the
// same React commit -- this is the same timing, reused, not re-derived.
function HeroSubtitleSection() {
  const revealStarted = useIntroRevealStarted()
  if (!revealStarted) return null
  return (
    <TextType
      as="p"
      loop={false}
      className="font-body-lg text-body-lg text-on-surface-variant"
      text="Perform authorized security reconnaissance using AI-guided DNS, WHOIS, SSL, HTTP header, cookie, sitemap, robots.txt, port and CVSS workers."
    />
  )
}

const SCAN_INPUT_PLACEHOLDERS = [
  'example.com',
  'yourcompany.com',
  'staging.yourapp.dev',
  'shop.yourbrand.io',
]

// PlaceholdersAndVanishInput is a self-contained form with its own text
// input and submit button -- it doesn't know about this app's scan flow.
// The static page still ships a hidden #targetInput/#openConsentButton pair
// (app.js's existing consent-modal flow reads/clicks those by id), so this
// wrapper just mirrors typed input into the hidden field and forwards
// submit into a click on the hidden button, leaving app.js and the
// component itself both untouched.
function HeroScanInput() {
  const handleChange = event => {
    const hiddenInput = document.getElementById('targetInput')
    if (hiddenInput) hiddenInput.value = event.target.value
  }

  const handleSubmit = () => {
    document.getElementById('openConsentButton')?.click()
  }

  return (
    <PlaceholdersAndVanishInput
      placeholders={SCAN_INPUT_PLACEHOLDERS}
      onChange={handleChange}
      onSubmit={handleSubmit}
    />
  )
}

// onHover is left at the component's own default ('speedUp') -- that's
// the shipped React Bits behavior: an infinite loop that keeps spinning at
// the faster pace for as long as the cursor stays inside, then eases back
// to the normal pace on mouse-leave (rather than a one-shot spin that
// settles and stops, which is what a 'pause'/spring transition would do).
// The phrase repeats with a bullet separator so the ring reads as a
// continuous loop instead of stopping short partway around with a gap.
function FooterBrandMark() {
  return (
    <div
      className="ss-footer-brandmark"
      role="img"
      aria-label="SentinelScan -- AI powered"
    >
      <CircularText
        text="SENTINEL SCANNER • AI POWERED • "
        spinDuration={22}
        className="ss-footer-brandmark-ring"
      />
    </div>
  )
}

const FOOTER_LINKS = [
  { label: 'Privacy Policy', href: '/privacy' },
  { label: 'GitHub', href: 'https://github.com/Zopyrus269/sentinelscan', external: true, icon: true },
  { label: 'Contact', href: 'mailto:security@sentinelscan.example' },
  { label: 'Terms and Conditions', href: '/terms' },
]

// Skiper 40's Link000 variant (no trailing icon) is the default: Link001-005
// append an arrow <svg> after the text, which widens the anchor's own
// content box beyond the word -- since the underline is `before:w-full`
// (100% of that box, not of the text node), the icon would stretch the line
// past the last letter. Link000 has no icon, so its box width equals the
// text's rendered width and the line's right edge lands exactly on the last
// letter, with nothing after it to overextend into.
//
// GitHub is the deliberate exception: Link001 is used there instead, which
// both ships the trailing arrow icon and already hardcodes target="_blank"
// -- exactly the external-link treatment GitHub needs. Its underline runs
// under the icon too, which is expected for this one link.
function FooterLinks() {
  return (
    <nav className="ss-footer-links" aria-label="Footer">
      {FOOTER_LINKS.map(({ label, href, external, icon }) => {
        if (icon) {
          return (
            <Link001 key={label} href={href}>
              {label}
            </Link001>
          )
        }
        return (
          <Link000
            key={label}
            href={href}
            target={external ? '_blank' : undefined}
            rel={external ? 'noopener noreferrer' : undefined}
          >
            {label}
          </Link000>
        )
      })}
    </nav>
  )
}

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

function Intro({ onRevealStart, onDone }) {
  const [stage, setStage] = useState('textIn')
  useRevealHtmlAfterFirstPaint()

  useEffect(() => {
    const toTextHold = setTimeout(() => setStage('textHold'), TIMING.textInMs)
    const toTextOut = setTimeout(
      () => setStage('textOut'),
      TIMING.textInMs + TIMING.textHoldMs,
    )
    const toOpen = setTimeout(
      () => {
        setStage('open')
        onRevealStart()
      },
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
  }, [onRevealStart, onDone])

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

// Own independent root for the same reason as the background above --
// SplashCursor listens on `window` directly and drives its own rAF loop,
// so it doesn't need to live inside any particular page element.
const splashCursorMountPoint = document.createElement('div')
document.body.insertBefore(splashCursorMountPoint, document.body.firstChild)

createRoot(splashCursorMountPoint).render(
  <StrictMode>
    <SplashCursor RAINBOW_MODE={false} COLOR="#ffffff" MOVE_FULL_INTENSITY_BOOST={1.4} />
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

const heroShutterMountPoint = document.getElementById('sentinelscan-hero-shutter')
if (heroShutterMountPoint) {
  createRoot(heroShutterMountPoint).render(
    <StrictMode>
      <HeroShutterSection />
    </StrictMode>,
  )
}

const heroInputMountPoint = document.getElementById('sentinelscan-hero-input')
if (heroInputMountPoint) {
  createRoot(heroInputMountPoint).render(
    <StrictMode>
      <HeroScanInput />
    </StrictMode>,
  )
}

const heroSubtitleMountPoint = document.getElementById('sentinelscan-hero-subtitle')
if (heroSubtitleMountPoint) {
  createRoot(heroSubtitleMountPoint).render(
    <StrictMode>
      <HeroSubtitleSection />
    </StrictMode>,
  )
}

const footerBrandMountPoint = document.getElementById('sentinelscan-footer-brand')
if (footerBrandMountPoint) {
  createRoot(footerBrandMountPoint).render(
    <StrictMode>
      <FooterBrandMark />
    </StrictMode>,
  )
}

const footerLinksMountPoint = document.getElementById('sentinelscan-footer-links')
if (footerLinksMountPoint) {
  createRoot(footerLinksMountPoint).render(
    <StrictMode>
      <FooterLinks />
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
        onRevealStart={() => {
          window.dispatchEvent(new Event(INTRO_REVEAL_EVENT))
        }}
        onDone={() => {
          sessionStorage.setItem(INTRO_SEEN_KEY, '1')
          introRoot.unmount()
          introMountPoint.remove()
        }}
      />
    </StrictMode>,
  )
}
