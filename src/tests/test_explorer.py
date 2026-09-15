import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from interactive_analysis import voxelize,threshold_stats
class ExplorerTest(unittest.TestCase):
 def test_voxel_conservation_with_signed_and_zero_clamped_heights(self):
  p=np.array([[1.,1.,-3.],[1.,1.,-1.],[1.,1.,1.],[1.,1.,3.]])
  raw=voxelize(p,2);corrected=p.copy();corrected[:,2]=np.maximum(0,corrected[:,2]-2);h=voxelize(corrected,2)
  self.assertEqual(sum(v[3] for v in raw['voxels']),4);self.assertEqual(sum(v[3] for v in h['voxels']),4)
  self.assertEqual(len(h['voxels']),1);self.assertAlmostEqual(h['total_s'],4/240);self.assertEqual(p[0,2],-3)
 def test_empty_dwell_is_absent_not_zero_duration_episode(self):
  self.assertEqual(voxelize(np.empty((0,3)),.5)['voxels'],[])
  self.assertEqual(threshold_stats([]),dict(episodes=0,total_ms=0,median_ms=None,max_ms=None))
