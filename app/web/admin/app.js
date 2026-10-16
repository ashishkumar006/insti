let tok=localStorage.getItem("cg_admin_tok")||"";
const $=id=>document.getElementById(id);
const H=()=>({"Authorization":"Bearer "+tok});
function showLogin(v){$("loginCard").style.display=v?"block":"none";$("dash").style.display=v?"none":"block";$("logout").style.display=v?"none":"inline-block"}
if(tok){showLogin(false);load()}else showLogin(true);
$("loginBtn").onclick=async()=>{
  $("loginErr").textContent="";
  const r=await fetch("/api/v1/admin/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({email:$("email").value,password:$("pw").value})});
  if(!r.ok){$("loginErr").textContent="Invalid email or password";return}
  const d=await r.json();tok=d.token;localStorage.setItem("cg_admin_tok",tok);
  $("who").textContent=d.email;showLogin(false);load();
};
$("logout").onclick=()=>{tok="";localStorage.removeItem("cg_admin_tok");showLogin(true);stopPolling()};

// ---------- uploads: multi-file, fire-and-forget ----------
$("pick").onclick=()=>$("file").click();
$("file").onchange=()=>{const f=$("file").files;if(f.length)uploadFiles(f);$("file").value=""};
["dragover","dragenter"].forEach(ev=>$("drop").addEventListener(ev,e=>{e.preventDefault();$("drop").style.background="#F1E8D2"}));
["dragleave","drop"].forEach(ev=>$("drop").addEventListener(ev,e=>{e.preventDefault();$("drop").style.background=""}));
$("drop").addEventListener("drop",e=>{if(e.dataTransfer.files.length)uploadFiles(e.dataTransfer.files)});

function uploadFiles(list){
  const files=Array.from(list);
  let i=0,failed=0;
  $("upbar").style.display="block";
  $("upmsg").textContent="Uploading 0/"+files.length+" …";
  const next=()=>{
    if(i>=files.length){
      $("upbar").style.display="none";
      $("upmsg").textContent=failed
        ? files.length+" file(s) queued, "+failed+" failed — see documents below for progress."
        : files.length+" file(s) queued — chunking & embedding continue in the background (see Documents below).";
      $("upmeta").textContent="";
      load();
      return;
    }
    const f=files[i];
    $("upmsg").textContent="Uploading "+(i+1)+"/"+files.length+": "+f.name;
    $("upfill").style.width="0%";$("upmeta").textContent="0%";
    const xhr=new XMLHttpRequest();
    xhr.open("POST","/api/v1/admin/documents/upload");
    xhr.setRequestHeader("Authorization","Bearer "+tok);
    xhr.upload.onprogress=e=>{
      if(!e.lengthComputable)return;
      const p=Math.round(e.loaded/e.total*100);
      $("upfill").style.width=p+"%";
      $("upmeta").textContent=p+"% · "+Math.round(e.loaded/1024)+" / "+Math.round(e.total/1024)+" KB";
    };
    xhr.onload=()=>{
      $("upfill").style.width="100%";
      let d={};try{d=JSON.parse(xhr.responseText)}catch(e){}
      if(xhr.status<200||xhr.status>=300){failed++;$("upmeta").textContent="failed: "+(d.detail||xhr.status);}
      else if(d.status==="duplicate"){$("upmeta").textContent="duplicate of "+d.existing+" — skipped";}
      i++;load();setTimeout(next,50);
    };
    xhr.onerror=()=>{failed++;i++;setTimeout(next,300);};
    const fd=new FormData();fd.append("file",f);xhr.send(fd);
  };
  next();
}

// ---------- documents list + live job progress ----------
function renderDocs(list){
  $("docs").innerHTML=`<table><thead><tr><th>File</th><th>SHA</th><th>Status</th><th>Chunks</th><th>Embed model</th><th>Updated</th><th></th></tr></thead><tbody>`+
    list.map(x=>{const m=x.models||"";const stale=!/gemini-embedding-2/.test(m);return `<tr><td>${x.filename}</td><td><code>${x.sha_short}</code></td>
    <td><span class="pill ${x.status}">${x.status}</span></td><td>${x.chunks||"—"}</td>
    <td style="font-size:12px">${m?m:"—"}${stale&&x.chunks?" ⚠️":""}</td><td>${x.updated_at||""}</td>
    <td><button class="ghost" onclick='reDoc("${x.id}","missing")' title="Fill chunks that failed/skipped embedding">Fill gaps</button>
        <button class="ghost" onclick='reDoc("${x.id}","all")' title="Wipe and re-embed every chunk with the current model (use after changing PAYGO_EMBED_MODEL)">Re-embed all</button>
        <button onclick="delDoc('${x.id}')">Delete</button></td></tr>`}).join("")+`</tbody></table>`;
}

async function load(){
  const r=await fetch("/api/v1/admin/documents",{headers:H()});
  if(r.status===401){showLogin(true);return}
  const d=await r.json();
  renderDocs(d.documents);
  const emb=d.documents.filter(x=>x.status==="embedding"&&x.job_id);
  if(emb.length)startPolling();
  else{$("jobmeta").textContent="No active job.";$("jobfill").style.width="0%";$("log").textContent="Progress appears here while documents embed."}
}

// Poll documents while anything is embedding; live bar + log for the active job.
let pollT=null;
function startPolling(){if(pollT)return;pollDocs()}
function stopPolling(){if(pollT){clearTimeout(pollT);pollT=null}}
async function pollDocs(){
  try{
    const r=await fetch("/api/v1/admin/documents",{headers:H()});
    if(r.status===401){stopPolling();return}
    const d=await r.json();
    renderDocs(d.documents);
    const emb=d.documents.find(x=>x.status==="embedding"&&x.job_id);
    if(!emb){pollT=null;$("jobmeta").textContent="All queued documents embedded ✓";$("jobfill").style.width="100%";$("log").textContent=(d.documents[0]&&d.documents[0].error)||"";load();return}
    const jr=await fetch("/api/v1/admin/jobs/"+emb.job_id,{headers:H()});
    if(jr.ok){
      const j=await jr.json();
      const total=j.total||0,done=j.done||0;
      $("jobfill").style.width=(total?Math.min(100,Math.round(done/total*100)):5)+"%";
      $("jobmeta").textContent=`${emb.filename}: ${done} / ${total||"?"} chunks · ${j.status}`;
      $("log").textContent=(j.log||[]).join("\n");
    }
    pollT=setTimeout(pollDocs,1500);
  }catch(e){pollT=setTimeout(pollDocs,4000)}
}

async function delDoc(id){if(!confirm("Delete this document and all its chunks?"))return;await fetch("/api/v1/admin/documents/"+id,{method:"DELETE",headers:H()});load()}
async function reDoc(id,scope){
  if(scope==="all"&&!confirm("Wipe and re-embed ALL chunks with the current embedding model?\nUse this after changing PAYGO_EMBED_MODEL.\nFor new chunk boundaries, Delete + re-upload instead."))return;
  const r=await fetch("/api/v1/admin/documents/"+id+"/reindex?scope="+scope,{method:"POST",headers:H()});
  if(!r.ok){$("upmsg").textContent="Re-embed failed to start ("+r.status+")";return}
  const d=await r.json();$("upmsg").textContent="Re-embed started ("+d.scope+") — watch progress below.";load();
}
