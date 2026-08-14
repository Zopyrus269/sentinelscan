import { useEffect, useRef, useState } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import './DocsExplorer.css'

gsap.registerPlugin(ScrollTrigger)

// Recreated from Skiper UI's "Side Scroll Navigation" (skiper60) -- a
// Premium/paywalled component (confirmed live on skiper-ui.com: it's listed
// under the ScrollEffects collection as a Pro item, not in the free
// registry, and `npx shadcn add @skiper-ui/skiper60` 404s because of that),
// so there's no source to vendor verbatim here the way this project's other
// React Bits/Skiper components are. This is a from-scratch rebuild of the
// same mechanic observed on its own live demo page: a rail of section
// labels pinned to the left-middle of the viewport, a thin track with a
// short highlight segment that slides and resizes to sit next to whichever
// section is currently in view (IntersectionObserver-driven), dimmed/
// inactive labels brightening to bold white when active, and a smooth
// scroll-to on click. Extended further than the demo itself: each section
// only reaches full visibility at the vertical center of the screen,
// fading in on the way there and back out past it (see the ScrollTrigger
// effect below), so the rail's active label is always "what's centered on
// screen right now" rather than just "what's anywhere on screen."
const SECTIONS = [
  {
    id: 'overview',
    label: 'Overview',
    heading: 'What SentinelScan Does',
    paragraphs: [
      'Gemini is the only decision-maker here.',
      'It picks which worker runs next, and why.',
      'Workers hold zero business logic of their own.',
    ],
  },
  {
    id: 'authorized-use',
    label: 'Authorized Use',
    heading: 'Authorized Use Only',
    paragraphs: [
      'Every scan assumes explicit authorization.',
      'Something you own, or have written permission for.',
      'No exploit code -- just recon, assessment, reporting.',
    ],
  },
  {
    id: 'reports',
    label: 'Reading Your Report',
    heading: 'Reading Your Report',
    paragraphs: [
      'Every report opens with a security score.',
      'Then the highest CVSS base score found.',
      'A severity breakdown, then a plain summary.',
      'PDF and JSON downloads, one click away.',
    ],
  },
  {
    id: 'privacy',
    label: 'Privacy Policy',
    heading: 'Privacy Policy',
    paragraphs: ['We store only what accounts and scans need.', 'We never share personal information with anyone.'],
    groups: [
      {
        heading: 'Data Security',
        paragraphs: ['Credentials are stored using password hashing.', 'Scan results and reports live on the server.'],
      },
      {
        heading: 'Cookies and Sessions',
        paragraphs: ['A secure session cookie keeps you signed in.'],
      },
    ],
  },
  {
    id: 'terms',
    label: 'Terms of Service',
    heading: 'Terms of Service',
    paragraphs: ['Use this platform only for authorized scanning.'],
    groups: [
      {
        heading: 'Use of the Platform',
        paragraphs: ['Only for authorized web security assessments.'],
      },
      {
        heading: 'Account Security',
        paragraphs: ['Keep credentials private -- you own the activity.'],
      },
      {
        heading: 'Limitations',
        paragraphs: ['Provided "as is." Confirm permission before scanning.'],
      },
    ],
  },
  {
    id: 'responsible-disclosure',
    label: 'Responsible Disclosure',
    heading: 'Reporting Vulnerabilities',
    paragraphs: [
      'SentinelScan performs passive, read-only recon.',
      'We never exploit vulnerabilities or targets.',
      'Found a platform bug? Email us privately:',
      'sentinelscan@gmail.com',
      'Good-faith research is always considered authorized.',
    ],
  },
  {
    id: 'status',
    label: 'System Status',
    heading: 'API Status & Health',
    paragraphs: ['The backend exposes a lightweight health endpoint.'],
    list: ['Health endpoint: /health', 'API base: /api/v1'],
  },
  {
    id: 'support',
    label: 'Support',
    heading: 'Need Help?',
    paragraphs: ['Most questions are answered above.', 'Still stuck? Just start a scan and follow along.'],
    links: [
      { href: '/', text: 'Start a New Scan' },
      { href: '/dashboard', text: 'Go to Dashboard' },
    ],
  },
]

export default function DocsExplorer() {
  const [activeId, setActiveId] = useState(SECTIONS[0].id)
  const [indicator, setIndicator] = useState({ top: 0, height: 0 })
  const sectionRefs = useRef({})
  const navRefs = useRef({})

  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id)
          }
        })
      },
      // A section counts as "current" once it's crossed 15% down from the
      // top of the viewport and hasn't yet passed 70% down -- matches the
      // live skiper60 demo's feel of the rail updating as a heading nears
      // the top of the screen, not only once it's fully centered.
      { rootMargin: '-15% 0px -70% 0px', threshold: 0 },
    )

    Object.values(sectionRefs.current).forEach(el => el && observer.observe(el))
    return () => observer.disconnect()
  }, [])

  // Deep links like /documentation#privacy (the site-wide footer's Privacy
  // Policy/Terms links, now that those used to be their own pages) rely on
  // the browser jumping straight to that section on load -- but the section
  // elements don't exist in the initial HTML at all, only after this
  // component mounts, so the browser's own fragment-scroll-on-navigation
  // never has anything to find. This does it manually once the real DOM
  // exists, landing the target section centered the same way clicking its
  // rail label would.
  useEffect(() => {
    const hash = window.location.hash.slice(1)
    if (!hash || !sectionRefs.current[hash]) return
    sectionRefs.current[hash].scrollIntoView({ behavior: 'auto', block: 'center' })
  }, [])

  // The IntersectionObserver above only ever looks at a 15%-30% band down
  // the viewport -- fine for every section in the middle of the page, but
  // the last one (Support) is short and sits right before the footer, so
  // its own top edge can run out of page to scroll through before it ever
  // reaches that band: the user hits the true bottom of the document while
  // the rail is still stuck on "System Status". This is a plain, direct
  // check for "the page is scrolled all the way to the bottom" that
  // overrides the observer in exactly that case, so the last item always
  // lights up once there's nothing left to scroll -- regardless of how
  // short it is relative to the band's geometry.
  useEffect(() => {
    const lastSectionId = SECTIONS[SECTIONS.length - 1].id

    const handleScroll = () => {
      const scrolledToBottom =
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2
      if (scrolledToBottom) {
        setActiveId(lastSectionId)
      }
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  useEffect(() => {
    const activeEl = navRefs.current[activeId]
    if (!activeEl) return
    setIndicator({ top: activeEl.offsetTop, height: activeEl.offsetHeight })
  }, [activeId])

  // Each section only appears fully at the vertical middle of the screen --
  // dim while it's still below center on the way in, full at center, then
  // dimming back down as it continues past center on the way out. Same
  // "peak at the middle, reversible on scroll up" idea as the report page's
  // paragraph crawl (see CrawlParagraph in ReportCrawl.jsx), but as one
  // whole-block opacity fade rather than a word-by-word reveal -- these
  // sections mix headings, multi-paragraph prose, lists, and links, so
  // there's no single plain-text string to split into words the way
  // ScrollReveal does for the report page's short paragraphs.
  useEffect(() => {
    const tweens = SECTIONS.map(section => {
      const el = sectionRefs.current[section.id]
      if (!el) return null

      const entrance = gsap.fromTo(
        el,
        { opacity: 0.15 },
        {
          opacity: 1,
          ease: 'none',
          scrollTrigger: {
            trigger: el,
            start: 'top bottom-=10%',
            end: 'center center',
            scrub: true,
          },
        },
      )

      const exit = gsap.fromTo(
        el,
        { opacity: 1 },
        {
          opacity: 0.15,
          ease: 'none',
          scrollTrigger: {
            trigger: el,
            start: 'center center',
            end: 'bottom top',
            scrub: true,
          },
        },
      )

      return [entrance, exit]
    })

    return () => {
      tweens.flat().forEach(tween => {
        if (!tween) return
        tween.scrollTrigger?.kill()
        tween.kill()
      })
    }
  }, [])

  const handleNavClick = id => {
    sectionRefs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  return (
    <div className="docs-explorer">
      <aside className="docs-explorer-nav">
        <div className="docs-explorer-nav-track">
          <span
            className="docs-explorer-nav-indicator"
            style={{ transform: `translateY(${indicator.top}px)`, height: `${indicator.height}px` }}
            aria-hidden="true"
          />
          {SECTIONS.map(section => (
            <button
              key={section.id}
              ref={el => {
                navRefs.current[section.id] = el
              }}
              type="button"
              className={`docs-explorer-nav-item${activeId === section.id ? ' is-active' : ''}`}
              onClick={() => handleNavClick(section.id)}
            >
              {section.label}
            </button>
          ))}
        </div>
      </aside>

      <div className="docs-explorer-content">
        {SECTIONS.map(section => (
          <section
            key={section.id}
            id={section.id}
            ref={el => {
              sectionRefs.current[section.id] = el
            }}
            className="docs-explorer-section"
          >
            <h2>{section.heading}</h2>
            {section.paragraphs?.map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
            {section.list && (
              <ul>
                {section.list.map(item => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
            {section.groups?.map((group, groupIndex) => (
              <div className="docs-explorer-group" key={groupIndex}>
                <h3>{group.heading}</h3>
                {group.paragraphs?.map((paragraph, index) => (
                  <p key={index}>{paragraph}</p>
                ))}
                {group.list && (
                  <ul>
                    {group.list.map(item => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}
                {group.endpoints && (
                  <div className="docs-explorer-endpoints">
                    {group.endpoints.map(endpoint => (
                      <div className="docs-explorer-endpoint" key={`${endpoint.method}-${endpoint.path}`}>
                        <div className="docs-explorer-endpoint-head">
                          <span className={`docs-explorer-method docs-explorer-method--${endpoint.method.toLowerCase()}`}>
                            {endpoint.method}
                          </span>
                          <code>{endpoint.path}</code>
                        </div>
                        <p>{endpoint.description}</p>
                      </div>
                    ))}
                  </div>
                )}
                {group.code && (
                  <pre className="docs-explorer-code">
                    <code>{group.code}</code>
                  </pre>
                )}
              </div>
            ))}
            {section.links && (
              <div className="docs-explorer-links">
                {section.links.map(link => (
                  <a key={link.href} href={link.href}>
                    {link.text} &rarr;
                  </a>
                ))}
              </div>
            )}
          </section>
        ))}
      </div>
    </div>
  )
}
