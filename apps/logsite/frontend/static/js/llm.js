/** SentinelScan Log Site — Gemini usage using Workstream B's exact response shape. */
(function(){
  const COST_PER_MILLION_TOKENS_ESTIMATE=0; // UI-only placeholder; update when an approved pricing basis is chosen.
  const el=id=>document.getElementById(id), set=(id,v)=>{const e=el(id);if(e)e.textContent=v;}, fmt=n=>Number(n||0).toLocaleString();
  async function load(){
    try{
      const group=el("groupBySelect")?.value||"day"; const d=await window.apiFetch("/api/llm-usage",{group_by:group});
      set("kpiTotalTokens",fmt(d.total_tokens)); set("kpiTokenSplit",`${fmt(d.prompt_tokens)} prompt · ${fmt(d.response_tokens)} response`); set("kpiCalls",fmt(d.calls));
      const rate=d.calls?((Number(d.cache_hits||0)/d.calls)*100):null; set("kpiCacheRate",rate===null?"N/A":rate.toFixed(1)+"%"); set("kpiCacheSub",`${fmt(d.cache_hits)} cached calls`);
      set("kpiAvgTokens",d.calls?Math.round(d.total_tokens/d.calls).toLocaleString():"N/A");
      set("kpiCost",COST_PER_MILLION_TOKENS_ESTIMATE>0?"Estimated $"+((d.total_tokens/1e6)*COST_PER_MILLION_TOKENS_ESTIMATE).toFixed(4):"N/A");
      renderChart(Array.isArray(d.buckets)?d.buckets:[]); renderUnsupported(); set("llmLastRefreshed","Last refreshed "+new Date().toLocaleTimeString());
    }catch(e){console.error("LLM usage load error",e);}
  }
  function renderChart(buckets){ const root=el("usageChart");if(!root)return;root.replaceChildren();if(!buckets.length){const d=document.createElement("div");d.className="ls-empty";d.textContent="No Gemini usage recorded yet.";root.appendChild(d);return;}const max=Math.max(...buckets.map(b=>Number(b.tokens||0)),1);buckets.forEach(b=>{const row=document.createElement("div");row.style.cssText="display:grid;grid-template-columns:110px 1fr 90px;gap:10px;align-items:center;margin:8px 0";const label=document.createElement("span");label.textContent=b.bucket||"—";const track=document.createElement("div");track.className="progress-track";const fill=document.createElement("span");fill.className="progress-fill";fill.style.width=((Number(b.tokens||0)/max)*100)+"%";track.appendChild(fill);const val=document.createElement("span");val.textContent=fmt(b.tokens);val.style.textAlign="right";row.append(label,track,val);root.appendChild(row);}); }
  function renderUnsupported(){const tbody=el("expensiveScansTbody");if(!tbody)return;tbody.replaceChildren();const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=6;td.className="ls-empty";td.textContent="Per-scan Gemini cost breakdown is not exposed by the current query contract.";tr.appendChild(td);tbody.appendChild(tr);}
  el("groupBySelect")?.addEventListener("change",load); window.onLogsiteAuthStateChanged?window.onLogsiteAuthStateChanged(u=>{if(u)load();}):load();
})();
