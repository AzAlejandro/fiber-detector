// El punto inicial sigue sobre la circunferencia aunque el campo limite el radio.
export function circleFromDiameter(start, end, width, height) {
  const dx = end.x - start.x
  const dy = end.y - start.y
  const length = Math.hypot(dx, dy)
  if (!length) return { center: { x: start.x, y: start.y }, radius: 0 }
  const ux = dx / length, uy = dy / length
  const limit = (space, rate) => rate > 0 ? space / rate : Infinity
  const radius = Math.min(length / 2,
    limit(start.x, 1 - ux), limit(width - 1 - start.x, 1 + ux),
    limit(start.y, 1 - uy), limit(height - 1 - start.y, 1 + uy))
  const center = { x: start.x + radius * ux, y: start.y + radius * uy }
  return { center, radius: Math.min(radius, center.x, center.y, width - 1 - center.x, height - 1 - center.y) }
}
