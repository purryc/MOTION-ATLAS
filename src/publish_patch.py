"""Allowlisted incremental site release over immutable v1.0.0 data assets."""
import json,hashlib,tarfile,shutil
from pathlib import Path
from analyze import B
ROOT=B/'.tmp/public-patch'
def main():
 if ROOT.exists():shutil.rmtree(ROOT)
 ROOT.mkdir(parents=True,exist_ok=True)
 files=[('outputs/natural-dwell-height.json','outputs/natural-dwell-height.json'),('src/viewer/index.html','index.html'),('outputs/report.html','outputs/report.html'),('outputs/ui-position-calibration.json','outputs/ui-position-calibration.json'),('outputs/participants.json','outputs/participants.json')]
 files +=[(str(p.relative_to(B)),str(Path('viewer')/p.name)) for p in (B/'src/viewer').iterdir() if p.is_file()]
 extra=B/'outputs/incremental-data-files.json'
 if extra.exists():
  for dest in json.loads(extra.read_text()):
   if not dest.startswith('outputs/') or '..' in Path(dest).parts:raise ValueError('Unsafe incremental artifact path')
   files.append(('.tmp/public-site/'+dest,dest))
 for src,dest in files:
  target=ROOT/dest;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy(B/src,target)
  live=B/'.tmp/public-site'/dest;live.parent.mkdir(parents=True,exist_ok=True);
  if (B/src).resolve()!=live.resolve():shutil.copy(B/src,live)
 manifest=dict(name='MOTION ATLAS',version='1.1.4',operation_selection='always-visible buttons inside Abstract input card; direct playback selection',base_release='v1.0.0',task_hierarchy='Reading, Writing, Abstract input (Tap, Drag, vertical/horizontal scroll)',home_zone='full-task valid thumb XYZ P10-P90 position reference; independent of dwell slider',ui_calibration='robust TAP DOWN pixel-to-recorded-marker XY, source timestamps and heldout errors',files={dest:hashlib.sha256((ROOT/dest).read_bytes()).hexdigest() for _,dest in files})
 (ROOT/'outputs/revision.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));shutil.copy(ROOT/'outputs/revision.json',B/'.tmp/public-site/outputs/revision.json')
 archive=B/'.tmp/public-patch.tar.gz'
 with tarfile.open(archive,'w:gz') as tar:
  for p in ROOT.rglob('*'):
   if p.is_file():tar.add(p,arcname=str(p.relative_to(ROOT)),recursive=False)
 print(json.dumps(dict(bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest())))
if __name__=='__main__':main()
