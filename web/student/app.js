const $=id=>document.getElementById(id);
function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
async function loadStats(){try{const r=await fetch("/api/v1/stats");if(!r.ok)return;const d=await r.json();
  if(d.documents>0)$("statspill").textContent=`${d.documents} doc${d.documents===1?"":"s"} • ${d.chunks} chunks`;
  else $("statspill").style.display="none";}catch(e){$("statspill").style.display="none"}}
let lastAnswer="";
async function doAsk(){
  const q=$("q").value.trim(); if(!q||$("go").disabled) return;
  $("go").disabled=true;
  $("answer").className="loading";$("answer").innerHTML=`<span class="skel" style="width:92%"></span><span class="skel" style="width:78%"></span><span class="skel" style="width:85%"></span>`;
  $("meta").textContent="";$("anstime").textContent="";
  $("copybtn").style.display="none";$("vote").style.display="none";
  document.querySelectorAll("#vote button").forEach(b=>b.classList.remove("on"));
  try{
    const topk=parseInt($("topk").value||"10");
    const ra=await fetch("/api/v1/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query:q,top_k:topk,max_turns:4})});
    if(!ra.ok){$("answer").className="";$("answer").innerHTML=`<div class="err">Sorry — server error (${ra.status}). Please try again.</div>`;return}
    const d=await ra.json();
    // show answer without exposing internal chunk ids
    let ans=d.answer||"(no answer)";
    // strip any raw chunk ids that slipped into the answer
    ans=ans.replace(/\[[^\]]*::chunk_\d+[^\]]*\]/g,"").trim();
    lastAnswer=ans;
    $("answer").className="";$("answer").textContent=ans||"(no answer)";
    $("anstime").textContent=`${(d.ms||0)} ms`;
    $("meta").textContent=`${(d.ms||0)} ms • Grounded in official docs`;
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
loadStats();
