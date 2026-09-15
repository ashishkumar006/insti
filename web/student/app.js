const $=id=>document.getElementById(id);
function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function recent(){try{return JSON.parse(localStorage.getItem("cg_recent")||"[]")}catch(e){return[]}}
function pushRecent(q){let r=[q,...recent().filter(x=>x!==q)].slice(0,6);localStorage.setItem("cg_recent",JSON.stringify(r));drawRecent()}
function drawRecent(){$("recent").innerHTML=recent().map(q=>`<button data-q="${esc(q)}">${esc(q.slice(0,42))}</button>`).join("");
  document.querySelectorAll("#recent button").forEach(b=>b.onclick=()=>{$("q").value=b.dataset.q;doAsk()})}
async function doAsk(){
  const q=$("q").value.trim(); if(!q) return; pushRecent(q);
  $("answer").textContent="Searching official documents…"; $("sources").innerHTML=""; $("meta").textContent="";
  try{
    const r=await fetch("/api/v1/ask",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({query:q,top_k:parseInt($("topk").value||"10"),max_turns:4})});
    if(!r.ok){$("answer").textContent="Sorry — server error ("+r.status+"). Try again.";return}
    const d=await r.json();
    $("answer").textContent=d.answer||"(no answer)";
    $("sources").innerHTML=(d.sources||[]).slice(0,12).map(s=>`<code>${esc(s)}</code>`).join(" ");
    $("meta").textContent=`Sources: ${(d.sources||[]).length} • ${(d.ms||0)} ms • Grounded in official docs`;
  }catch(e){$("answer").textContent="Network error: "+e.message}
}
$("go").onclick=doAsk; $("q").addEventListener("keydown",e=>{if(e.key==="Enter")doAsk()}); drawRecent();
