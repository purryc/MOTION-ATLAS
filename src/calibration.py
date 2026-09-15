"""Expose existing analysis touch baselines without modifying recorded coordinates."""
import json
import pandas as pd
from analyze import B,save_json

def main():
 summary=pd.read_csv(B/'data/summary.csv');thumb=summary[(summary.finger=='Thumb')&(summary.basis=='context_500ms')]
 records={}
 for (participant,phone,condition),g in thumb.groupby(['participant','phone','condition']):
  record=f'P{int(participant)}_{phone}_{condition}';baseline=g.thumb_touch_marker_baseline_mm.dropna().unique()
  if len(baseline)>1 and baseline.max()-baseline.min()>1e-8:raise ValueError('Inconsistent recording baseline')
  records[record]=dict(baseline_mm=float(baseline[0]) if len(baseline) else None,method='record_contact_median',marker='Thumb_Fn',source='data/summary.csv:thumb_touch_marker_baseline_mm',scope='participant_phone_condition',minimum_valid_contact_samples=20,interpretation='signed marker height minus known-contact median; not measured finger-pad clearance',physical_sync_verified=False)
 save_json(B/'outputs/calibration.json',dict(version=1,unit='mm',records=records))
 for c in json.loads((B/'outputs/index.json').read_text())['clips']:
  path=B/'outputs'/c['meta'];md=json.loads(path.read_text());record=f'P{c["participant"]}_{c["phone"]}_{c["condition"]}';md['height_calibration']=records[record];save_json(path,md)
 print('Height calibration metadata',len(records),'records',flush=True)

if __name__=='__main__':main()
