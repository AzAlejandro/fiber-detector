import React, { useEffect, useState } from 'react'
import { apiGet } from '../api'

const number = new Intl.NumberFormat('es-CL', { maximumSignificantDigits: 8 })
const unitLabel = unit => unit === 'um' ? 'µm' : 'nm'

export default function ImageScaleCell({ imageId, calibration, loading, onEdit, refreshKey }) {
  const [local, setLocal] = useState(undefined)


  const [error, setError] = useState('')
  // An already open desktop backend can supply the same calibration through its per-image endpoint.
  useEffect(() => {
    if (calibration !== undefined) return
    let active = true
    apiGet('/api/diameter-research/calibration/load?image_id=' + encodeURIComponent(imageId))
      .then(res => { if (active) setLocal(res.calibration) })
      .catch(err => { if (active) setError(err.message) })
    return () => { active = false }
  }, [imageId, calibration, refreshKey])
  const scale = calibration === undefined ? local : calibration
  const known = scale?.unit_per_px > 0
  const hasBar = known && !scale.direct_factor
  return <td className="image-scale-cell">
    <button type="button" className="image-scale-value" title="Doble clic para marcar la escala en la foto"
      disabled={loading || scale === undefined}
      onDoubleClick={() => onEdit(scale)} onKeyDown={e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onEdit(scale) }
      }}>
      {hasBar && <span>{number.format(scale.known_value)} {unitLabel(scale.unit)} = {number.format(scale.pixel_distance)} px</span>}
      {known ? <span>{number.format(scale.unit_per_px)} {unitLabel(scale.unit)}/px</span>
        : loading || scale === undefined ? 'Cargando…' : 'Sin escala'}
    </button>
    {error && <small role="alert">{error}</small>}
  </td>
}
