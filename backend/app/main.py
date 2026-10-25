from pathlib import Path
import sqlite3
from typing import Optional
from urllib.parse import quote
from urllib.request import Request, urlopen
import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics import pairwise_distances

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "MovieDude.db"
app = FastAPI(title="MovieDude API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

IMAGE_CACHE = {}

# Curated shelves for the Netflix-style home page. These are presentation/catalog
# shelves; the original MovieDude ML engine remains the recommendation engine.
COLLECTIONS = {
    "Telugu Movies": [
        ("Baahubali: The Beginning", 2015, "Action, Drama, Fantasy"),
        ("Baahubali 2: The Conclusion", 2017, "Action, Drama, Fantasy"),
        ("RRR", 2022, "Action, Drama"),
        ("Pushpa: The Rise", 2021, "Action, Crime, Drama"),
        ("Jersey", 2019, "Drama, Sport"),
        ("Sita Ramam", 2022, "Romance, Drama"),
        ("Arjun Reddy", 2017, "Romance, Drama"),
        ("Eega", 2012, "Fantasy, Action, Romance"),
        ("Ala Vaikunthapurramuloo", 2020, "Action, Comedy, Drama"),
        ("Kushi", 2001, "Romance, Comedy, Drama"),
    ],
    "Marvel & Spider-Man": [
        ("Spider-Man", 2002, "Action, Adventure, Science Fiction"),
        ("Spider-Man 2", 2004, "Action, Adventure, Science Fiction"),
        ("Spider-Man 3", 2007, "Action, Adventure, Science Fiction"),
        ("The Amazing Spider-Man", 2012, "Action, Adventure, Science Fiction"),
        ("The Amazing Spider-Man 2", 2014, "Action, Adventure, Science Fiction"),
        ("Spider-Man: Homecoming", 2017, "Action, Adventure, Science Fiction"),
        ("Spider-Man: Far From Home", 2019, "Action, Adventure, Science Fiction"),
        ("Spider-Man: No Way Home", 2021, "Action, Adventure, Science Fiction"),
        ("Avengers: Infinity War", 2018, "Action, Adventure, Science Fiction"),
        ("Avengers: Endgame", 2019, "Action, Adventure, Science Fiction"),
    ],
    "Love Stories": [
        ("The Notebook", 2004, "Romance, Drama"),
        ("Titanic", 1997, "Romance, Drama"),
        ("La La Land", 2016, "Romance, Drama, Music"),
        ("Me Before You", 2016, "Romance, Drama"),
        ("About Time", 2013, "Romance, Comedy, Drama"),
        ("Before Sunrise", 1995, "Romance, Drama"),
        ("Pride & Prejudice", 2005, "Romance, Drama"),
        ("Five Feet Apart", 2019, "Romance, Drama"),
        ("The Fault in Our Stars", 2014, "Romance, Drama"),
        ("10 Things I Hate About You", 1999, "Romance, Comedy"),
    ],
    "Trending Now": [
        ("Interstellar", 2014, "Adventure, Drama, Science Fiction"),
        ("Inception", 2010, "Action, Science Fiction, Adventure"),
        ("The Dark Knight", 2008, "Drama, Action, Crime, Thriller"),
        ("Dune", 2021, "Science Fiction, Adventure, Drama"),
        ("The Martian", 2015, "Science Fiction, Drama, Adventure"),
        ("Avatar", 2009, "Action, Adventure, Science Fiction"),
        ("Oppenheimer", 2023, "Drama, History"),
        ("Joker", 2019, "Crime, Drama, Thriller"),
        ("Top Gun: Maverick", 2022, "Action, Drama"),
        ("Everything Everywhere All at Once", 2022, "Action, Comedy, Science Fiction"),
    ],
}

class LoginRequest(BaseModel):
    user_id: str
    password: str

def conn():
    return sqlite3.connect(DB_PATH)

def wiki_image(title: str):
    """Best-effort poster lookup using Wikipedia's public summary/search API."""
    if title in IMAGE_CACHE:
        return IMAGE_CACHE[title]
    try:
        slug = quote(title.replace(" ", "_"), safe="()'!,-")
        req = Request(f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}", headers={"User-Agent": "MovieDude/2.0"})
        with urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
        thumb = (data.get("thumbnail") or {}).get("source")
        if thumb:
            IMAGE_CACHE[title] = thumb
            return thumb
    except Exception:
        pass
    # Search API fallback handles titles whose Wikipedia page uses a suffix.
    try:
        params = quote(json.dumps({"action":"query","generator":"search","gsrsearch":title,"gsrnamespace":0,"gsrlimit":1,"prop":"pageimages","piprop":"thumbnail","pithumbsize":500,"format":"json"}))
        # JSON parameters are encoded above; urllib endpoint is still public and keyless.
        req = Request("https://en.wikipedia.org/w/api.php?" + "action=query&generator=search&gsrsearch=" + quote(title) + "&gsrnamespace=0&gsrlimit=1&prop=pageimages&piprop=thumbnail&pithumbsize=500&format=json", headers={"User-Agent": "MovieDude/2.0"})
        with urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            thumb = (page.get("thumbnail") or {}).get("source")
            if thumb:
                IMAGE_CACHE[title] = thumb
                return thumb
    except Exception:
        pass
    IMAGE_CACHE[title] = None
    return None

def movie_row(row):
    return {"movie_id": row[0], "title": row[1], "release_year": row[2], "genres": row[3] or "", "language": row[4] or "", "director": row[5] or "", "stars": row[6] or "", "keywords": row[7] or "", "rating": row[8], "rating_count": row[9], "image_url": wiki_image(row[1])}

def get_movie(movie_id):
    with conn() as c:
        r=c.execute("SELECT movie_id,title,release_year,genres,orginall_lang,director,stars,keywords,rating,rating_count FROM Movies_sorted WHERE movie_id=?",(movie_id,)).fetchone()
    return movie_row(r) if r else None

def find_movie(title):
    with conn() as c:
        r=c.execute("SELECT movie_id,title,release_year,genres,orginall_lang,director,stars,keywords,rating,rating_count FROM Movies_sorted WHERE title LIKE ? COLLATE NOCASE ORDER BY rating_count DESC LIMIT 1",(f"%{title}%",)).fetchone()
    return movie_row(r) if r else None

def recommend_from_features(features, limit=10, watched=None):
    watched=watched or []
    with conn() as c:
        df=pd.read_sql("SELECT movie_id,title,genres,keywords,final_score FROM Movies_sorted",c)
    df=df[~df.movie_id.isin(watched)]
    for col in ["genres","keywords"]:
        df[col]=df[col].fillna("").str.lower().str.strip().str.split(",")
        df[col]=df[col].apply(lambda x:[i.strip() for i in x if i.strip()])
    encoded=[]; encoders={}
    for col in ["genres","keywords"]:
        mlb=MultiLabelBinarizer(); encoded.append(mlb.fit_transform(df[col])); encoders[col]=mlb
    user_parts=[]
    for col, vals in zip(["genres","keywords"],features):
        vals=[v.lower().strip() for v in vals]
        known=set(encoders[col].classes_)
        vals=[v for v in vals if v in known]
        user_parts.append(encoders[col].transform([vals]) if vals else np.zeros((1,len(encoders[col].classes_)),dtype=int))
    matrix=np.hstack(encoded).astype(bool); user_vector=np.hstack(user_parts).astype(bool)
    sims=1-pairwise_distances(matrix,user_vector,metric="jaccard").flatten()
    df["similarity"]=sims
    top=df.sort_values(["similarity","final_score"],ascending=[False,False]).head(limit)
    return [get_movie(int(mid)) | {"similarity": round(float(sim),4)} for mid,sim in zip(top.movie_id,top.similarity)]

def curated_item(title, year, genres):
    m=find_movie(title)
    if m:
        return m
    return {"movie_id": f"curated-{abs(hash(title))}", "title": title, "release_year": year, "genres": genres, "rating": None, "rating_count": None, "image_url": wiki_image(title), "language": "", "director": "", "stars": "", "keywords": ""}

@app.get("/")
def root(): return {"message":"MovieDude API is running"}

@app.get("/api/health")
def health(): return {"status":"ok","database":str(DB_PATH)}

@app.post("/api/login")
def login(req: LoginRequest):
    with conn() as c:
        r=c.execute("SELECT user_id,name FROM Users WHERE user_id=? AND password=?",(req.user_id,req.password)).fetchone()
    if not r: raise HTTPException(401,"Invalid user ID or password")
    return {"user_id":r[0],"name":r[1]}

@app.get("/api/movies/search")
def search_movies(q: str = Query(min_length=1), limit:int=10):
    with conn() as c:
        rows=c.execute("SELECT movie_id,title,release_year,genres,orginall_lang,director,stars,keywords,rating,rating_count FROM Movies_sorted WHERE title LIKE ? COLLATE NOCASE ORDER BY rating_count DESC LIMIT ?",(f"%{q}%",limit)).fetchall()
    return [movie_row(r) for r in rows]

@app.get("/api/movies/{movie_id}")
def movie_detail(movie_id:int):
    m=get_movie(movie_id)
    if not m: raise HTTPException(404,"Movie not found")
    return m

@app.get("/api/recommend/title")
def recommend_by_title(title:str=Query(min_length=1),limit:int=10):
    m=find_movie(title)
    if not m: raise HTTPException(404,"No matching movie found in the MovieDude dataset")
    genres=[x.strip().lower() for x in m["genres"].split(",") if x.strip()]
    keywords=[x.strip().lower() for x in m["keywords"].split(",") if x.strip()]
    recs=recommend_from_features([genres,keywords],limit,[m["movie_id"]])
    return {"source":m,"recommendations":recs}

@app.get("/api/recommend/personalized/{user_id}")
def personalized(user_id:str,limit:int=10):
    with conn() as c:
        rows=c.execute("SELECT ud.movie_id,ud.user_rate,ud.liked,ms.genres,ms.keywords FROM Users_data ud JOIN Movies_sorted ms ON ud.movie_id=ms.movie_id WHERE ud.user_id=?",(user_id,)).fetchall()
    if not rows: raise HTTPException(404,"No activity found for this user")
    df=pd.DataFrame(rows,columns=["movie_id","user_rate","liked","genres","keywords"])
    mn,mx=df.user_rate.min(),df.user_rate.max(); df["normalized_rate"]=(df.user_rate-mn)/(mx-mn) if mx!=mn else 1.0
    df["score"]=.75*df.normalized_rate+.25*df.liked.astype(int)
    top=df.sort_values("score",ascending=False).head(max(1,len(df)//3))
    genres=[x.strip().lower() for x in ",".join(top.genres.dropna()).split(",") if x.strip()]
    keywords=[x.strip().lower() for x in ",".join(top.keywords.dropna()).split(",") if x.strip()]
    from collections import Counter
    genres=[x for x,_ in Counter(genres).most_common(6)]; keywords=[x for x,_ in Counter(keywords).most_common(10)]
    watched=[r[0] for r in rows]
    return {"user_id":user_id,"interests":{"genres":genres,"keywords":keywords},"recommendations":recommend_from_features([genres,keywords],limit,watched)}

@app.get("/api/collections")
def collections():
    return {name:[curated_item(*item) for item in items] for name,items in COLLECTIONS.items()}
