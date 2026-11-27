// TEM footers have a row of regularly spaced dark ticks on white paper.
// A saved calibration may cover just one of those intervals.
export function scaleBarBounds(image, line) {
  const { naturalWidth: w, naturalHeight: h } = image
  const y = line ? Math.round((line[0].y + line[1].y) / 2) : Math.round(h * .85)
  const left = line ? Math.min(line[0].x, line[1].x) : 0
  const right = line ? Math.max(line[0].x, line[1].x) : w
  const top = Math.max(0, y - Math.ceil(h * .12))
  const bottom = Math.min(h, y + Math.ceil(h * .16))
  const fallback = { left: 0, right: w, top, bottom }
  if (bottom <= top) return fallback
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = bottom - top
  const ctx = canvas.getContext('2d')
  let data
  try {
    ctx.drawImage(image, 0, -top)
    data = ctx.getImageData(0, 0, w, canvas.height).data
  } catch {
    return fallback
  }
  let best = []
  let tickY = y
  for (let row = 0; row < canvas.height; row++) {
    const ticks = []
    let start = -1
    let white = 0
    for (let x = 0; x <= w; x++) {
      const gray = x < w ? data[(row * w + x) * 4] : 255
      if (gray > 215) white++
      if (gray < 140 && start < 0) start = x
      if (gray >= 140 && start >= 0) {
        if (x - start <= Math.max(3, w / 220)) ticks.push((start + x - 1) / 2)
        start = -1
      }
    }
    if (white < .65 * w) continue
    for (let i = 0; i < ticks.length - 3; i++) {
      const step = ticks[i+1] - ticks[i]
      if (step < Math.max(4, w / 180)) continue
      let j = i + 2
      while (j < ticks.length && Math.abs(ticks[j] - ticks[j-1] - step) <= Math.max(1.5, step * .10)) j++
      if (j-i > Math.max(3, best.length) && (!line || (ticks[i] <= left + step / 2 && ticks[j-1] >= right - step / 2))) {
        best = ticks.slice(i, j)
        tickY = top + row
      }
    }
  }
  if (!best.length) return fallback
  const margin = Math.max(w * .045, best[1] - best[0])
  return { left: Math.max(0, Math.min(line ? left : w, best[0]) - margin),
    right: Math.min(w, Math.max(line ? right : 0, best.at(-1)) + margin),
    top: Math.max(0, Math.min(tickY, line ? y : tickY) - h * .045),
    bottom: Math.min(h, Math.max(tickY, line ? y : tickY) + h * .085) }
}
