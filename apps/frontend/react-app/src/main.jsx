import { StrictMode, useEffect, useRef } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import FloatingLines from './components/FloatingLines/FloatingLines.jsx'

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

const mountPoint = document.createElement('div')
document.body.insertBefore(mountPoint, document.body.firstChild)

createRoot(mountPoint).render(
  <StrictMode>
    <SiteBackground />
  </StrictMode>,
)
