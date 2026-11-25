export async function buildGreenMaskLayer(maskUrl) {
  if (!maskUrl) return ''
  const img = new Image()
  img.crossOrigin = 'anonymous'
  await new Promise((resolve, reject) => {
    img.onload = resolve
    img.onerror = () => reject(new Error('No se pudo renderizar la mascara.'))
    img.src = maskUrl
  })
  const w = Math.max(1, img.naturalWidth || img.width || 1)
  const h = Math.max(1, img.naturalHeight || img.height || 1)
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) throw new Error('No se pudo dibujar la capa de máscara.')
  ctx.drawImage(img, 0, 0, w, h)
  const image = ctx.getImageData(0, 0, w, h)
  const data = image.data
  for (let i = 0; i < data.length; i += 4) {
    const lum = Math.max(data[i], data[i + 1], data[i + 2])
    data[i] = 25
    data[i + 1] = 214
    data[i + 2] = 107
    data[i + 3] = lum > 8 ? lum : 0
  }
  ctx.putImageData(image, 0, 0)
  return canvas.toDataURL('image/png')
}
