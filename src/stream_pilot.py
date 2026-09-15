"""Extract completed P3 members from a still-downloading ZIP, verify descriptor CRC."""
import struct, zlib
from pathlib import Path
B=Path(__file__).resolve().parents[1]
f=open(B/'sources/mocap_dataset.zip','rb')
while True:
 h=f.read(30)
 if h[:4]!=b'PK\x03\x04': break
 n,e=struct.unpack('<HH',h[26:]); name=f.read(n).decode(); f.read(e)
 if not name.startswith(('P3_','__MACOSX/._P3_')): break
 d=zlib.decompressobj(-15); crc=0; size=0
 out=B/'.tmp'/name; out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('wb') as w:
  while not d.eof:
   buf=f.read(1024*1024)
   if not buf: raise RuntimeError('Member still downloading: '+name)
   raw=d.decompress(buf); w.write(raw); crc=zlib.crc32(raw,crc); size+=len(raw)
 f.seek(-len(d.unused_data),1); descriptor=f.read(16)
 assert descriptor[:4]==b'PK\x07\x08'
 expected,compressed,uncompressed=struct.unpack('<III',descriptor[4:])
 assert crc==expected and size==uncompressed
 print(name,size,'CRC PASS',flush=True)
