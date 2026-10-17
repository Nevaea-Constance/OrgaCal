"""Fixed-parameter foreground validation against SLiMIA manual masks, no tuning/training."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import zipfile

import cv2
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from morphology import detect_candidates,render_result


def validate(archive,output_dir):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    with zipfile.ZipFile(archive) as z:
        names=sorted(n for n in z.namelist() if '/Images/' in n and n.endswith('.ome.tiff') and 'SCALEBAR' not in n)
        for index,name in enumerate(names):
            mask_name=name.replace('/Images/','/Manual segmentations/').replace('.ome.tiff','.tiff')
            if mask_name not in z.namelist():raise ValueError('Missing manual mask: '+name)
            raw=z.read(name);mask_raw=z.read(mask_name)
            image=Image.open(BytesIO(raw));gt=np.asarray(Image.open(BytesIO(mask_raw)).convert('L'))>0
            pred=np.zeros(gt.shape,dtype=np.uint8)
            record={'image':name,'mask':mask_name,'cell_line':name.split('/')[2],
                    'image_sha256':hashlib.sha256(raw).hexdigest(),'mask_sha256':hashlib.sha256(mask_raw).hexdigest()}
            try:
                result=detect_candidates(image,5000,0)
                small=np.zeros(result['rgb'].shape[:2],dtype=np.uint8)
                cv2.drawContours(small,[o['contour'] for o in result['objects']],-1,1,cv2.FILLED)
                pred=cv2.resize(small,(gt.shape[1],gt.shape[0]),interpolation=cv2.INTER_NEAREST)
                record['candidate_count']=len(result['objects'])
                record['status']='ok' if result['objects'] else 'zero candidates'
                if index in (0,15,30,45):
                    render_result(result)[0].save(output_dir/f'prediction_{index:02}.png')
                    Image.fromarray(np.uint8(gt)*255).save(output_dir/f'mask_{index:02}.png')
            except (ValueError,OSError) as error:
                record.update(candidate_count=0,status=str(error))
            p=pred.astype(bool)
            intersection=int(np.count_nonzero(p&gt));union=int(np.count_nonzero(p|gt))
            pred_area=int(p.sum());gt_area=int(gt.sum())
            record.update(iou=intersection/union if union else 1.0,
                          dice=2*intersection/(pred_area+gt_area) if pred_area+gt_area else 1.0,
                          relative_foreground_area_error=(pred_area-gt_area)/gt_area if gt_area else None)
            rows.append(record)
    result={'dataset':'SLiMIA OperaPhenix','doi':'10.6084/m9.figshare.27390402.v1',
            'article':'https://www.nature.com/articles/s41597-025-04441-x','license':'CC BY 4.0',
            'archive_sha256':hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
            'selection':'all paired non-scalebar images from the OperaPhenix subdataset, sorted filenames',
            'parameters':{'min_area_px2':5000,'threshold_offset':0,'manual_exclusions':False},
            'n_images':len(rows),'zero_or_failed':sum(r['status']!='ok' for r in rows),
            'mean_iou':float(np.mean([r['iou'] for r in rows])), 'median_iou':float(np.median([r['iou'] for r in rows])),
            'mean_dice':float(np.mean([r['dice'] for r in rows])), 'median_dice':float(np.median([r['dice'] for r in rows])),
            'limitations':['Foreground union overlap, not instance segmentation accuracy.',
                           'External spheroid dataset, not brain-organoid or shaker validation.',
                           'One microscope, 4 cell lines and correlated technical/biological replicates; no independence claim.',
                           'No tuning on these labels; all failures remain in the denominator.'],'rows':rows}
    (ROOT/'data/reference/segmentation_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('archive');parser.add_argument('--output-dir',required=True)
    args=parser.parse_args();validate(args.archive,args.output_dir)
