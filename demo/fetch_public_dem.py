import math, requests, numpy as np, io
from PIL import Image
z=15
def xy(lat,lon):
    n=2**z; x=(lon+180)/360*n; y=(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n; return x,y
lat0,lat1,lon0,lon1=37.563,37.589,126.998,127.029
x0,y1=xy(lat0,lon0); x1,y0=xy(lat1,lon1)
X=range(int(x0),int(x1)+1); Y=range(int(y0),int(y1)+1)
rows=[]
for ty in Y:
    row=[]
    for tx in X:
        r=requests.get(f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{tx}/{ty}.png',timeout=30)
        a=np.array(Image.open(io.BytesIO(r.content)).convert('RGB')).astype(float)
        row.append(a[:,:,0]*256+a[:,:,1]+a[:,:,2]/256-32768)
    rows.append(np.hstack(row))
E=np.vstack(rows)
np.savez('dem.npz',E=E,tx0=int(x0),ty0=int(y0),z=z)
print(E.shape, E.min(), E.max())
