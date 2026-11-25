// Sample in the same pixel coordinates as the saved agent circles and mask.
export function fiberContacts(circle, mask, gray, width, height) {
  const { x, y, radius_px: radius } = circle
  if (!(radius > 0) || x-radius < 0 || y-radius < 0 || x+radius > width-1 || y+radius > height-1) return []
  const n = Math.max(192, Math.min(1440, Math.round(2*Math.PI*radius*6)))
  const angleStep = 2*Math.PI/n
  function point(i) {
    const a = i*angleStep
    return { x: x+radius*Math.cos(a), y: y+radius*Math.sin(a) }
  }
  const inside = new Uint8Array(n)
  const intensity = new Float32Array(n)
  // NumPy rint in the proposal stage rounds exact half-pixels to even.
  const nearest = v => v%1 === 0.5 ? 2*Math.round(v/2) : Math.round(v)
  for (let i=0; i<n; i++) {
    const p = point(i)
    inside[i] = mask[nearest(p.y)*width+nearest(p.x)] > 0
    const col = Math.floor(p.x), row = Math.floor(p.y)
    const right = Math.min(width-1,col+1), bottom = Math.min(height-1,row+1)
    const dx=p.x-col, dy=p.y-row
    intensity[i] = (1-dy)*((1-dx)*gray[row*width+col]+dx*gray[row*width+right])
      + dy*((1-dx)*gray[bottom*width+col]+dx*gray[bottom*width+right])
  }
  const wrap = i => (i%n+n)%n
  const boundaries = []
  for (let i=0; i<n; i++) {
    if (inside[i] && !inside[wrap(i-1)] && inside[wrap(i+1)]) {
      let end = i+1
      while (inside[wrap(end)]) end++
      boundaries.push({ at:i-.5, sign:-1 }, { at:wrap(end)-.5, sign:1 })
    }
  }
  boundaries.sort((a,b)=>a.at-b.at)
  const wrapIndex = j => (j+boundaries.length)%boundaries.length
  return boundaries.map(({at,sign},i)=>{
    // Keep the search on this side of the midpoint to either neighboring edge.
    const distance = Math.min(wrap(at-boundaries[wrapIndex(i-1)].at),wrap(boundaries[wrapIndex(i+1)].at-at))
    const samplePx = radius*angleStep
    const window = Math.min(1.5/samplePx, distance/2)
    const delta = Math.max(1, Math.round(Math.min(.6/samplePx, distance/2)))
    let best = at, strongest = 0
    for (let j=Math.ceil(at-window); j<=at+window; j++) {
      const contrast = sign*(intensity[wrap(j+delta)]-intensity[wrap(j-delta)])
      if (contrast>strongest || (contrast===strongest && contrast>0 && Math.abs(j-at)<Math.abs(best-at))) {
        best=j; strongest=contrast
      }
    }
    const supported = strongest>=1
    return { ...point(supported ? best : at), supported }
  })
}

export async function readAgentLayer(url, width, height, signal) {
  const response = await fetch(url, {signal, cache:'no-store'})
  if (!response.ok) throw Error('No se pudo leer la capa del agente.')
  const bitmap = await createImageBitmap(await response.blob())
  try {
    if (bitmap.width!==width || bitmap.height!==height) throw Error('La capa y los círculos tienen tamaños distintos.')
    const canvas = document.createElement('canvas')
    canvas.width=width; canvas.height=height
    const ctx=canvas.getContext('2d')
    ctx.drawImage(bitmap,0,0)
    const rgba=ctx.getImageData(0,0,width,height).data
    const gray = new Uint8Array(width*height)
    for (let i=0; i<gray.length; i++) gray[i]=rgba[4*i]
    return gray
  } finally { bitmap.close() }
}

export function edgeReviewFor(run, circle) {
  if (!circle || !run?.edge_review) return null
  const prefix = 'agent_' + run.run_id + '_'
  const key = String(circle.id)
  const review = run.edge_review.circles[key.startsWith(prefix) ? key.slice(prefix.length) : key]
  if (!review || ['x','y','radius_px'].some(k => Math.abs(circle[k] - review.geometry[k]) > 0.000001)) return null
  return review
}

export async function detectCircleContacts(url, run, circles, signal) {
  const result = {}
  const pending = []
  for (const circle of circles) {
    const review = edgeReviewFor(run, circle)
    if (review) result[circle.id] = review.points
    else pending.push(circle)
  }
  if (pending.length) {
    const [mask, gray] = await Promise.all(['mascara', 'suavizada'].map(layer =>
      readAgentLayer(url + '/layers/' + layer, run.width, run.height, signal)))
    for (const c of pending) result[c.id] = fiberContacts(c, mask, gray, run.width, run.height)
  }
  return result
}
