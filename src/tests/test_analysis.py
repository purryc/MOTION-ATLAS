import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.spatial.transform import Rotation
from analyze import transform,speed_of,contacts,labels,episodes,motive_epoch,canonical_record

class AnalysisTests(unittest.TestCase):
 def test_source_sitting_alias_preserves_canonical_record(self):
  self.assertEqual(canonical_record('P10_N6_sitting.csv'),'P10_N6_seated')
 def test_documented_motive_noon_bug_and_dst(self):
  self.assertEqual(motive_epoch('2018-03-23 12.20.53.709 AM'),motive_epoch('2018-03-23 12.20.53.709 PM'))
  # Berlin 14:00 on March 22 is 13 UTC; on March 27 it is 12 UTC.
  from datetime import datetime,timezone
  for day,utc_hour in [(22,13),(27,12)]:
   expected=datetime(2018,3,day,utc_hour,tzinfo=timezone.utc).timestamp()*1000
   self.assertEqual(motive_epoch(f'2018-03-{day} 02.00.00.000 PM'),expected)
 def test_shared_midpoint_has_one_task(self):
  i=[dict(task='TAP',context_start_ms=0,context_end_ms=5,start_ms=0,end_ms=4,sync_eligible=True),dict(task='DRAG',context_start_ms=5,context_end_ms=10,start_ms=6,end_ms=9,sync_eligible=True)]
  core,context,eligible=labels(np.array([4.,5.,6.]),i);np.testing.assert_equal(context,[2,3,3])
 def test_transform_roundtrip_and_rigid_motion(self):
  rng=np.random.default_rng(5);q=Rotation.random(8,random_state=rng).as_quat();p=rng.normal(size=(8,3))*100
  raw=rng.normal(size=(8,25,3));R=Rotation.from_quat(q).as_matrix();w=np.einsum('nij,nmj->nmi',R,raw)+p[:,None]
  local,valid,_=transform(q,p,w);np.testing.assert_allclose(local[:,:,[0,2,1]],raw,atol=1e-12);self.assertTrue(valid.all())
 def test_speed_does_not_bridge_missing_or_source_gap(self):
  t=np.array([0,4.167,8.334,12.5]);p=np.zeros((4,1,3));p[:,0,0]=[0,1,np.nan,3]
  s=speed_of(t,p,np.array([0,1,2,4]));self.assertTrue(np.isnan(s[0,0]));self.assertGreater(s[1,0],200);self.assertTrue(np.isnan(s[2:,0]).all())
 def test_missing_up_is_unknown_after_last_observation(self):
  t=np.arange(0,40,4.167);e=[dict(timestamp_ms=4,action='POINTER_DOWN',trial='a',sync_eligible=True),dict(timestamp_ms=12,action='MOVE',trial='a',sync_eligible=True)]
  state,_,ups=contacts(t,e,[]);self.assertEqual(len(ups),0);self.assertTrue((state[t>12]==-1).all())
 def test_episode_splits_task_and_frame_gap(self):
  t=np.arange(0,2000,1000/240);f=np.arange(len(t));f[240:]+=2;p=np.ones((len(t),1,3));v=np.zeros((len(t),1));task=np.zeros(len(t),dtype=int)
  e=episodes(t,f,v,p,task,np.zeros(len(t)),np.array([3000]),np.array([-1000]),duration=400)
  self.assertEqual(len(e),2);self.assertLess(e[0]['end_frame'],e[1]['start_frame'])
if __name__=='__main__':unittest.main()
