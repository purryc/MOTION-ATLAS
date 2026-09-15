# Le 2019 posture analysis

## Purpose
Reanalyse the original right-handed smartphone motion capture by six tasks. Preserve the parent research Markdown and PDF. The user explicitly authorized publishing MOTION ATLAS to a public GitHub repository and GitHub Pages on 2026-09-15. Publish only this project’s code, public-source derived playback and report assets; preserve private parent study documents locally.

## Structure
- sources/: immutable downloads, upstream code and provenance.
- src/: reproducible Python analysis and local Three.js viewer.
- data/: derived arrays, coverage, summaries, episode and event tables.
- outputs/: report, figures and viewer clips.
- qa/: checks, visual review and limitations.
- .tmp/: rebuildable temporary files only.
- Version revised plans and deliverables. Never replace raw data.

## Evidence
Use actual marker samples, with per-marker validity. Never interpolate across missing samples. Keep world and phone coordinates and source frame IDs. Anatomical joint angles, pad clearance, grip adjustments and Hover intent must not be asserted from marker geometry alone. Keep reading-scroll context. Verify six-task segmentation and S3 synchronization before event inference. Frames are not independent participants.

## Height calibration
Keep recorded marker geometry unchanged. Calibrated thumb reference points are display overlays, clearly labelled, with record-level touch baseline or a user-selected observed contact frame. Per user request, displayed screen distance has a 0mm lower bound; retain signed differences in data for audit, and identify below-baseline values displayed as zero. Do not calibrate missing/unknown-contact frames. Calibration metadata must also work for on-demand clips and exported screenshots.

## Three-dimensional task zones
Playback Home Zone is a green wireframe of measured stable XYZ P10-P90 bounds, without fill or heat maps. All 3D spatial heat maps belong exclusively in the analysis report. No stable episodes means no Home Zone frame; never substitute an activity box. Never infer a stable Home Zone for a task with no episodes. Preserve measured small extents; provide region focus instead of inflating volumes for visibility. Focus may thin display marker/line glyphs to prevent occlusion; never alter positions or zone bounds. More clips inherit recording/task zone metadata. Calibrated reference volumes use the same height display transform as the reference point; measured marker coordinates remain unchanged.

## Verification
Validate ZIP CRC and record SHA256, timestamp coverage, transform round trips and distance invariance. Validate the pilot before the full batch. Statistical figures and viewer use the same processed arrays. Browser checks and visual acceptance must be recorded separately.

## Interactive dwell and heat maps
Use maximal continuous qualifying episodes at fixed speed <20mm/s and >300ms touch exclusion, then filter minimum duration at 100/200/300/400/500/600ms. Do not truncate longer episodes to the threshold. Display task-wide totals and distinguish current clip/current episode. Timelines support pointer dragging and original-frame seeking. Volumetric heat maps use actual valid samples in documented voxel bins with count conservation; absence of stable samples never becomes inferred dwell. Report height switches affect absolute thumb height tables/charts and preserve original findings/relative-event metrics.

## Task UI context
Overlay controls using logged trial positions, touch coordinates and known device pixel dimensions, linked to phone/world transforms. Preserve the raw event/source provenance. Provide a readable enlarged UI inset when the physical phone view is small. Mark UI as a schematic reconstruction, not a video or verified pixel-perfect layout. Do not invent reading text, keyboard layout, target sizes, or physical synchronization evidence. User-visible evidence labels distinguish logged positions and schematic regions.

## Publication
- src/publish.py builds an explicit allowlist into .tmp/public-site; .tmp/public-repo is the isolated release checkout. Never add parent study documents, raw archives/arrays, caches or qa screenshots to Git.
- Publish compact explorer JSON, gzip lossless original-frame binary clips, metadata, report figures, Three.js dependencies and code/provenance. Static playback includes all representative clips and every qualifying 100ms maximal dwell episode with bounded pre/post context; local server retains full-task arbitrary segment access.
- Site paths must work below /MOTION-ATLAS/. Static mode must never call Python API endpoints. Check every task/threshold home-null correspondence, full dwell durations and source frames.
- deploy/ holds release workflow; public-site.tar.gz is a versioned GitHub release asset. The project workflow downloads, verifies SHA256, and deploys to GitHub Pages. Record public URL and actual deployment/browser results in qa/.
