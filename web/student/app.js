const $=id=>document.getElementById(id);
function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
const CHIPS=["What is the fine for tobacco possession?","What are the hostel timings?","How do I apply for a mess rebate?","Where is the elective list?"];
function drawChips(){$("chips").innerHTML=CHIPS.map((c,i)=>`<button data-i="${i}">${esc(c.length>32?c.slice(0,32)+"…":c)}</button>`).join("");
  document.querySelectorAll("#chips button").forEach(b=>b.onclick=()=>{$("q").value=CHIPS[+b.dataset.i];doAsk()})}
function recent(){try{return JSON.parse(localStorage.getItem("cg_recent")||"[]")}catch(e){return[]}}
function pushRecent(q){let r=[q,...recent().filter(x=>x!==q)].slice(0,6);localStorage.setItem("cg_recent",JSON.stringify(r));drawRecent()}
function drawRecent(){const r=recent();$("recent").innerHTML=r.length?`<span class="lbl">Recent:</span>`+r.map(q=>`<button data-q="${esc(q)}">${esc(q.slice(0,36))}</button>`).join(""):"";
  document.querySelectorAll("#recent button").forEach(b=>b.onclick=()=>{$("q").value=b.dataset.q;doAsk()})}
async function loadStats(){try{const r=await fetch("/api/v1/stats");if(!r.ok)return;const d=await r.json();
  if(d.documents>0)$("statspill").textContent=`${d.documents} doc${d.documents===1?"":"s"} • ${d.chunks} chunks`;
  else $("statspill").style.display="none";}catch(e){$("statspill").style.display="none"}}
function parseSrc(cid){const i=(cid||"").lastIndexOf("::");return i<0?{doc:cid,chunk:""}:{doc:cid.slice(0,i),chunk:cid.slice(i+2)}}
let lastAnswer="",lastNum=[];
async function doAsk(){
  const q=$("q").value.trim(); if(!q||$("go").disabled) return; pushRecent(q);
  $("go").disabled=true;
  $("answer").className="loading";$("answer").innerHTML=`<span class="skel" style="width:92%"></span><span class="skel" style="width:78%"></span><span class="skel" style="width:85%"></span>`;
  $("citepills").innerHTML="";$("sources").innerHTML="";$("meta").textContent="";$("anstime").textContent="";
  $("copybtn").style.display="none";$("vote").style.display="none";
  document.querySelectorAll("#vote button").forEach(b=>b.classList.remove("on"));
  try{
    const topk=parseInt($("topk").value||"10");
    const [ra,rs]=await Promise.all([
      fetch("/api/v1/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query:q,top_k:topk,max_turns:4})}),
      fetch("/api/v1/search?q="+encodeURIComponent(q)+"&top_k="+topk).catch(()=>null)]);
    if(!ra.ok){$("answer").className="";$("answer").innerHTML=`<div class="err">Sorry — server error (${ra.status}). Please try again.</div>`;return}
    const d=await ra.json();
    let hits=[]; try{hits=(rs&&rs.ok)?(await rs.json()).results||[]:[]}catch(e){hits=[]}
    const byId={};hits.forEach(h=>byId[h.chunk_id]=h);
    const srcs=(d.sources||[]).slice(0,12);
    // numbered citations: longest chunk_ids first so nested replaces are safe
    lastNum=srcs.map((cid,i)=>({n:i+1,cid}));
    let html=esc(d.answer||"(no answer)");
    [...lastNum].sort((a,b)=>b.cid.length-a.cid.length).forEach(({n,cid})=>
      {html=html.split(esc(cid)).join(`<a href="#src${n}" title="${esc(cid)}">[${n}]</a>`)});
    lastAnswer=d.answer||"";
    $("answer").className="";$("answer").innerHTML=html||"(no answer)";
    $("citepills").innerHTML=lastNum.map(({n,cid})=>`<a href="#src${n}" title="${esc(cid)}">[${n}]</a>`).join("");
    // source cards, scores normalized across matched hits (relative match)
    const scores=srcs.map(cid=>byId[cid]?byId[cid].score:null).filter(s=>s!==null);
    const mx=Math.max(...scores,0),mn=Math.min(...scores,0);
    $("sources").innerHTML=srcs.map((cid,i)=>{const p=parseSrc(cid),h=byId[cid];
      const pct=h&&mx>mn?Math.round(12+88*(h.score-mn)/(mx-mn)):Math.round(100/(i+2)+20);
      const snip=h&&h.text?esc(h.text.slice(0,160))+(h.text.length>160?"…":""):"";
      const rel=h?" • relative match "+pct+"%":"";
      const snipdiv=snip?'<div class="chunk">'+snip+'</div>':"";
      return '<div class="src" id="src'+(i+1)+'"><b>['+(i+1)+'] '+esc(p.doc||cid)+'</b><div class="chunk">'+esc(p.chunk)+rel+'</div>'+snipdiv+'<div class="bar"><i style="width:'+pct+'%"></i></div></div>'}).join("");
    $("anstime").textContent=`${(d.ms||0)} ms`;
    $("meta").textContent=`Sources: ${srcs.length} • ${(d.ms||0)} ms • Grounded in official docs`;
    $("ansflag").textContent="ANSWER • grounded";
    if(lastAnswer){$("copybtn").style.display="inline-block";$("vote").style.display="inline";
      const k="cg_vote_"+lastAnswer.length+"_"+(lastAnswer.slice(0,32)||"");
      const v=localStorage.getItem(k);if(v)$(v==="1"?"yesbtn":"nobtn").classList.add("on")}
  }catch(e){$("answer").className="";$("answer").innerHTML=`<div class="err">Network error: ${esc(e.message)}</div>`}
  finally{$("go").disabled=false}
}
$("go").onclick=doAsk; $("q").addEventListener("keydown",e=>{if(e.key==="Enter")doAsk()});
$("copybtn").onclick=async()=>{try{await navigator.clipboard.writeText(lastAnswer);$("copybtn").textContent="Copied ✓";setTimeout(()=>$("copybtn").textContent="Copy answer",1500)}catch(e){$("copybtn").textContent="Copy failed"}};
function vote(v){const k="cg_vote_"+lastAnswer.length+"_"+(lastAnswer.slice(0,32)||"");localStorage.setItem(k,v?"1":"0");
  $("yesbtn").classList.toggle("on",v);$("nobtn").classList.toggle("on",!v)}
$("yesbtn").onclick=()=>vote(true);$("nobtn").onclick=()=>vote(false);
drawChips();drawRecent();loadStats();
