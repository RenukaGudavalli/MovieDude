import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Search, Play, Info, Star, ChevronRight, Sparkles} from 'lucide-react';
import './style.css';

const API='http://127.0.0.1:8000';
const fallback='https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=800&q=80';

function Poster({m, wide=false}){
  return <div className={'poster '+(wide?'wide':'')}>
    {m.image_url ? <img src={m.image_url} alt={m.title} loading="lazy" onError={e=>e.currentTarget.src=fallback}/> : <img src={fallback} alt="Movie"/>}
    <div className="posterShade"/>
    <span className="year">{m.release_year || '—'}</span>
  </div>
}
function Card({m, onSelect}){
 return <article className="card" onClick={()=>onSelect?.(m)}>
   <Poster m={m}/>
   <div className="cardInfo"><h3>{m.title}</h3><p>{m.genres||'Movie'}</p><div className="rating"><Star size={14} fill="currentColor"/> {m.rating?.toFixed?.(1) ?? m.rating ?? 'N/A'} {m.similarity!=null&&<em>{Math.round(m.similarity*100)}% match</em>}</div></div>
 </article>
}
function Shelf({title,movies,onSelect}){
 if(!movies?.length)return null;
 return <section className="shelf"><div className="shelfHead"><h2>{title}</h2><ChevronRight size={20}/></div><div className="row">{movies.map((m,i)=><Card key={m.movie_id ?? i} m={m} onSelect={onSelect}/>)}</div></section>
}
function Modal({movie,onClose}){
 if(!movie)return null;
 return <div className="modalBackdrop" onClick={onClose}><div className="modal" onClick={e=>e.stopPropagation()}><button className="close" onClick={onClose}>×</button><Poster m={movie} wide/><div className="modalText"><div className="eyebrow">MOVIEDUDE</div><h2>{movie.title}</h2><p>{movie.release_year} • {movie.genres}</p>{movie.rating&&<p>⭐ {Number(movie.rating).toFixed(1)}</p>}<button className="watch" onClick={onClose}><Play size={17} fill="currentColor"/> Browse recommendations</button></div></div></div>
}
function App(){
 const [q,setQ]=useState(''); const [source,setSource]=useState(null); const [recs,setRecs]=useState([]); const [collections,setCollections]=useState({}); const [loading,setLoading]=useState(false); const [error,setError]=useState(''); const [selected,setSelected]=useState(null);
 useEffect(()=>{fetch(`${API}/api/collections`).then(r=>r.json()).then(setCollections).catch(()=>{});},[]);
 async function search(e,term=q){e?.preventDefault(); if(!term.trim())return;setLoading(true);setError('');try{const r=await fetch(`${API}/api/recommend/title?title=${encodeURIComponent(term)}&limit=10`);const d=await r.json();if(!r.ok)throw Error(d.detail||'Movie not found');setSource(d.source);setRecs(d.recommendations);window.scrollTo({top:430,behavior:'smooth'});}catch(x){setError(x.message)}finally{setLoading(false)}}
 function reset(){setSource(null);setRecs([]);setQ('');setError('');window.scrollTo({top:0,behavior:'smooth'})}
 return <div className="app">
   <header><div className="nav"><button className="brand" onClick={reset}><span className="brandMark">M</span><span>MOVIEDUDE</span></button><nav><button onClick={reset}>Home</button><button onClick={()=>document.getElementById('telugu')?.scrollIntoView({behavior:'smooth'})}>Telugu</button><button onClick={()=>document.getElementById('marvel')?.scrollIntoView({behavior:'smooth'})}>Marvel</button><button onClick={()=>document.getElementById('love')?.scrollIntoView({behavior:'smooth'})}>Love</button></nav><div className="navSearch"><Search size={17}/><form onSubmit={search}><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search movies..."/></form></div></div></header>
   {!source && <section className="hero"><div className="heroBg"/><div className="heroContent"><div className="badge"><Sparkles size={14}/> AI-POWERED RECOMMENDATIONS</div><h1>Movies you'll<br/><span>love to watch.</span></h1><p>Discover your next obsession with content-based recommendations — now with Telugu cinema, Marvel, Spider-Man and unforgettable love stories.</p><form className="bigSearch" onSubmit={search}><Search size={21}/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search for a movie..."/><button>Find Movies</button></form><div className="chips"><span>Try:</span>{['Interstellar','Inception','The Dark Knight','Spider-Man'].map(x=><button key={x} onClick={()=>{setQ(x);search(null,x)}}>{x}</button>)}</div></div></section>}
   {source && <section className="searchResults"><div className="back" onClick={reset}>← Back to home</div><div className="sourceBanner"><Poster m={source} wide/><div><div className="eyebrow">BECAUSE YOU SEARCHED FOR</div><h1>{source.title}</h1><p>{source.release_year} • {source.genres} {source.rating ? ` • ⭐ ${Number(source.rating).toFixed(1)}`:''}</p><p className="muted">Similar titles selected by the original MovieDude content-based engine.</p></div></div><Shelf title="Because you watched this" movies={recs} onSelect={setSelected}/></section>}
   {error&&<div className="error">{error}</div>}
   {!source && <main><div id="telugu"><Shelf title="Telugu Movies" movies={collections['Telugu Movies']} onSelect={setSelected}/></div><div id="marvel"><Shelf title="Marvel & Spider-Man" movies={collections['Marvel & Spider-Man']} onSelect={setSelected}/></div><div id="love"><Shelf title="Love Stories" movies={collections['Love Stories']} onSelect={setSelected}/></div><Shelf title="Trending Now" movies={collections['Trending Now']} onSelect={setSelected}/></main>}
   <footer><b>MOVIEDUDE</b><span>Content-based filtering • Python • scikit-learn • SQLite • FastAPI • React</span></footer>
   <Modal movie={selected} onClose={()=>setSelected(null)}/>
 </div>
}
createRoot(document.getElementById('root')).render(<App/>);
