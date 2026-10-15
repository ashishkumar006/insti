const $=id=>document.getElementById(id);
function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function formatAnswer(s){
  let h=esc(s);
  // code blocks
  h=h.replace(/```([\s\S]*?)```/g,(m,c)=>`<pre><code>${c}</code></pre>`);
  h=h.replace(/`([^`]+)`/g,'<code>$1</code>');
  // bold **text** and __text__
  h=h.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
  h=h.replace(/__([^_]+)__/g,'<strong>$1</strong>');
  // italic *text* and _text_ (after bold, avoid **)
  h=h.replace(/(^|[^*])\*([^*\n]+)\*([^*]|$)/g,(m,a,b,c)=>a+'<em>'+b+'</em>'+c);
  h=h.replace(/(^|[^_])_([^_\n]+)_([^_]|$)/g,(m,a,b,c)=>a+'<em>'+b+'</em>'+c);
  // headers
  h=h.replace(/^### (.+)$/gm,'<h4>$1</h4>');
  h=h.replace(/^## (.+)$/gm,'<h3>$1</h3>');
  h=h.replace(/^# (.+)$/gm,'<h3>$1</h3>');
  // unordered lists: lines starting with - or * or •
  h=h.replace(/^\s*[-*•]\s+(.+)$/gm,'<li>$1</li>');
  // ordered lists: 1. 2.
  h=h.replace(/^\s*\d+\.\s+(.+)$/gm,'<li class="ol">$1</li>');
  // wrap consecutive <li> into <ul> (simple)
  h=h.replace(/(<li>.*?<\/li>)(?=(<br>)*<li>)/gs,'$1');
  // use placeholder for lists to group
  // group <li> blocks
  h=h.replace(/(<li>[\s\S]*?<\/li>)/g,(m)=>`<ul>${m}</ul>`);
  h=h.replace(/<\/ul><br><ul>/g,'');
  h=h.replace(/<\/ul>\s*<ul>/g,'');
  // paragraphs: double <br> -> paragraph
  h=h.replace(/(<br>\s*){2,}/g,'</p><p>');
  h=`<p>${h}</p>`;
  h=h.replace(/<p><\/p>/g,'');
  h=h.replace(/<p><h/g,'<h'); h=h.replace(/<\/h([34])><\/p>/g,'</h$1>');
  h=h.replace(/<p><pre>/g,'<pre>'); h=h.replace(/<\/pre><\/p>/g,'</pre>');
  h=h.replace(/<p><ul>/g,'<ul>'); h=h.replace(/<\/ul><\/p>/g,'</ul>');
  return h;
}
async function loadStats(){try{const r=await fetch("/api/v1/stats");if(!r.ok)return;const d=await r.json();
  if(d.documents>0)$("statspill").textContent=`${d.documents} doc${d.documents===1?"":"s"} • ${d.chunks} chunks`;
  else $("statspill").style.display="none";}catch(e){$("statspill").style.display="none"}}
let lastAnswer="",lastQuery="",lastMs=0;
async function doAsk(){
  const q=$("q").value.trim(); if(!q||$("go").disabled) return;
  lastQuery=q;
  $("go").disabled=true;
  $("answer").className="loading";$("answer").innerHTML=`<span class="skel" style="width:92%"></span><span class="skel" style="width:78%"></span><span class="skel" style="width:85%"></span>`;
  $("meta").textContent="";$("anstime").textContent="";
  $("copybtn").style.display="none";$("vote").style.display="none";
  document.querySelectorAll("#vote button").forEach(b=>b.classList.remove("on"));
  try{
    const topk=10;
    const ra=await fetch("/api/v1/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query:q,top_k:topk,max_turns:4})});
    if(!ra.ok){$("answer").className="";$("answer").innerHTML=`<div class="err">Sorry — server error (${ra.status}). Please try again.</div>`;return}
    const d=await ra.json();
    let ans=d.answer||"(no answer)";
    ans=ans.replace(/\[[^\]]*::chunk_\d+[^\]]*\]/g,"").replace(/\[chunk_\d+[^\]]*\]/g,"").trim();
    lastAnswer=ans; lastMs=d.ms||0;
    $("answer").className="answer-content";$("answer").innerHTML=formatAnswer(ans)||"(no answer)";
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
function vote(v){
  const k="cg_vote_"+lastAnswer.length+"_"+(lastAnswer.slice(0,32)||"");
  localStorage.setItem(k,v?"1":"0");
  $("yesbtn").classList.toggle("on",v);$("nobtn").classList.toggle("on",!v);
  // persist for improvement: query + answer + helpful tag → var/feedback.jsonl
  try{
    fetch("/api/v1/feedback",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({query:lastQuery, answer:lastAnswer, helpful:!!v, ms:lastMs})}).catch(()=>{});
  }catch(e){}
}
$("yesbtn").onclick=()=>vote(true);$("nobtn").onclick=()=>vote(false);
loadStats();
