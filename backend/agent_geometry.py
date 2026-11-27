"""Single-fiber candidate selection used in the nanocellulose circle rounds."""
import heapq

import cv2 as cv
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

def count_crossings(mask: np.ndarray, x: float, y: float, radius: float) -> int:
    sample_count = max(192, min(1440, round(2 * np.pi * radius * 6)))
    angle = np.linspace(0, 2 * np.pi, sample_count, endpoint=False)
    xs = np.rint(x + radius * np.cos(angle)).astype(int)
    ys = np.rint(y + radius * np.sin(angle)).astype(int)
    inside = mask[ys, xs] > 0
    # Count complete entry/exit pairs across the cyclic boundary.
    return 2 * int(np.count_nonzero(inside & ~np.roll(inside, 1) & np.roll(inside, -1)))


ANGLES = np.linspace(0, 2 * np.pi, 192, endpoint=False)
COS = np.cos(ANGLES)
SIN = np.sin(ANGLES)
COS2 = np.cos(2 * ANGLES)
SIN2 = np.sin(2 * ANGLES)


def rings(mask, x, y, radius):
    xx = np.rint(x[:, None] + radius[:, None] * COS).astype(np.int32)
    yy = np.rint(y[:, None] + radius[:, None] * SIN).astype(np.int32)
    return mask[yy, xx]


def arcs(ring):
    return (ring & ~np.roll(ring, 1, axis=1) & np.roll(ring, -1, axis=1)).sum(axis=1)


def samples(gray, x, y):
    return ndi.map_coordinates(gray, [y, x], order=1, prefilter=False)


def orientation_fields(gray):
    result = []
    for scale, width in ((1.4, 4.2), (2.4, 8.0), (3.8, 13.0)):
        smooth = cv.GaussianBlur(gray.astype(np.float32), (0, 0), scale)
        gx = cv.Sobel(smooth, cv.CV_32F, 1, 0, scale=.125)
        gy = cv.Sobel(smooth, cv.CV_32F, 0, 1, scale=.125)
        fields = [cv.GaussianBlur(v, (0, 0), width) for v in (gx * gx, gy * gy, gx * gy)]
        result.append(fields)
    return result


def proposals(mask, gray, bottom, contrast_floor, orientation, alignment=True, continuity=True):
    inner = cv.distanceTransform(mask.astype(np.uint8), cv.DIST_L2, 5)
    y, x = np.nonzero(skeletonize(mask))
    dist = inner[y, x]
    allowed = (dist <= 17) & (x > 6) & (y > 6) & (x < gray.shape[1] - 7) & (y < bottom - 7)
    x, y, dist = x[allowed], y[allowed], dist[allowed]
    for factor in (1.0, 1.26, .84, .71):
        r = np.round(np.clip((1.74 * dist + 1.0) * factor, 3.1, 33.0), 2)
        interior = (x - r >= 3) & (y - r >= 3) & (x + r < gray.shape[1] - 3) & (y + r < bottom - 3)
        rx, ry, rr = x[interior], y[interior], r[interior]
        for sl in (slice(k, k + 4000) for k in range(0, len(rx), 4000)):
            sx, sy, sr = rx[sl], ry[sl], rr[sl]
            ring = rings(mask, sx, sy, sr)
            occupied = ring.mean(axis=1)
            each_half = np.abs(ring[:, :96].mean(axis=1) - ring[:, 96:].mean(axis=1))
            good = (arcs(ring) == 2) & (occupied >= .115) & (occupied <= .48) & (each_half < .26)
            sx, sy, sr, ring, occupied = sx[good], sy[good], sr[good], ring[good], occupied[good]
            if not len(sx):
                continue
            weights = ring.astype(np.float32)
            a = weights @ COS2
            b = weights @ SIN2
            angle = .5 * np.arctan2(b, a)
            symmetry = (ring & np.roll(ring, 96, axis=1)).sum(axis=1) / ring.sum(axis=1)
            tx, ty = np.cos(angle), np.sin(angle)
            offsets = np.array([-.83, -.68, -.53, -.33, -.15, 0, .15, .33, .53, .68, .83])
            lateral = offsets[None, None, :] * sr[:, None, None]
            along = np.array([-.5, 0, .5])[None, :, None] * sr[:, None, None]
            sx3, sy3, tx3, ty3 = [v[:, None, None] for v in (sx, sy, tx, ty)]
            profile = samples(gray, sx3 + tx3 * along - ty3 * lateral, sy3 + ty3 * along + tx3 * lateral)
            core = profile[:, :, 4:7].mean(axis=2)
            left = profile[:, :, :3].mean(axis=2) - core
            right = profile[:, :, -3:].mean(axis=2) - core
            strength = np.minimum(left, right).min(axis=1)
            good = (strength >= contrast_floor) & (symmetry >= .52)
            alignment_score = np.zeros_like(strength)
            if alignment:
                level = np.digitize(sr, [7, 14])
                for k, (xx, yy, cross) in enumerate(orientation):
                    take = level == k
                    u, v = sx[take], sy[take]
                    jxx, jyy, jxy = xx[v, u], yy[v, u], cross[v, u]
                    alignment_score[take] = (
                        np.cos(2 * angle[take]) * (jyy - jxx) - 2 * np.sin(2 * angle[take]) * jxy
                    ) / (jxx + jyy + .05)
                good &= alignment_score >= .25
            if not np.any(good):
                continue
            ext_score = np.zeros_like(strength)
            if continuity:
                ext_along = np.array([-2.35, -1.75, -1.18, 1.18, 1.75, 2.35])[None, :, None] * np.maximum(sr, 6)[:, None, None]
                ext_x = sx3 + tx3 * ext_along - ty3 * lateral
                ext_y = sy3 + ty3 * ext_along + tx3 * lateral
                ext_profile = samples(gray, ext_x, ext_y)
                ext_core = np.minimum.reduce([ext_profile[:, :, j:j+3].mean(axis=2) for j in (3, 4, 5)])
                ext_flanks = np.minimum(ext_profile[:, :, :3].mean(axis=2), ext_profile[:, :, -3:].mean(axis=2))
                ext_strength = ext_flanks - ext_core
                ext_threshold = np.maximum(contrast_floor * .8, strength[:, None] * .20)
                supporting = (ext_strength >= ext_threshold) & (ext_y[:, :, 5] < bottom - 3)
                good &= (supporting[:, :3].sum(axis=1) >= 2) & (supporting[:, 3:].sum(axis=1) >= 2)
                ext_score = np.minimum(np.median(ext_strength[:, :3], axis=1), np.median(ext_strength[:, 3:], axis=1))
            sx, sy, sr, strength, symmetry, occupied, ext_score, alignment_score = [
                v[good] for v in (sx, sy, sr, strength, symmetry, occupied, ext_score, alignment_score)
            ]
            stable = (arcs(rings(mask, sx, sy, sr * .91)) == 2)
            stable &= arcs(rings(mask, sx, sy, sr * 1.08)) == 2
            scores = strength + 2.0 * ext_score + 26 * alignment_score + 8 * symmetry + 3 * stable - 5 * abs(occupied - .27)
            yield from zip(scores.tolist(), sx.tolist(), sy.tolist(), sr.tolist(), strength.tolist(), stable.tolist())


def single_band(mask, x, y, r):
    extent = int(np.ceil(r))
    dy, dx = np.ogrid[-extent:extent + 1, -extent:extent + 1]
    inside = dx * dx + dy * dy <= (r + .45) ** 2
    patch = mask[y - extent:y + extent + 1, x - extent:x + extent + 1] & inside
    labs, _ = ndi.label(patch, structure=np.ones((3, 3)))
    center_label = labs[extent, extent]
    component = (labs == center_label) if center_label else np.zeros_like(patch)
    return component.sum() >= .92 * patch.sum() and count_crossings(component, extent, extent, r) == 4


def fiber_segments(mask, prune_spurs=True):
    """Label centerlines between junctions after removing short terminal spurs."""
    neighbors = np.ones((3, 3), dtype=np.uint8)
    skeleton = skeletonize(mask)
    degree = ndi.convolve(skeleton.astype(np.uint8), neighbors, mode='constant') - skeleton
    if prune_spurs:
        junctions = skeleton & (degree > 2)
        arms, _ = ndi.label(skeleton & ~junctions, neighbors)
        endpoints = np.unique(arms[skeleton & (degree == 1)])
        at_junction = np.unique(arms[ndi.binary_dilation(junctions, neighbors)])
        short = np.flatnonzero(np.bincount(arms.ravel()) <= 8)
        spurs = np.intersect1d(np.intersect1d(endpoints, at_junction), short)
        skeleton = skeletonize(skeleton & ~np.isin(arms, spurs[spurs > 0]))
        degree = ndi.convolve(skeleton.astype(np.uint8), neighbors, mode='constant') - skeleton
    return ndi.label(skeleton & (degree <= 2), neighbors)[0]


def _circle_selection(mask, spacing, prune_spurs):
    segments = fiber_segments(mask, prune_spurs)
    # A slightly smoother tracking mask bridges notches on thick fibers. The
    # original mask still decides the four crossings and keeps thin fibers.
    smooth_mask = ndi.gaussian_filter(mask.astype(np.float32), 2) > .45
    holes, _ = ndi.label(~smooth_mask)
    small_holes = np.bincount(holes.ravel()) < 32
    small_holes[0] = False
    tracks = fiber_segments(smooth_mask | small_holes[holes], prune_spurs)
    distance, nearest = ndi.distance_transform_edt(tracks == 0, return_indices=True)
    tracks = np.where(smooth_mask & (distance <= 2), tracks[tuple(nearest)], 0)
    used_segments = set()
    used_tracks = set()
    selected = []

    def accept(candidate):
        _, x, y, r, *_ = candidate
        segment, track = segments[y, x], tracks[y, x]
        if not segment or segment in used_segments or track in used_tracks:
            return False
        if any((x - ox) ** 2 + (y - oy) ** 2 < max(spacing, r + ro + 1) ** 2
               for _, ox, oy, ro, *_ in selected):
            return False
        if count_crossings(mask, x, y, r) != 4 or not single_band(mask, x, y, r):
            return False
        selected.append(candidate)
        used_segments.add(segment)
        if track:
            used_tracks.add(track)
        return True

    return selected, accept


def choose(mask, candidates, spacing, limit, prune_spurs=True):
    selected, accept = _circle_selection(mask, spacing, prune_spurs)
    tiles = {}
    for candidate in sorted(candidates, reverse=True):
        _, x, y, *_ = candidate
        tiles.setdefault((x // 142, y // 142), []).append(candidate)
    tiles = list(tiles.values())
    queue = [(-pool[0][0], i, 0, 0) for i, pool in enumerate(tiles)]
    heapq.heapify(queue)
    while queue and len(selected) < limit:
        _, i, index, accepted = heapq.heappop(queue)
        pool = tiles[i]
        candidate = pool[index]
        if accept(candidate):
            accepted += 1
        index += 1
        if index < len(pool):
            heapq.heappush(queue, (-(pool[index][0] / (1 + .009 * accepted)), i, index, accepted))
    return selected


def choose_zoned(mask, candidates, spacing, limit, *, coverage_mask, field_height,
                 rows=2, columns=4, prune_spurs=True, redistribute=True):
    """Apportion by fiber pixels; retain global spacing and track uniqueness across zone borders."""
    width = mask.shape[1]
    zones = []
    for row in range(rows):
        y0, y1 = (int(np.ceil(i * field_height / rows)) for i in (row, row + 1))
        for col in range(columns):
            x0, x1 = (int(np.ceil(i * width / columns)) for i in (col, col + 1))
            fiber = int(np.count_nonzero(coverage_mask[y0:y1, x0:x1]))
            zones.append(dict(zone=len(zones)+1, row=row+1, column=col+1, x0=x0, y0=y0, x1=x1, y1=y1,
                              fiber_pixels=fiber, area_pixels=(x1-x0)*(y1-y0), quota=0, selected=0))
    total = sum(z['fiber_pixels'] for z in zones)
    if not total or not limit:
        return [], zones
    # Largest remainders keep the integer targets summing to the request.
    remainders = []
    for z in zones:
        z['quota'], remainder = divmod(limit * z['fiber_pixels'], total)
        remainders.append(remainder)
    missing = limit - sum(z['quota'] for z in zones)
    for i in sorted(range(len(zones)), key=remainders.__getitem__, reverse=True)[:missing]:
        zones[i]['quota'] += 1

    pools = [[] for _ in zones]
    for c in sorted(candidates, reverse=True):
        _, x, y, *_ = c
        if 0 <= x < width and 0 <= y < field_height:
            index = (y * rows // field_height) * columns + x * columns // width
            if zones[index]['fiber_pixels']:
                pools[index].append(c)
    streams = [iter(pool) for pool in pools]
    selected, accept = _circle_selection(mask, spacing, prune_spurs)
    # First fill each quota. Only then allow spare capacity to absorb a shortfall.
    for overflow in ([False, True] if redistribute else [False]):
        queue = []
        for i, z in enumerate(zones):
            if pools[i] and (overflow or z['quota']):
                heapq.heappush(queue, ((z['selected'] + 1) / z['fiber_pixels'], -pools[i][0][0], i))
        while queue and len(selected) < limit:
            _, _, i = heapq.heappop(queue)
            z = zones[i]
            for candidate in streams[i]:
                if accept(candidate):
                    z['selected'] += 1
                    if overflow or z['selected'] < z['quota']:
                        heapq.heappush(queue, ((z['selected'] + 1) / z['fiber_pixels'], -candidate[0], i))
                    break
    return selected, zones
