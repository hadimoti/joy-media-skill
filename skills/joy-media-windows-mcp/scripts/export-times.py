import sqlite3,sys,datetime,re
con=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True); cur=con.cursor()
rows=cur.execute("select asset_id,display_name,bytes,created_at from local_assets where display_name like 'joy-media-export-%' order by created_at").fetchall()
jobs={r[0]:r for r in cur.execute("select ref_id,id,status,created_at,updated_at,error from jobs where kind='render.export'")}
for a,name,b,ca in rows:
    m=re.search(r'export-(\d{13})',name)
    stamp=datetime.datetime.fromtimestamp(int(m.group(1))/1000,datetime.timezone.utc)
    staged=datetime.datetime.fromisoformat(ca.replace('Z','+00:00'))
    j=jobs.get(a)
    wk=None
    if j:
        s=datetime.datetime.fromisoformat(j[3].replace('Z','+00:00')); e=datetime.datetime.fromisoformat(j[4].replace('Z','+00:00')); wk=(e-s).total_seconds()
    print(name, 'staged bytes',b,'browser phase %.1fs'%((staged-stamp).total_seconds()),'worker %s s'%wk, j[2] if j else None, j[5] if j else None)
