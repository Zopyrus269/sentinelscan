import GooeyNav from '../GooeyNav/GooeyNav.jsx'
import './GooeyActionNav.css'

// GooeyNav (React Bits) is a persistent-active-tab nav: its <a href> items
// navigate natively and there's no onItemClick prop to hook into -- it has
// no concept of "run this one-off action" the way a button does. Rather
// than editing GooeyNav.jsx itself (kept byte-for-byte vendor), each item's
// href here is just a local anchor id used to identify which one was
// clicked; this wrapper intercepts the click on the way up (bubble phase
// still runs before the browser's default anchor navigation), calls
// preventDefault so the page never actually jumps to "#action-0" etc., and
// calls the matching callback instead -- after a delay (see
// ANIMATION_DURATION_MS) so the gooey particle/pill animation actually gets
// to play out before the real action (view report, download, sign out)
// fires, instead of firing instantly while the animation is still visibly
// in progress.
//
// Generic over any number of actions -- used for the account history
// cards' three actions (View Report/Download PDF/Download JSON) and for
// the profile dropdown's single Sign Out action alike.

// Matches the animationTime/timeVariance passed to GooeyNav below. GooeyNav
// computes its own particle-burst lifetime the same way internally
// (`bubbleTime = animationTime * 2 + timeVariance`, see makeParticles in
// GooeyNav.jsx) -- this is that same total.
const ANIMATION_TIME = 500
const TIME_VARIANCE = 300
const ANIMATION_DURATION_MS = ANIMATION_TIME * 2 + TIME_VARIANCE

export default function GooeyActionNav({ actions, className = '' }) {
  const items = actions.map((action, index) => ({ label: action.label, href: `#action-${index}` }))

  const handleClick = event => {
    const anchor = event.target.closest('a')
    if (!anchor) return
    event.preventDefault()
    const index = items.findIndex(item => item.href === anchor.getAttribute('href'))
    const handler = actions[index]?.onClick
    if (!handler) return
    setTimeout(handler, ANIMATION_DURATION_MS)
  }

  return (
    <div className={`gooey-action-nav ${className}`} onClick={handleClick}>
      <GooeyNav
        items={items}
        particleCount={10}
        animationTime={ANIMATION_TIME}
        timeVariance={TIME_VARIANCE}
        initialActiveIndex={-1}
      />
    </div>
  )
}
