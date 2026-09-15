import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.spatial.transform import Rotation
from phone_pose import fit

class PhonePoseTests(unittest.TestCase):
 def test_observed_subset_recovers_known_pose_and_unfitted_marker(self):
  template=np.array([[0,0,0],[20,0,0],[0,30,0],[10,10,8]],float)
  rotation=Rotation.from_euler('xyz',[25,60,10],degrees=True).as_matrix();origin=np.array([100,200,300])
  observed=template@rotation.T+origin
  recovered,pivot,error,s=fit(template[:3],observed[None,:3])
  np.testing.assert_allclose(recovered[0],rotation,atol=1e-10)
  np.testing.assert_allclose(pivot[0],origin,atol=1e-10)
  np.testing.assert_allclose(recovered[0]@template[3]+pivot[0],observed[3],atol=1e-10)
 def test_mirrored_nonplanar_samples_cannot_be_accepted_as_rotation(self):
  template=np.array([[0,0,0],[20,0,0],[0,30,0],[10,10,20]],float)
  observed=template*np.array([-1,1,1])+[100,200,300]
  rotation,pivot,error,s=fit(template,observed[None])
  self.assertAlmostEqual(np.linalg.det(rotation[0]),1)
  self.assertGreater(error[0],1)
