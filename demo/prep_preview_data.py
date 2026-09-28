import numpy as np, json, math, base64, io
from scipy.stats import spearmanr
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
d=np.load('sim5.npz'); m=json.load(open('meta5.json'))
hbi,tem,tfm,zg,home,Z=d['hbi'],d['tem'],d['tfm'],d['zg'],d['home'],d['Z']
print('max hbi',hbi.max().round(2), (hbi>=1.3).mean().round(3), (hbi>=1.5).mean().round(3))
GH,GW=hbi.shape; cellm=float(d['cs'])*5
# ablation
te=tem.ravel(); tf=tfm.ravel(); h=hbi.ravel()
top=te>=np.quantile(te,.9); ftop=tf>=np.quantile(tf,.9)
a1=(top&~ftop).sum()/top.sum(); rho=spearmanr(te,tf).correlation
# hidden by coarse 500m (~9 cells of 57m)
k=9; CH,CW=GH//k,GW//k
coarse=hbi[:CH*k,:CW*k].reshape(CH,k,CW,k).mean(axis=(1,3))
fine=hbi[:CH*k,:CW*k]; cz=np.repeat(np.repeat(coarse,k,0),k,1)
thr=1.3
hid=((fine>=thr)&(cz<1.15)).sum()/max((fine>=thr).sum(),1)
# "평지 기준 양호(중앙값 이하)인데 HBI>=1.3"
good_flat=(h>=thr)&(tf<=np.median(tf)); a3=good_flat.sum()/max((h>=thr).sum(),1)
print('ablation',round(a1,3),round(rho,3),round(hid,3),round(a3,3))
# site: 창신역 1번출구 37.57933,127.01508 radius 300m
n=2**15; tx0,ty0=None,None
dd=np.load('dem.npz'); tx0=int(dd['tx0']); ty0=int(dd['ty0'])
def ll_to_px(lon,lat):
    x=(lon+180)/360*n*256-tx0*256; y=(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n*256-ty0*256; return x,y
sx,sy=ll_to_px(127.01508,37.57933); gx,gy=sx/15,sy/15  # 5*3 px per grid cell
R,C=np.mgrid[0:GH,0:GW]; dist=np.hypot((C+.5-gx),(R+.5-gy))*cellm
site_mean=hbi[dist<=300].mean(); pct=(hbi<site_mean).mean()
print('site',round(site_mean,3),round(pct,3))
# candidates: top HBI cells, spaced >=400m
order=np.argsort(-h); cands=[]
for i in order:
    r,c=divmod(i,GW)
    if tem[r,c]>70 or tfm[r,c]<6: continue
    if all(math.hypot(r-rr,c-cc)*cellm>=400 for rr,cc,_ in cands): cands.append((r,c,i))
    if len(cands)==5: break
st=m['spx']
def near(r,c):
    x,y=(c+.5)/GW,(r+.5)/GH; best=min(st.items(),key=lambda kv:math.hypot(kv[1][0]-x,kv[1][1]-y))
    bx,by=best[1]; dm=math.hypot(bx-x,by-y)*GW*cellm
    ang=math.degrees(math.atan2(-(y-by),x-bx)); dirs=['동','북동','북','북서','서','남서','남','남동']
    return f"{best[0]} {dirs[int(((ang+22.5)%360)//45)]}쪽 약 {int(round(dm,-1))}m"
cand=[dict(r=int(r),c=int(c),hbi=round(float(hbi[r,c]),2),te=round(float(tem[r,c]),1),tf=round(float(tfm[r,c]),1),where=near(r,c),z=round(float(zg[r,c]))) for r,c,_ in cands]
print(cand)
# hillshade + contour image
ls=LightSource(azdeg=315,altdeg=40); hs=ls.hillshade(Z,vert_exag=2,dx=d['cs'],dy=d['cs'])
fig=plt.figure(figsize=(6.82,6.82),dpi=100); ax=fig.add_axes([0,0,1,1]); ax.axis('off')
ax.imshow(hs,cmap='gray',vmin=0.25,vmax=1.05,alpha=1)
ax.contour(Z,levels=np.arange(20,160,10),colors='#3b4a40',linewidths=0.35,alpha=0.55)
ax.set_xlim(0,Z.shape[1]); ax.set_ylim(Z.shape[0],0)
buf=io.BytesIO(); fig.savefig(buf,format='jpeg',pil_kwargs={'quality':72}); plt.close(fig)
b64=base64.b64encode(buf.getvalue()).decode(); print('img kb',len(b64)//1024)
out=dict(GH=GH,GW=GW,cellm=round(cellm,1),hbi=np.round(hbi,3).ravel().tolist(),tem=np.round(tem,1).ravel().tolist(),
 tfm=np.round(tfm,1).ravel().tolist(),home=np.round(home,3).ravel().tolist(),z=np.round(zg).astype(int).ravel().tolist(),
 stations=st,site=dict(x=gx/GW,y=gy/GH,mean=round(float(site_mean),3),pct=round(float(pct),3)),
 ablation=dict(a1=round(float(a1),3),rho=round(float(rho),3),hid=round(float(hid),3),a3=round(float(a3),3)),cand=cand,
 dist=dict(p50=float(np.median(h)),share13=float((h>=1.3).mean()),share15=float((h>=1.5).mean())))
json.dump(out,open('data.json','w'),ensure_ascii=False); open('hill.b64','w').write(b64)
