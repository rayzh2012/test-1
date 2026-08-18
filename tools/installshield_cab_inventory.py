#!/usr/bin/env python3
import argparse, hashlib, json, re, struct
from collections import Counter
from pathlib import Path

IMG={'.png','.jpg','.jpeg','.bmp','.gif'}
AUD={'.ogg','.mp3','.wav','.mid','.midi','.wma','.m4a'}


def find_cabs(blob):
    out=[]; start=0
    while True:
        i=blob.find(b'MSCF',start)
        if i<0: break
        try:
            sig,r1,cb,r2,coff,r3,vmin,vmaj,nfold,nfile,flags,setid,icab=struct.unpack_from('<4sIIIII BB HHHHH',blob,i)
            if cb>0 and i+cb<=len(blob) and nfile>0 and coff>=36:
                out.append((i,cb,nfold,nfile,coff))
        except struct.error: pass
        start=i+1
    return out


def inventory(path):
    p=Path(path); blob=p.read_bytes(); cabs=find_cabs(blob)
    if not cabs: raise SystemExit('no valid embedded Microsoft Cabinet found')
    # Prefer largest embedded cabinet; SFX bootstrap cabs are often small.
    base,cb,nfold,nfile,coff=max(cabs,key=lambda x:x[1])
    folder_off=base+36
    coff_data,cdata,ctype=struct.unpack_from('<IHH',blob,folder_off)
    method=ctype & 0xF
    method_name={0:'NONE',1:'MSZIP',2:'QUANTUM',3:'LZX'}.get(method,f'UNKNOWN_{method}')
    pos=base+coff; files=[]
    for _ in range(nfile):
        size,uoff,ifold,date,time,attr=struct.unpack_from('<IIHHHH',blob,pos); pos+=16
        end=blob.index(0,pos); raw=blob[pos:end]; pos=end+1
        for enc in ('utf-8','gb18030','big5','cp1252'):
            try: name=raw.decode(enc); break
            except UnicodeDecodeError: continue
        else: name=raw.decode('latin1','replace')
        files.append({'name':name.replace('\\','/'),'bytes':size,'offset_uncompressed':uoff,'folder_index':ifold})
    exts=Counter(Path(x['name']).suffix.lower() for x in files)
    tops=Counter(x['name'].split('/')[0] for x in files)
    maps=[x for x in files if re.fullmatch(r'Data/Map\d+\.rvdata2',x['name'],re.I)]
    data=[x for x in files if x['name'].lower().startswith('data/')]
    imgs=[x for x in files if Path(x['name']).suffix.lower() in IMG]
    aud=[x for x in files if Path(x['name']).suffix.lower() in AUD]
    return {
      'schema':'fangame-installshield-cab-inventory-v1',
      'source':{'file':p.name,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()},
      'cab':{'offset':base,'bytes':cb,'folder_count':nfold,'file_count':nfile,'compression':method_name,'cfdata_blocks':cdata},
      'summary':{'map_data_files':len(maps),'data_files':len(data),'image_files':len(imgs),'audio_files':len(aud),
                 'script_archive_present':any(x['name'].lower()=='data/scripts.rvdata2' for x in files),
                 'uncompressed_bytes':sum(x['bytes'] for x in files),'data_bytes':sum(x['bytes'] for x in data),
                 'image_bytes':sum(x['bytes'] for x in imgs),'audio_bytes':sum(x['bytes'] for x in aud)},
      'top_level':dict(tops),'extensions':dict(exts),'files':files,
      'evidence_boundary':'Directory inventory is structural evidence only. Compressed Data contents are not semantically parsed until decompressed.'
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('package'); ap.add_argument('--out')
    a=ap.parse_args(); obj=inventory(a.package); text=json.dumps(obj,ensure_ascii=False,indent=2)
    if a.out: Path(a.out).write_text(text+'\n',encoding='utf-8')
    else: print(text)

if __name__=='__main__': main()
