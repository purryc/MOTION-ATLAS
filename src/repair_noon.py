"""One-time targeted recomputation after the documented Motive noon correction."""
import csv, zipfile
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
from analyze import B,process_zip_member,merge

def main():
 names=[]
 with zipfile.ZipFile(B/'sources/mocap_dataset.zip') as z:
  for n in z.namelist():
   if not n.endswith('.csv') or n.startswith('__'):continue
   with z.open(n) as f:h=next(csv.reader([f.readline().decode()]))
   if datetime.strptime(h[9],'%Y-%m-%d %I.%M.%S.%f %p').hour==0:names.append(n)
 print('Noon repair records',len(names),flush=True)
 with ProcessPoolExecutor(max_workers=2) as pool:
  for _ in pool.map(process_zip_member,names):pass
 merge()
if __name__=='__main__':main()
