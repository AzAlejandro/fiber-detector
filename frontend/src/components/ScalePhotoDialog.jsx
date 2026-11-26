import React, { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { apiPost } from '../api'
import { convertScaleLength } from './CalibrationPanel'

const format = new Intl.NumberFormat('es-CL', { maximumSignificantDigits: 8 })

function savedLine(cal, horizontal) {
  if (!cal || cal.direct_factor || ![cal.line_x1, cal.line_y1, cal.line_x2, cal.line_y2].every(Number.isFinite)) return null
  return [{ x: cal.line_x1, y: cal.line_y1 }, { x: cal.line_x2, y: horizontal ? cal.line_y1 : cal.line_y2 }]
}

function horizontalLine(start, end) {
  return [start, { x: end.x, y: start.y }]
}

export default function ScalePhotoDialog({ photo, onClose, onSaved }) {
  const dialog = useRef(null)
  const stage = useRef(null)
  const target = useRef(null)
  const [viewport, setViewport] = useState({ width: 1, height: 1 })
  const [size, setSize] = useState(null)
  const [zoom, setZoom] = useState(1)
  const [failed, setFailed] = useState(false)
  const [editing, setEditing] = useState(photo.reviewScale === 'editar')
  const cal = photo.calibration
  const [value, setValue] = useState(() => cal?.direct_factor ? '' : String(cal?.known_value ?? ''))
  const [unitCode, setUnitCode] = useState(cal?.unit || 'nm')
  const [draftLine, setDraftLine] = useState(null)
  const [drawing, setDrawing] = useState(editing && !savedLine(cal))
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const gesture = useRef(null)

  useEffect(() => {
    const el = dialog.current
    el.showModal()
    const observer = new ResizeObserver(() => setViewport({ width: stage.current.clientWidth, height: stage.current.clientHeight }))
    observer.observe(stage.current)
    return () => { observer.disconnect(); el.close() }
  }, [])

  const factor = size ? Math.min(viewport.width / size.width, viewport.height / size.height) : 1
  const width = size ? size.width * factor * zoom : 0
  const height = size ? size.height * factor * zoom : 0
  const hasScale = cal?.unit_per_px > 0
  const unit = cal?.unit === 'um' ? 'µm' : 'nm'
  const line = (!drawing && preview) || draftLine || savedLine(cal, editing)
  const displayLine = preview || line
  const pixels = line ? Math.abs(line[1].x - line[0].x) : 0
  const knownValue = Number(value.trim().replace(',', '.'))
  const conversion = knownValue / pixels
  const canSave = size && !failed && !busy && !drawing && !preview && pixels > 0 && conversion > 0 && Number.isFinite(conversion)

  function imagePoint(e) {
    const point = new DOMPoint(e.clientX, e.clientY).matrixTransform(e.currentTarget.getScreenCTM().inverse())
    return { x: Math.max(0, Math.min(size.width - 1, point.x)), y: Math.max(0, Math.min(size.height - 1, point.y)) }
  }
  function startLine(e) {
    if (!editing || busy || !e.isPrimary || e.button !== 0) return
    const point = imagePoint(e)
    if (!drawing) {
      const handle = e.target.dataset.handle
      if (!handle || !line) return
      gesture.current = { handle, line, point, pointerId: e.pointerId }
      e.currentTarget.setPointerCapture(e.pointerId)
      e.preventDefault()
      return
    }
    const start = preview?.[0] || point
    gesture.current = { start, finishing: !!preview, x: e.clientX }
    e.currentTarget.setPointerCapture(e.pointerId)
    setPreview(horizontalLine(start, point))
  }
  function adjustedLine(drag, point) {
    let dx = point.x - drag.point.x, dy = drag.handle === 'line' ? point.y - drag.point.y : 0
    const moved = drag.line.filter((_, i) => drag.handle === 'line' || drag.handle === String(i))
    dx = Math.max(-Math.min(...moved.map(p => p.x)), Math.min(size.width - 1 - Math.max(...moved.map(p => p.x)), dx))
    dy = Math.max(-Math.min(...moved.map(p => p.y)), Math.min(size.height - 1 - Math.max(...moved.map(p => p.y)), dy))
    return drag.line.map(p => moved.includes(p) ? { x: p.x + dx, y: p.y + dy } : p)
  }
  function moveLine(e) {
    if (!e.isPrimary) return
    const drag = gesture.current
    if (drag?.handle && drag.pointerId === e.pointerId) setPreview(adjustedLine(drag, imagePoint(e)))
    else if (drawing && preview) setPreview(horizontalLine(preview[0], imagePoint(e)))
  }
  function endLine(e) {
    const drag = gesture.current
    if (!drag || !e.isPrimary) return
    gesture.current = null
    if (drag.handle) {
      const next = adjustedLine(drag, imagePoint(e))
      if (Math.abs(next[1].x - next[0].x) >= 1) setDraftLine(next)
      setPreview(null)
      return
    }
    if (!drag.finishing && Math.abs(e.clientX - drag.x) < 3) return
    const end = imagePoint(e)
    if (Math.abs(end.x - drag.start.x) < 1) return
    setDraftLine(horizontalLine(drag.start, end))
    setPreview(null)
    setDrawing(false)
  }
  async function save(e) {
    e.preventDefault()
    if (!canSave) return
    const [a, b] = line
    const payload = { image_id: photo.image_id, enabled: true, unit: unitCode, known_value: knownValue,
      pixel_distance: pixels, unit_per_px: conversion, line_x1: a.x, line_y1: a.y, line_x2: b.x, line_y2: b.y }
    setBusy(true)
    setError('')
    try {
      const response = await apiPost('/api/diameter-research/calibration/save', payload)
      onSaved(photo.image_id, response.calibration || payload, response.measurements?.updated_count)
      onClose()
    } catch (err) { setError(err.message); setBusy(false) }
  }

  function changeZoom(next, point) {
    const el = stage.current
    target.current = point || {
      x: (el.scrollLeft + el.clientWidth / 2 - Math.max(0, (el.clientWidth - width) / 2)) / width,
      y: (el.scrollTop + el.clientHeight / 2 - Math.max(0, (el.clientHeight - height) / 2)) / height,
    }
    const nextZoom = Math.max(1, Math.min(32, next))
    if (nextZoom === zoom) centerView()
    else setZoom(nextZoom)
  }
  function centerView() {
    const point = target.current
    const el = stage.current
    if (!point || !el) return
    el.scrollTo(Math.max(0, point.x * width - el.clientWidth / 2), Math.max(0, point.y * height - el.clientHeight / 2))
    target.current = null
  }
  useLayoutEffect(centerView, [width, height])

  return <dialog className="scale-photo-dialog" ref={dialog} aria-labelledby="scale-photo-title"
    onCancel={e => { e.preventDefault(); if (!busy) onClose() }} onClick={e => { if (!busy && e.target === dialog.current) onClose() }}>
    <div className="point-review-head">
      <div><h2 id="scale-photo-title">{photo.image_name}</h2>
        {!editing && <p>{photo.scaleError || (hasScale ? [
          line && (format.format(cal.known_value) + ' ' + unit + ' = ' + format.format(cal.pixel_distance) + ' px'),
          format.format(cal.unit_per_px) + ' ' + unit + '/px',
        ].filter(Boolean).join(' · ') : cal === undefined ? 'Cargando escala…' : 'Sin escala guardada')}</p>}
      </div>
      <button type="button" className="icon-tool" disabled={busy} onClick={onClose} autoFocus>Cerrar</button>
    </div>
    <div className="viewer-toolbar">
      <button type="button" className="icon-tool" aria-label="Reducir zoom" disabled={!size || zoom <= 1} onClick={() => changeZoom(zoom / 1.5)}>−</button>
      <button type="button" className="icon-tool" aria-label="Ampliar foto" disabled={!size || zoom >= 32} onClick={() => changeZoom(zoom * 1.5)}>+</button>
      <button type="button" className="icon-tool" disabled={!size} onClick={() => changeZoom(1)}>Ajustar vista</button>
      {!editing && <button type="button" className="icon-tool" disabled={!size || cal === undefined} onClick={() => {
        setValue(cal?.direct_factor ? '' : String(cal?.known_value ?? ''))
        setUnitCode(cal?.unit || 'nm')
        setDrawing(!line)
        setEditing(true)
      }}>Editar escala</button>}
      {pixels > 0 && <button type="button" className="icon-tool" disabled={!size} onClick={() => changeZoom(
        Math.min(viewport.width, viewport.height) * .7 / (pixels * factor),
        { x: (line[0].x + line[1].x) / (2 * size.width), y: (line[0].y + line[1].y) / (2 * size.height) }
      )}>Ver barra de escala</button>}
      {editing && <button type="button" className="icon-tool" disabled={!size || busy || (!line && drawing)} onClick={() => {
        setDrawing(!drawing); setPreview(null); gesture.current = null
      }}>{drawing && line ? 'Cancelar trazado' : 'Marcar línea'}</button>}
    </div>
    <div className="scale-photo-stage" ref={stage}>
      {failed || photo.error ? <p role="alert">{photo.error || 'No se pudo abrir la foto.'}</p>
        : photo.loading ? <p>Cargando foto…</p>
        : <div className="scale-photo-canvas">
          <div className="scale-photo-frame" style={{ width, height }}><img src={photo.url} alt={photo.image_name} draggable="false"
            style={{ width, height }} onLoad={e => setSize({ width: e.target.naturalWidth, height: e.target.naturalHeight })}
            onError={() => setFailed(true)} />
          {size && <svg className={'scale-photo-overlay' + (drawing ? ' drawing' : '')} viewBox={`-0.5 -0.5 ${size.width} ${size.height}`}
            aria-label="Línea de calibración" onPointerDown={startLine} onPointerUp={endLine}
            onPointerMove={moveLine}
            onLostPointerCapture={() => { if (gesture.current?.handle) { gesture.current = null; setPreview(null) } }}
            onPointerCancel={() => { gesture.current = null; setPreview(null) }}>
            {displayLine && <g stroke="#ffce42" fill="#ffce42" pointerEvents="none">
              <line x1={displayLine[0].x} y1={displayLine[0].y} x2={displayLine[1].x} y2={displayLine[1].y}
                vectorEffect="non-scaling-stroke" strokeWidth="2" />
              {displayLine.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r={3 / (factor * zoom)}
                stroke="#322500" vectorEffect="non-scaling-stroke" />)}
              {editing && !drawing && !busy && <g className="scale-photo-handles">
                <line data-handle="line" x1={line[0].x} y1={line[0].y} x2={line[1].x} y2={line[1].y}
                  stroke="transparent" strokeWidth="14" vectorEffect="non-scaling-stroke" pointerEvents="stroke" />
                {line.map((p, i) => <circle key={i} data-handle={i} cx={p.x} cy={p.y} r={9 / (factor * zoom)}
                  fill="transparent" stroke="none" pointerEvents="all" />)}
              </g>}
            </g>}
          </svg>}</div>
        </div>}
    </div>
    {editing && <form className="scale-photo-form" onSubmit={save}>
      <p>{drawing ? (preview ? 'Marca el segundo extremo.' : 'Marca dos graduaciones consecutivas o los extremos de una barra simple.')
        : 'Arrastra los extremos para ajustar la línea o el tramo amarillo para moverla.'}</p>
      <p>Ingresa el valor de un tramo según la calibración del proyecto. Por ejemplo, si cada tramo vale 1 µm, marca dos divisiones consecutivas e ingresa 1 µm.</p>
      <label>Longitud conocida <input aria-label="Valor de escala" inputMode="decimal" value={value} disabled={busy}
        onChange={e => setValue(e.target.value)} /></label>
      <label>Unidad <select aria-label="Unidad de escala" value={unitCode} disabled={busy} onChange={e => {
        setValue(String(convertScaleLength(value, unitCode, e.target.value)))
        setUnitCode(e.target.value)
      }}>
        <option value="nm">nm</option><option value="um">µm</option>
      </select></label>
      {pixels > 0 && !drawing && <output>{format.format(pixels)} px
        {Number.isFinite(conversion) && conversion > 0 && ` · ${format.format(conversion)} ${unitCode === 'um' ? 'µm' : 'nm'}/px`}</output>}
      <button type="submit" disabled={!canSave}>Guardar escala</button>
      {error && <p role="alert">{error}</p>}
    </form>}
  </dialog>
}
