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
$("logout").onclick=()=>{tok="";localStorage.removeItem("cg_admin_tok");showLogin(true)};
$("pick").onclick=()=>$("file").click();
$("file").onchange=()=>{
  const f=$("file").files[0];if(!f)return;
  // Upload with real progress (fetch can't report upload progress, XHR can)
  $("upmsg").textContent="Uploading "+f.name+" …";
  $("upbar").style.display="block";$("upfill").style.width="0%";$("upmeta").textContent="0%";
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
    let d={}; try{d=JSON.parse(xhr.responseText)}catch(e){}
    if(xhr.status<200||xhr.status>=300){$("upmsg").textContent="Failed: "+(d.detail||xhr.status);$("upmeta").textContent="";return}
    if(d.status==="duplicate"){$("upmsg").textContent=`Duplicate detected — identical to ${d.existing}. Skipped embedding.`;$("upmeta").textContent="0 embeddings used ✓"}
    else{$("upmsg").textContent="Upload complete — chunking & embedding started…";$("upmeta").textContent="100% uploaded";if(d.job_id)follow(d.job_id)}
    load();
  };
  xhr.onerror=()=>{$("upmsg").textContent="Network error during upload";};
  const fd=new FormData();fd.append("file",f);
  xhr.send(fd);
};
async function load(){
  const r=await fetch("/api/v1/admin/documents",{headers:H()});
  if(r.status===401){showLogin(true);return}
  const d=await r.json();
  $("docs").innerHTML=`<table><thead><tr><th>File</th><th>SHA</th><th>Status</th><th>Chunks</th><th>Updated</th><th></th></tr></thead><tbody>`+
    d.documents.map(x=>`<tr><td>${x.filename}</td><td><code>${x.sha_short}</code></td>
    <td><span class="pill ${x.status}">${x.status}</span></td><td>${x.chunks||"—"}</td><td>${x.updated_at||""}</td>
    <td><button onclick="delDoc('${x.id}')">Delete</button></td></tr>`).join("")+`</tbody></table>`;
}
async function delDoc(id){if(!confirm("Delete indexed chunks?"))return;await fetch("/api/v1/admin/documents/"+id,{method:"DELETE",headers:H()});load()}
async function follow(job){
  // Poll until the job finishes — no artificial cap (large books take a while).
  // Shows a determinate bar when the server reports done/total, else elapsed time.
  const t0=Date.now();
  $("jobfill").style.width="0%";$("jobmeta").textContent="Starting…";
  for(let i=0;i<3600;i++){
    const r=await fetch("/api/v1/admin/jobs/"+job,{headers:H()});
    if(!r.ok){$("jobmeta").textContent="Job not found";break}
    const j=await r.json();
    $("log").textContent=(j.log||[]).join("\n");
    const el=Math.round((Date.now()-t0)/1000);
    if((j.total||0)>0){
      const p=Math.min(100,Math.round((j.done||0)/j.total*100));
      $("jobfill").style.width=p+"%";
      $("jobmeta").textContent=`${j.done||0} / ${j.total} chunks embedded · ${p}% · ${el}s elapsed · status: ${j.status}`;
    } else {
      $("jobmeta").textContent=`Working… ${el}s elapsed · status: ${j.status}`;
    }
    if(j.status!=="running"){
      if((j.total||0)>0){$("jobfill").style.width="100%"}
      $("jobmeta").textContent+=j.status==="done"?" — complete ✓":" — "+j.status;
      load();break;
    }
    await new Promise(r=>setTimeout(r,1500));
  }
}