import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
kr=[f for f in fm.findSystemFonts() if 'NotoSansCJK' in f and 'Regular' in f]
fp=fm.FontProperties(fname=kr[0]) if kr else None
fm.fontManager.addfont(kr[0]); plt.rcParams['font.family']=fm.FontProperties(fname=kr[0]).get_name()
DARK='1F3B2D'; ORANGE='E8743B'; SAGE='7FA88E'; TINT='EEF3EF'; INK='22302A'
c=lambda h:'#'+h

# terrain
x=np.linspace(0,10,500); y=np.linspace(0,5.625,300); X,Y=np.meshgrid(x,y)
def terrain(X,Y,seed=3):
    r=np.random.RandomState(seed); Z=np.zeros_like(X)
    for _ in range(9):
        cx,cy=r.uniform(0,10),r.uniform(0,5.6); s=r.uniform(0.8,2.2); h=r.uniform(0.5,1.5)
        Z+=h*np.exp(-((X-cx)**2+(Y-cy)**2)/(2*s*s))
    return Z
Z=terrain(X,Y)
# contour background (dark)
for name,bg,lc,alpha in [('contour_dark',DARK,'3E6450',1.0)]:
    fig=plt.figure(figsize=(10,5.625),dpi=200); ax=fig.add_axes([0,0,1,1]); ax.set_facecolor(c(bg)); fig.patch.set_facecolor(c(bg))
    ax.contour(X,Y,Z,levels=26,colors=c(lc),linewidths=0.7,alpha=alpha)
    ax.set_xlim(0,10); ax.set_ylim(0,5.625); ax.axis('off'); fig.savefig(f'img/{name}.png',facecolor=c(bg)); plt.close()
# light contour (for tint corners)
fig=plt.figure(figsize=(10,5.625),dpi=200); ax=fig.add_axes([0,0,1,1])
ax.contour(X,Y,terrain(X,Y,7),levels=22,colors=c('D5E2D8'),linewidths=0.8)
ax.set_xlim(0,10); ax.set_ylim(0,5.625); ax.axis('off'); fig.savefig('img/contour_light.png',transparent=True); plt.close()

# elevation profile: flat vs hill 450m
d=np.linspace(0,450,200)
h=54*(1/(1+np.exp(-(d-225)/70)))  # home up top at end (return trip uphill)
h=h-h.min(); h=h/h.max()*54
fig,ax=plt.subplots(figsize=(6.2,3.0),dpi=220)
ax.fill_between(d,0,h,color=c(ORANGE),alpha=0.15); ax.plot(d,h,color=c(ORANGE),lw=3)
ax.plot(d,np.zeros_like(d)+0.5,color=c(SAGE),lw=3,ls='--')
ax.scatter([0],[0.5],s=90,color=c(INK),zorder=5); ax.scatter([450],[54],s=90,color=c(INK),zorder=5)
ax.annotate('약국',(0,0.5),xytext=(8,10),textcoords='offset points',fontsize=12,color=c(INK))
ax.annotate('집',(450,54),xytext=(-22,8),textcoords='offset points',fontsize=12,color=c(INK))
ax.text(250,3.5,'지도앱이 가정하는 길 (평지)',color=c('5E8A6E'),fontsize=11)
ax.text(215,40,'실제 귀갓길: 고도 +54m\n평균 경사 12%',color=c(ORANGE),fontsize=11,ha='right')
ax.set_xlabel('거리 (m)',fontsize=10,color='#555'); ax.set_ylabel('고도차 (m)',fontsize=10,color='#555')
for s in ['top','right']: ax.spines[s].set_visible(False)
for s in ['left','bottom']: ax.spines[s].set_color('#bbb')
ax.tick_params(colors='#666',labelsize=9); ax.set_ylim(-3,66); ax.set_xlim(-10,470)
fig.tight_layout(); fig.savefig('img/profile.png',transparent=True); plt.close()

# mock HBI map
r=np.random.RandomState(11)
x=np.linspace(0,6,400); y=np.linspace(0,4,300); X,Y=np.meshgrid(x,y)
Z=1.4*np.exp(-((X-4.3)**2+(Y-2.6)**2)/1.3)+0.9*np.exp(-((X-1.2)**2+(Y-3.2)**2)/0.8)+0.2*Y/4
fig=plt.figure(figsize=(6,4),dpi=220); ax=fig.add_axes([0,0,1,1]); ax.set_facecolor('#F7F9F7')
ax.contour(X,Y,Z,levels=18,colors='#C9D6CC',linewidths=0.7)
# roads
for yy in np.arange(0.3,4,0.55): ax.plot([0,6],[yy+0.08*np.sin(yy*3),yy-0.1],color='white',lw=3.2,zorder=2); ax.plot([0,6],[yy+0.08*np.sin(yy*3),yy-0.1],color='#D9DED9',lw=0.6,zorder=2)
for xx in np.arange(0.4,6,0.7): ax.plot([xx,xx+0.15],[0,4],color='white',lw=3.2,zorder=2)
# parcels
from scipy.ndimage import sobel
gz=np.hypot(sobel(Z,0),sobel(Z,1))
pts=r.uniform([0.1,0.1],[5.9,3.9],(420,2))
vals=[]
for px,py in pts:
    i=int(py/4*299); j=int(px/6*399)
    elev=Z[i,j]; vals.append(1+elev*0.75+r.normal(0,0.08))
vals=np.clip(np.array(vals),1,2.6)
from matplotlib.colors import LinearSegmentedColormap
cm=LinearSegmentedColormap.from_list('h',['#7FA88E','#F2D16B','#E8743B','#B23A2A'])
ax.scatter(pts[:,0],pts[:,1],c=vals,cmap=cm,vmin=1,vmax=2.4,s=26,marker='s',edgecolors='white',linewidths=0.4,zorder=3)
fac=[(0.6,0.4,'약국'),(2.9,0.9,'정류장'),(5.3,0.5,'의원')]
for fx,fy,t in fac:
    ax.scatter([fx],[fy],s=140,marker='P',color='#1F3B2D',edgecolors='white',zorder=5)
    ax.text(fx+0.1,fy+0.1,t,fontsize=9,color='#1F3B2D',zorder=6,fontweight='bold')
ax.set_xlim(0,6); ax.set_ylim(0,4); ax.axis('off')
ax.text(0.12,3.78,'분석 예시 · 가상 데이터',fontsize=9,color='#777',zorder=7,bbox=dict(fc='white',ec='none',alpha=0.85))
fig.savefig('img/hbi_map.png'); plt.close()
# legend bar
fig=plt.figure(figsize=(3,0.5),dpi=220); ax=fig.add_axes([0.05,0.45,0.9,0.3])
ax.imshow(np.linspace(0,1,256)[None,:],aspect='auto',cmap=cm); ax.set_yticks([]); ax.set_xticks([0,85,170,255]); ax.set_xticklabels(['1.0','1.5','2.0','2.4+'],fontsize=8,color='#555')
for s in ax.spines.values(): s.set_visible(False)
fig.savefig('img/legend.png',transparent=True); plt.close()
print('done')
