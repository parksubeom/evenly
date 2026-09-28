# -*- coding: utf-8 -*-
"""가상 테스트 데이터 생성 (안심구역 방문 전 내 PC에서 코드 동작 확인용)
실행: python tools/make_test_data.py → testdata/ 폴더 생성, config.py 경로를 testdata로 바꿔 run_all.py 실행"""
import numpy as np, geopandas as gpd, rasterio, os
from rasterio.transform import from_origin
from shapely.geometry import LineString, Polygon, Point, box
crs="EPSG:5186"; X0,Y0=200000,545000; W=2000
r=np.random.RandomState(0)
def z(x,y): return 30+70*np.exp(-(((x-X0-1300)**2+(y-Y0-1200)**2)/(2*400**2)))
BASE=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","testdata"); os.makedirs(BASE,exist_ok=True); os.chdir(BASE); os.makedirs("dem",exist_ok=True)
for i,(ox) in enumerate([X0, X0+1000]):
    xs=ox+np.arange(200)*5+2.5; ys=Y0+W-np.arange(400)*5-2.5
    XX,YY=np.meshgrid(xs,ys); arr=z(XX,YY).astype("float32")
    with rasterio.open(f"dem/tile{i}.img","w",driver="HFA",height=400,width=200,count=1,dtype="float32",crs=crs,transform=from_origin(ox,Y0+W,5,5),nodata=-9999) as d: d.write(arr,1)
for sheet,(xa,xb) in {"37612006":(0,1000),"37612007":(1000,2000)}.items():
    d=f"map/{sheet}"; os.makedirs(d,exist_ok=True)
    roads=[]
    for y in range(0,W+1,100): roads.append(LineString([(X0+xa,Y0+y),(X0+xb,Y0+y)]))
    for x in range(xa,xb+1,200): roads.append(LineString([(X0+x,Y0),(X0+x,Y0+W)]))
    gpd.GeoDataFrame({"ROAD_SE":["RDC014"]*len(roads)},geometry=roads,crs=crs).to_file(f"{d}/N3L_A0020000.shp",encoding="cp949")
    sw=[LineString([(X0+xa,Y0+y+3),(X0+xb,Y0+y+3)]) for y in range(0,W+1,500)]
    g=gpd.GeoDataFrame(geometry=sw,crs=crs); g.to_file(f"{d}/N3L_A0033328.shp")
    os.remove(f"{d}/N3L_A0033328.prj")  # prj 누락 상황 테스트
    bl=[];use=[];fl=[]
    for k in range(250):
        cx=X0+r.uniform(xa+10,xb-10); cy=Y0+r.uniform(10,W-10)
        bl.append(box(cx-6,cy-6,cx+6,cy+6)); use.append(r.choice(["BDU001","BDU002","BDU003","BDU009","BDU011"],p=[.5,.3,.12,.04,.04])); fl.append(r.randint(1,6))
    gpd.GeoDataFrame({"BPRP_SE":use,"BULD_SE":"BDC001","BFLR_CO":fl},geometry=bl,crs=crs).to_file(f"{d}/N3A_B0010000.shp",encoding="cp949")
    st=[]
    for x in range(xa+100,xb,200):   # 도로 사이 중간에 끊긴 계단 (네트워크 미통과)
        st.append(box(X0+x-2,Y0+1105,X0+x+2,Y0+1195))
    st.append(box(X0+xa+197,Y0+1310,X0+xa+203,Y0+1390))  # 도로가 지나는 계단
    gpd.GeoDataFrame({"ARSFCKD_SE":["PGS001"]*len(st),"WIDT":[3]*len(st)},geometry=st,crs=crs).to_file(f"{d}/N3A_C0390000.shp")
    bs=[Point(X0+x,Y0+50) for x in range(xa+100,xb,400)]
    gpd.GeoDataFrame({"PTRFCKD_SE":["BTS005"]*len(bs)},geometry=bs,crs=crs).to_file(f"{d}/N3P_A0140000.shp")
gpd.GeoDataFrame(geometry=[box(X0+50,Y0+1990,X0+350,Y0+2010)],crs=crs).to_file("map/37612006/N3A_A0070000.shp")
# 외부 데이터
from pyproj import Transformer
t=Transformer.from_crs(crs,"EPSG:4326",always_xy=True)
os.makedirs("ext",exist_ok=True)
import pandas as pd
ph=[t.transform(X0+x,Y0+y) for x,y in [(150,150),(1700,300),(900,1900)]]
pd.DataFrame({"name":["약국A","약국B","약국C"],"lon":[p[0] for p in ph],"lat":[p[1] for p in ph]}).to_csv("ext/pharmacy.csv",index=False,encoding="utf-8-sig")
s=[t.transform(X0+x,Y0+y) for x,y in [(1300,1200),(300,300)]]
pd.DataFrame({"name":["언덕정상","평지"],"lon":[p[0] for p in s],"lat":[p[1] for p in s],"radius_m":[300,300]}).to_csv("ext/sites.csv",index=False,encoding="utf-8-sig")
o=t.transform(X0+1300,Y0+1100); dd=t.transform(X0+1300,Y0+1200); o2=t.transform(X0+200,Y0+200); d2=t.transform(X0+600,Y0+200)
pd.DataFrame({"name":["계단구간","평지구간"],"o_lon":[o[0],o2[0]],"o_lat":[o[1],o2[1]],"d_lon":[dd[0],d2[0]],"d_lat":[dd[1],d2[1]],"measured_min":[3.5,6.2]}).to_csv("ext/od_pairs.csv",index=False,encoding="utf-8-sig")
print("ok")
