/** SentinelScan Log Site — Health screen using only Workstream B fields. */
(function(){
  const el=id=>document.getElementById(id); const set=(id,v)=>{const e=el(id);if(e)e.textContent=v;};
  const fmt=n=>Number(n||0).toLocaleString();
  async function load(){
    try { const d=await window.apiFetch("/api/health"); renderKPIs(d); renderWorkers(Array.isArray(d.workers)?d.workers:[]); renderUnsupported(); set("healthLastRefreshed","Last refreshed "+new Date().toLocaleTimeString()); }
    catch(e){ console.error("Health load error",e); }
  }
  function renderKPIs(d){
    set("kpiErrorRate", typeof d.error_rate==="number"?(d.error_rate*100).toFixed(1)+"%":"N/A");
    set("kpiErrorSub","Observed across telemetry in the last hour");
    set("kpiLatency", (typeof d.p50_ms==="number"&&typeof d.p95_ms==="number")?`${d.p50_ms}ms / ${d.p95_ms}ms`:"N/A");
    set("kpiRequests", typeof d.requests_1h==="number"?fmt(d.requests_1h)+" requests in 1h":"N/A");
    set("kpiRetry","N/A");
    set("kpiFailure", typeof d.llm_failure_rate==="number"?"Failures: "+(d.llm_failure_rate*100).toFixed(1)+"%":"Failures: N/A");
  }
  function renderWorkers(list){
    const tbody=el("workersTbody"); if(!tbody)return; tbody.replaceChildren();
    if(!list.length){ const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=5;td.className="ls-empty";td.textContent="No worker health telemetry recorded yet.";tr.appendChild(td);tbody.appendChild(tr);set("kpiWorkerSuccess","N/A");set("kpiWorkerSub","No worker telemetry in current window");return; }
    let ok=0,failed=0;
    [...list].sort((a,b)=>String(a.name||"").localeCompare(String(b.name||""))).forEach(w=>{
      ok+=Number(w.ok||0); failed+=Number(w.failed||0); const rate=typeof w.success_rate==="number"?w.success_rate:((w.ok||0)+(w.failed||0)?(w.ok||0)/((w.ok||0)+(w.failed||0)):null);
      const tr=document.createElement("tr"); [w.name||"unknown",fmt(w.ok),fmt(w.failed),rate===null?"—":(rate*100).toFixed(1)+"%",rate===null?"No data":rate>=.9?"Operational":rate>=.7?"Degraded":"Error"].forEach((v,i)=>{const td=document.createElement("td");td.textContent=v;if(i>0)td.style.textAlign="right";tr.appendChild(td);});tbody.appendChild(tr);
    });
    const total=ok+failed; set("kpiWorkerSuccess",total?((ok/total)*100).toFixed(1)+"%":"N/A"); set("kpiWorkerSub",list.length+" workers observed");
  }
  function renderUnsupported(){ const tbody=el("fingerprintsTbody");if(!tbody)return;tbody.replaceChildren();const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=4;td.className="ls-empty";td.textContent="Frequent-error fingerprints are not exposed by the current Workstream B query contract.";tr.appendChild(td);tbody.appendChild(tr); }
  window.onLogsiteAuthStateChanged?window.onLogsiteAuthStateChanged(u=>{if(u)load();}):load();
})();
