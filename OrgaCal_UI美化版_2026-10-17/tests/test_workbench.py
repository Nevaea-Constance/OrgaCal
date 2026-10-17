import json
import math
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image

from batch import analyze_batch,review_batch,reference_records
from constraints import conditional_interval,convert_rpm,settling_velocity,sensitivity,oxygen_minimum
from consistency import relative_mad,pca_fit,summarize
from morphology import measure_contour
from literature import extract_evidence
from reports import csv_bytes,clean_json


def scenario():
    return dict(orbit_mm=25,vessel_mm=35,volume_ml=3,mu_low=.7,mu_high=1,temperature_c=37,
                shear_limit_mpa=45,diameter_um=500,delta_rho=40,rho=1000,oxygen_q=.02,
                bulk_oxygen=.2,critical_oxygen=.02,diffusivity=3e-9,tissue_diffusivity=2e-9,
                beta_suspend=.05,beta_transfer=.01,max_rpm=300,basis='hypothetical example')


class ConstraintTests(unittest.TestCase):
    def test_missing_and_feasible(self):
        self.assertEqual(conditional_interval({})['status'],'missing')
        result=conditional_interval(scenario())
        self.assertEqual(result['status'],'feasible')
        self.assertGreaterEqual(result['lower'],result['suspension_lower'])
        self.assertGreaterEqual(result['lower'],result['oxygen_lower'])
        self.assertLessEqual(result['upper'],result['shear_upper'])
        self.assertGreater(result['lower'],0)
        self.assertEqual(len(sensitivity(scenario())),9)

    def test_no_overlap_and_internal_diffusion(self):
        p=scenario();p['shear_limit_mpa']=.01
        self.assertEqual(conditional_interval(p)['status'],'empty')
        p=scenario();p['oxygen_q']=.1
        result=conditional_interval(p)
        self.assertEqual(result['status'],'empty')
        self.assertIn('内部扩散',result['message'])

    def test_drag_small_re_approaches_stokes(self):
        w,re=settling_velocity(1e-6,10,1000,.001)
        exact=10*9.80665*1e-12/(18*.001)
        self.assertLess(re,.001)
        self.assertAlmostEqual(w/exact,1,places=3)
        self.assertEqual(settling_velocity(.001,0,1000,.001),(0,0))

    def test_conversion_roundtrip(self):
        for mode in ['等轨道线速度','等轨道加速度','等模型剪切（液深尺度）']:
            target=convert_rpm(mode,80,25,19,35,3,.7,22,2,1)
            source=convert_rpm(mode,target,19,25,22,2,1,35,3,.7)
            self.assertAlmostEqual(source,80)
        self.assertAlmostEqual(convert_rpm('等轨道线速度',80,25,19),80*25/19)

    def test_oxygen_inverse_boundary(self):
        d,q,bulk,critical,diff,tissue,rho,mu,beta,orbit=.0005,.03,.2,.02,3e-9,2e-9,1000,.001,.01,.025
        result=oxygen_minimum(d,q,bulk,critical,diff,tissue,rho,mu,beta,orbit)
        self.assertIsNotNone(result['rpm'])
        speed=math.pi*orbit*result['rpm']/60*beta
        re=rho*speed*d/mu;sc=mu/(rho*diff)
        k=(2+.6*math.sqrt(re)*sc**(1/3))*diff/d
        centre=bulk-q*d/(6*k)-q*d*d/(24*tissue)
        self.assertAlmostEqual(centre,critical,places=12)


class MorphologyTests(unittest.TestCase):
    def test_rectangle_feret_solidity(self):
        contour=np.array([[[0,0]],[[100,0]],[[100,50]],[[0,50]]],dtype=np.int32)
        result=measure_contour(contour,(200,100),(200,100))
        self.assertEqual(result['area_px2'],5000)
        self.assertAlmostEqual(result['max_feret_px'],math.sqrt(12500))
        self.assertAlmostEqual(result['min_feret_px'],50)
        self.assertAlmostEqual(result['solidity'],1)

    def test_batch_failures_exclusion_and_scale(self):
        with tempfile.TemporaryDirectory() as folder:
            image=np.full((300,400,3),245,np.uint8)
            cv2.circle(image,(100,100),35,(20,20,20),-1)
            cv2.circle(image,(260,180),45,(20,20,20),-1)
            a=Path(folder)/'a.png';Image.fromarray(image).save(a)
            b=Path(folder)/'b.png';Image.fromarray(image).save(b)
            state=analyze_batch([a,b],min_area=500,shared_scale=.5,shared_scale_confirmed=True)
            self.assertEqual(len(state['records']),2)
            self.assertEqual(len(state['failures']),1)
            r=state['records'][0]
            self.assertEqual(r['unit_basis'],'um')
            self.assertAlmostEqual(r['area'],r['area_px2']*.25)
            updated,_,_=review_batch(state,[r['object_key']])
            self.assertTrue(updated['records'][0]['excluded'])


class StatisticsTests(unittest.TestCase):
    def test_mad(self):
        r=relative_mad([1,2,3,4,100])
        self.assertEqual(r['median'],3)
        self.assertEqual(r['mad'],1)
        self.assertAlmostEqual(r['relative_mad_pct'],100/3)
        self.assertIsNone(relative_mad([-1,0,1])['relative_mad_pct'])

    def test_pca_standardized_invariance(self):
        x=np.random.default_rng(10).normal(size=(20,4))
        a=pca_fit(x);b=pca_fit(x*np.array([1,100,3,2])+np.array([20,3,9,0]))
        np.testing.assert_allclose(a['explained'],b['explained'],atol=1e-12)
        np.testing.assert_allclose(a['scores']@a['scores'].T,b['scores']@b['scores'].T,atol=1e-11)
        with self.assertRaises(ValueError):pca_fit(np.ones((4,2)))

    def test_strata_and_paper_reference(self):
        records=reference_records()
        self.assertEqual(len(records),298)
        result=summarize(records,features=['area','perimeter','paper_roundness_pct','max_feret','min_feret'])
        self.assertEqual(len(result['pca']),4)
        self.assertEqual({r['day'] for r in result['summary']},{'6','90'})
        self.assertEqual({r['unit_basis'] for r in result['summary']},{'um'})


class ReportingTests(unittest.TestCase):
    def test_csv_and_json(self):
        data=csv_bytes([{'sample':'=HYPERLINK(1)','value':-4,'status':'已排除'}]).decode('utf-8-sig')
        self.assertIn("'=HYPERLINK",data)
        self.assertIn('-4',data)
        self.assertIsNone(clean_json(float('nan')))
        self.assertEqual(json.loads(json.dumps(clean_json(np.array([1,2])))),[1,2])

    def test_extractor_excludes_viscometer(self):
        fields,evidence=extract_evidence('The orbital shaker was used at 80 rpm. A viscometer torque was measured at 100 rpm on the shaker.')
        self.assertIn('80 rpm',fields['rpm'])
        self.assertNotIn('100 rpm',fields['rpm'])
        self.assertLessEqual(len(evidence['excerpt'].split()),18)


if __name__=='__main__':unittest.main(verbosity=2)
