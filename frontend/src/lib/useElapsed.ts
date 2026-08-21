import { useEffect, useState } from 'react'

/** Seconds since `key` last changed. Pass null to stop counting. */
export function useElapsed(key: number | string | null) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    if (key === null) return
    setSeconds(0)
    const started = Date.now()
    const id = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500)
    return () => clearInterval(id)
  }, [key])

  return seconds
}
