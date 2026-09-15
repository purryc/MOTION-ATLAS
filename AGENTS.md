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
The user revised Home Zone on 2026-09-15: playback shows position only, independent of dwell thresholds. Use each operation’s full-task valid thumb XYZ P10-P90 as a green position-reference frame; explicitly label it a spatial reference, not a proven resting/home state. Never imply it is derived from the current dwell slider. No fill or playback heat maps. Preserve real positions/extents and allow focus. Dwell analysis remains separate below the viewer and in the report. Heat maps belong exclusively in the report.

## Original task hierarchy
The primary task entry has Reading, Writing and Abstract input, with original requirements. Tap/Drag/Vertical scroll/Horizontal scroll buttons and the selected operation requirement live inside the Abstract input card. Keep these controls visible when another task is selected, allowing direct operation selection without activating the parent first. Do not nest buttons. Retain all six underlying operation labels/data and reading-scroll context. Do not imply six independent original experiments.

## UI position calibration and coverage
Keep raw tile/target and touch coordinates distinct; unknown anchor convention/size must not be presented as a known control centre. Fit UI pixel-to-recorded-marker XY mapping from valid timestamp-matched TAP DOWN samples in the same recording, with robust diagonal affine mapping, held-out error and spatial coverage. Transform UI anchors/touch schematic only. Never shift markers or their height reference coordinates to force alignment. Never move real marker samples or relabel estimated nail-reference alignment as measured fingertip position. If recording calibration fails, a phone-level pooled mapping may be used only after participant-heldout validation; explicitly label it an estimate with unverified recording-specific accuracy. Keep original screen-pixel mapping available. Show all participant IDs, disable IDs without published motion capture, and state actual phone-log vs mocap coverage without inventing exclusion reasons. Phone labels include diagonal plus official body/screen dimensions with units.

## Verification
Validate ZIP CRC and record SHA256, timestamp coverage, transform round trips and distance invariance. Validate the pilot before the full batch. Statistical figures and viewer use the same processed arrays. Browser checks and visual acceptance must be recorded separately.

## Interactive dwell and heat maps
Use maximal continuous qualifying episodes at fixed speed <20mm/s and >300ms touch exclusion, then filter minimum duration at 100/200/300/400/500/600ms. Do not truncate longer episodes to the threshold. Display task-wide totals and distinguish current clip/current episode. Timelines support pointer dragging and original-frame seeking. Volumetric heat maps use actual valid samples in documented voxel bins with count conservation; absence of stable samples never becomes inferred dwell. Report height switches affect absolute thumb height tables/charts and preserve original findings/relative-event metrics.

## Natural dwell height summary
Add the height summary reproducibly from explorer_dwell_episodes.csv and calibration.json. Each episode contributes its recorded thumb median Z; corrected episode reference is max(0, median Z minus its record contact baseline). First take each participant's median across qualifying episodes, then report the across-participant median and P25-P75, with participant/record/episode coverage and threshold sensitivity. Do not describe episode counts as independent participants, P25-P75 as a confidence interval, marker-reference height as pad clearance, or natural dwell as intentional Hover. Keep the summary independent of Home Zone and synchronized with the report height switch and dwell slider. Preserve existing report content with idempotent section updates.

## Task UI context
Overlay controls using logged trial positions, touch coordinates and known device pixel dimensions, linked to phone/world transforms. Preserve the raw event/source provenance. Provide a readable enlarged UI inset when the physical phone view is small. Mark UI as a schematic reconstruction, not a video or verified pixel-perfect layout. Do not invent reading text, keyboard layout, target sizes, or physical synchronization evidence. User-visible evidence labels distinguish logged positions and schematic regions.

## Publication
- src/publish.py builds an explicit allowlist into .tmp/public-site; .tmp/public-repo is the isolated release checkout. Never add parent study documents, raw archives/arrays, caches or qa screenshots to Git.
- Publish compact explorer JSON, gzip lossless original-frame binary clips, metadata, report figures, Three.js dependencies and code/provenance. Static playback includes all representative clips and every qualifying 100ms maximal dwell episode with bounded pre/post context; local server retains full-task arbitrary segment access.
- Version changed viewer entry script and styles in HTML URLs so an existing browser session cannot combine new markup with cached old controls.
- Site paths must work below /MOTION-ATLAS/. Static mode must never call Python API endpoints. Check every task/threshold home-null correspondence, full dwell durations and source frames.
- deploy/ holds release workflow; public-site.tar.gz is a versioned GitHub release asset. The project workflow downloads, verifies SHA256, and deploys to GitHub Pages. Record public URL and actual deployment/browser results in qa/.

## Incremental release
Small updates may publish a verified public-patch.tar.gz Release asset over the immutable verified v1.0.0 base site. src/publish_patch.py defines its allowlist; Pages workflow verifies both SHA256 values before overlay extraction. Record base tag, patch tag, source commit and live checks.
