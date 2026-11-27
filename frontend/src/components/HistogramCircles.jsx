import React, { useEffect, useRef, useState } from 'react'
import { API_BASE, apiGet, b64ToDataUrl } from '../api'

// Store only the circle geometry, including when connected to an older desktop backend.
async function loadRunCircles(runId) {
  const run = await apiGet('/api/diameter-research/results/get?' + new URLSearchParams({ run_id: runId, geometry_only: true }))
  const prior = run.meta?.prior_run_id || ''
  const seeds = run.meta?.params_effective?.circle_square_circles_by_point || []
  const circles = new Map()
  for (const result of run.results || []) {
    const seed = seeds[result.point_index] || {}
    const radius = seed.circle_square_seed_radius_px ?? result.circle_radius_px
    const id = result.interactive_geometry_id || result.circle_square_geometry_id || seed.circle_square_geometry_id
    const x = seed.circle_square_center_x ?? result.original_xy?.[0] ?? result.x
    const y = seed.circle_square_center_y ?? result.original_xy?.[1] ?? result.y
    if (radius > 0 && Number.isFinite(x) && Number.isFinite(y)) {
      circles.set(result.point_index, { x, y, radius, id, left: result.left_edge_xy, right: result.right_edge_xy,
        agentRun: prior.startsWith('agent:') ? prior.slice(6) : /^agent_([a-f0-9]{32})_/.exec(id)?.[1] })
    }
  }
  return circles
}

function CirclePhoto({ rows, project, cache, onOpen }) {
  const imageId = rows[0].image_id
  const svg = useRef(null)
  const drag = useRef(null)
  const [photo, setPhoto] = useState(null)
  const [runs, setRuns] = useState({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [chosen, setChosen] = useState('')
  const [view, setView] = useState({ x: 0, y: 0, zoom: 1 })
  const runIds = JSON.stringify([...new Set(rows.map(row => row.run_id).filter(Boolean))].sort())
  useEffect(() => {
    let live = true
    async function load() {
      let url
      if (project) url = API_BASE + '/api/agent-training/' + encodeURIComponent(project) + '/circulos/photo/' + encodeURIComponent(imageId)
      else {
        const res = await apiGet('/api/assist-models/dataset/preview?image_id=' + encodeURIComponent(imageId))
        url = b64ToDataUrl(res.image_b64, res.image_mime)
      }
      const img = new Image()
      img.src = url
      await img.decode()
      if (live) setPhoto({ url, width: img.naturalWidth, height: img.naturalHeight })
    }
    load().catch(() => { if (live) setError('No se pudo cargar la foto original.') })
    return () => { live = false }
  }, [imageId, project])
  useEffect(() => {
    let live = true
    Promise.all(JSON.parse(runIds).map(async id => {
      if (!cache.has(id)) cache.set(id, loadRunCircles(id).catch(err => { cache.delete(id); throw err }))
      return [id, await cache.get(id)]
    })).then(entries => { if (live) setRuns(Object.fromEntries(entries)) })
      .catch(err => { if (live) setError(err.message) })
    return () => { live = false }
  }, [runIds, cache])
  function point(e) {
    return new DOMPoint(e.clientX, e.clientY).matrixTransform(svg.current.getScreenCTM().inverse())
  }
  useEffect(() => {
    const el = svg.current
    if (!el) return
    function wheel(e) {
      if (!e.ctrlKey) return
      e.preventDefault()
      const p = point(e)
      setView(old => {
        const zoom = Math.max(0.5, Math.min(64, old.zoom * (e.deltaY < 0 ? 1.2 : 1 / 1.2)))
        const ratio = zoom / old.zoom
        return { zoom, x: p.x - (p.x - old.x) * ratio, y: p.y - (p.y - old.y) * ratio }
      })
    }
    el.addEventListener('wheel', wheel, { passive: false })
    return () => el.removeEventListener('wheel', wheel)
  }, [photo])
  const circles = rows.flatMap(row => {
    const circle = runs[row.run_id]?.get(row.point_index)
    return circle ? [{ ...circle, row }] : []
  })
  const selected = circles.find(c => c.row.measurement_id === chosen)
  return <>
    {error && <p role="alert">{error}</p>}
    {photo ? <svg ref={svg} className="histogram-circle-photo" aria-label="Foto con los círculos del intervalo"
      viewBox={`0 0 ${photo.width} ${photo.height}`}
      onPointerDown={e => {
        if (e.button !== 0 || !e.isPrimary) return
        drag.current = { point: point(e), view, clientX: e.clientX, clientY: e.clientY, id: e.target.dataset.measurement }
        e.currentTarget.setPointerCapture(e.pointerId)
      }} onPointerMove={e => {
        const d = drag.current
        if (!d || !e.isPrimary) return
        if (!d.moved && Math.hypot(e.clientX - d.clientX, e.clientY - d.clientY) < 3) return
        d.moved = true
        const p = point(e)
        setView({ ...d.view, x: d.view.x + p.x - d.point.x, y: d.view.y + p.y - d.point.y })
      }} onPointerUp={e => {
        if (!e.isPrimary) return
        if (drag.current?.id && !drag.current.moved) setChosen(drag.current.id)
        drag.current = null
      }} onLostPointerCapture={() => { drag.current = null }}>
      <g transform={`translate(${view.x} ${view.y}) scale(${view.zoom})`}>
        <image href={photo.url} width={photo.width} height={photo.height} />
        {circles.map(c => c.left && c.right && <line key={c.row.measurement_id}
          x1={c.left[0]} y1={c.left[1]} x2={c.right[0]} y2={c.right[1]}
          stroke="#ff6347" strokeWidth={2} vectorEffect="non-scaling-stroke" pointerEvents="none" />)}
        {circles.map(c => <circle key={c.row.measurement_id} data-measurement={c.row.measurement_id}
          cx={c.x} cy={c.y} r={c.radius} fill="transparent" stroke={c === selected ? '#ffcf39' : '#00e4f2'}
          strokeWidth={c === selected ? 3 : 2} vectorEffect="non-scaling-stroke" role="button" tabIndex={0}
          aria-label={`Círculo ${c.row.point_index + 1}, ${c.row.diameter_value.toPrecision(4)} ${c.row.diameter_unit}`}
          onClick={e => { if (e.detail === 0) setChosen(c.row.measurement_id) }}
          onKeyDown={e => { if (['Enter',' '].includes(e.key)) { e.preventDefault(); setChosen(c.row.measurement_id) } }} />)}
      </g>
    </svg> : !error && <p>Cargando foto…</p>}
    <div className="inline">
      <small>{Object.keys(runs).length ? `${circles.length} círculos de ${rows.length} mediciones` : 'Cargando círculos…'} · Arrastra para desplazar · Ctrl + rueda para zoom</small>
      {selected && <button disabled={busy} onClick={async () => {
        setBusy(true)
        try { await onOpen(selected) } catch (err) { setError(err.message) } finally { setBusy(false) }
      }}>{busy ? 'Abriendo…' : 'Ir a Diámetro'}</button>}
    </div>
  </>
}

export default function HistogramCircles({ rows, onOpen }) {
  const cache = useRef(new Map())
  const [preferred, setPreferred] = useState('')
  const images = new Map(rows.map(row => [row.image_id, row.image_name || row.image_id]))
  const id = images.has(preferred) ? preferred : rows[0].image_id
  const visible = rows.filter(row => row.image_id === id)
  return <section className="histogram-circle-panel">
    <h3>Círculos del intervalo</h3>
    {images.size > 1 ? <select aria-label="Imagen del intervalo" value={id} onChange={e => setPreferred(e.target.value)}>
      {Array.from(images, ([key, name]) => <option key={key} value={key}>{name}</option>)}
    </select> : <strong>{images.get(id)}</strong>}
    <CirclePhoto key={id} rows={visible} project={visible[0].project_ids?.[0]} cache={cache.current} onOpen={onOpen} />
  </section>
}
