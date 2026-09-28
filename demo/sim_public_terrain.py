import numpy as np, math, json
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
d=np.load('dem.npz'); E=d['E']; tx0=int(d['tx0']); ty0=int(d['ty0']); z=int(d['z'])
n=2**z
def px_to_ll(px,py):
    lon=(tx0*256+px)/256/n*360-180
    lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*(ty0*256+py)/256/n)))); return lon,lat
def ll_to_px(lon,lat):
    x=(lon+180)/360*n*256-tx0*256; y=(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n*256-ty0*256; return x,y
lat_c=37.576; mpp=40075016.686*math.cos(math.radians(lat_c))/(256*n)
print('m/px',mpp, E.shape)
f=3; H,W=E.shape[0]//f, E.shape[1]//f
Z=E[:H*f,:W*f].reshape(H,f,W,f).mean(axis=(1,3)); cs=mpp*f
print('cell',cs,Z.shape)
idx=np.arange(H*W).reshape(H,W)
us=[];vs=[];L=[];S=[]
for dy,dx in [(0,1),(1,0),(1,1),(1,-1)]:
    a=idx[max(0,-dy):H-max(0,dy), max(0,-dx):W-max(0,dx)]
    b=idx[max(0,dy):H-max(0,-dy)+ (0), max(0,dx):W-max(0,-dx)] if False else idx[max(0,dy):H+min(0,dy) if dy>0 else H, max(0,dx):W+min(0,-dx) if dx>0 else W+dx]
for a in []: pass
# simpler explicit
def shift_pairs(dy,dx):
    r0=np.arange(H); c0=np.arange(W)
    R,Cc=np.meshgrid(r0,c0,indexing='ij'); R2=R+dy; C2=Cc+dx
    ok=(R2>=0)&(R2<H)&(C2>=0)&(C2<W)
    return idx[R[ok],Cc[ok]], idx[R2[ok],C2[ok]]
for dy,dx in [(0,1),(1,0),(1,1),(1,-1)]:
    a,b=shift_pairs(dy,dx); l=cs*math.hypot(dy,dx)
    s=(Z.ravel()[b]-Z.ravel()[a])/l
    us+= [a,b]; vs+=[b,a]; L+=[np.full(len(a),l)]*2; S+=[s,-s]
u=np.concatenate(us); v=np.concatenate(vs); L=np.concatenate(L); s=np.clip(np.concatenate(S),-0.4,0.4)
tob=lambda s:6*np.exp(-3.5*np.abs(s+0.05)); F=tob(0)
up=F/tob(np.abs(s)); down=1+0.5*(up-1); fac=np.where(s>=0,F/tob(s),down)
te=L/0.8*fac; tf=L/0.8
N=H*W
Ge=coo_matrix((te,(u,v)),shape=(N,N)).tocsr(); Gf=coo_matrix((tf,(u,v)),shape=(N,N)).tocsr()
stations={"창신역":(127.0151,37.5793),"동묘앞역":(127.0165,37.5733),"동대문역":(127.0098,37.5714),"보문역":(127.0194,37.5852),"신설동역":(127.0250,37.5760),"한성대입구역":(127.0063,37.5885),"혜화역":(127.0019,37.5822)}
src=[];spx={}
for k,(lo,la) in stations.items():
    x,y=ll_to_px(lo,la); c=int(x/f); r=int(y/f)
    if 0<=r<H and 0<=c<W: src.append(idx[r,c]); spx[k]=(x/1024,y/1024)
back=dijkstra(Ge,indices=src,min_only=True); go=dijkstra(Ge.T.tocsr(),indices=src,min_only=True)
fb=dijkstra(Gf,indices=src,min_only=True)
Te=(go+back).reshape(H,W); Tf=(2*fb).reshape(H,W); Tb=back.reshape(H,W); Tfb=fb.reshape(H,W)
HBI=Te/np.maximum(Tf,1e-6); HBI[Tf<1]=1
# aggregate 11x11 cells -> ~125m
g=5; GH,GW=H//g,W//g
agg=lambda A:A[:GH*g,:GW*g].reshape(GH,g,GW,g).mean(axis=(1,3))
hbi=agg(HBI); tem=agg(Te)/60; tfm=agg(Tf)/60; zg=agg(Z); home=agg(Tb/np.maximum(Tfb,1e-6))
print('grid',hbi.shape,'hbi',np.percentile(hbi,[5,50,90,99]).round(2),'te',np.percentile(tem,[5,50,95]).round(1))
# slope stats
sl=np.hypot(*np.gradient(Z,cs)); print('slope med',np.median(sl).round(3),'p90',np.percentile(sl,90).round(3))
np.savez('sim5.npz',hbi=hbi,tem=tem,tfm=tfm,zg=zg,home=home,Z=Z,cs=cs,g=g)
json.dump({"spx":spx,"cs":cs,"g":g,"GH":GH,"GW":GW,"mpp":mpp},open('meta5.json','w'))
# bounds lonlat
print(px_to_ll(0,0),px_to_ll(1024,1024))
