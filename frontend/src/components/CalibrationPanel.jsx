import React from 'react'

const UNITS = [
  { value: 'nm', label: 'nm' },
  { value: 'um', label: 'µm' },
]

export function convertScaleLength(value, fromUnit, toUnit) {
  if (fromUnit === toUnit || String(value).trim() === '') return value
  const number = Number(String(value).replace(',', '.'))
  return Number.isFinite(number) ? Number((fromUnit === 'nm' ? number / 1000 : number * 1000).toPrecision(15)) : value
}

export default function CalibrationPanel({
  calibration,
  onChange,
  onSave,
  onStartDraw,
  drawing,
  loading,
  imageId,
}) {
  if (!calibration) return null

  const handleChange = (field, value) => {
    onChange({ ...calibration, enabled: true, [field]: value })
  }

  const hasLineCoords = ['line_x1', 'line_y1', 'line_x2', 'line_y2'].every((key) => Number.isFinite(Number(calibration[key])))
  const lineDistance = hasLineCoords
    ? Math.hypot(Number(calibration.line_x2) - Number(calibration.line_x1), Number(calibration.line_y2) - Number(calibration.line_y1))
    : 0
  const hasLine = lineDistance > 0
  const pixelDistance = Number(calibration.pixel_distance || 0)
  const factor = pixelDistance > 0 && Number(calibration.known_value || 0) > 0
    ? Number(calibration.unit_per_px || (calibration.known_value / pixelDistance)).toFixed(4)
    : '0.0000'

  return (
    <div className="calibration-panel">
      <h3 className="calibration-title">
        Calibracion de Escala
      </h3>

      <div className="calibration-fields">
        <label className="field">
          <span>Unidad</span>
          <div className="calibration-unit-group">
            {UNITS.map((u) => (
              <button
                key={u.value}
                type="button"
                className={`btn-small ${calibration.unit === u.value ? 'active' : ''}`}
                onClick={() => onChange({ ...calibration, unit: u.value,
                  known_value: convertScaleLength(calibration.known_value, calibration.unit, u.value) })}
                disabled={loading}
              >
                {u.label}
              </button>
            ))}
          </div>
        </label>

        <label className="field">
          <span>Valor conocido ({calibration.unit})</span>
          <input
            type="number"
            min="0.001"
            step="any"
            value={calibration.known_value}
            onChange={(e) => handleChange('known_value', e.target.value)}
            disabled={loading}
          />
        </label>

        <div className="calibration-readout">
          <strong>Distancia en pixeles:</strong> {pixelDistance > 0 ? pixelDistance.toFixed(2) : 'sin linea'}
        </div>

        <div className="calibration-actions">
          <button type="button" onClick={onStartDraw} disabled={loading || !imageId} className={`btn-small ${drawing ? 'active' : ''}`}>
            {drawing ? 'Dibujando...' : 'Dibujar linea'}
          </button>
        </div>
      </div>

      <div className="calibration-result">
        <strong>Factor:</strong> {factor} {calibration.unit}/px
      </div>

      <p className="small calibration-help">
        Marca la barra completa, desde la primera hasta la última graduación o de extremo a extremo si es continua. Ingresa la longitud total impresa.
      </p>

      <div className="calibration-actions">
        <button onClick={onSave} disabled={loading || !imageId || (!hasLine && !calibration.direct_factor)} className="btn-small">
          Guardar
        </button>
      </div>
    </div>
  )
}
