import { useEffect, useMemo, useState } from "react";
import { Activity, CalendarDays, ChevronDown, Plus, RefreshCw, Trash2 } from "lucide-react";

const STATUSES = ["Applied", "Pending", "Responded", "Interview", "Rejected", "Offer", "Withdrawn"];
const freshDraft = () => ({ company:"", role:"", status:"Applied", platform:"Manual", job_url:"", applied_date:new Date().toISOString().slice(0,10), follow_up_date:"", interview_date:"", notes:"" });

export default function ApplicationDashboard({ apiBase, workspaceId }) {
  const [items,setItems] = useState([]);
  const [loading,setLoading] = useState(false);
  const [error,setError] = useState("");
  const [expanded,setExpanded] = useState(false);
  const [showForm,setShowForm] = useState(false);
  const [filter,setFilter] = useState("All");
  const [period,setPeriod] = useState("All time");
  const [draft,setDraft] = useState(freshDraft);
  const base = apiBase + "/api/v1/applications";
  const load = async () => {
    setLoading(true);
    try {
      const r=await fetch(base+"?workspace_id="+encodeURIComponent(workspaceId));
      if(!r.ok) throw new Error("Could not load saved applications ("+r.status+").");
      const data=await r.json(); setItems(data.applications||[]); setError("");
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  };
  useEffect(()=>{load(); const refresh=()=>load(); window.addEventListener("nova-applications-updated",refresh); return ()=>window.removeEventListener("nova-applications-updated",refresh);},[workspaceId]);
  const scoped = useMemo(()=>{
    if(period==="All time") return items;
    const days=period==="7 days"?7:period==="30 days"?30:90;
    const cutoff=new Date(Date.now()-days*86400000);
    return items.filter(x=>!x.applied_date || new Date(x.applied_date)>=cutoff);
  },[items,period]);
  const counts = {
    total:scoped.length,
    applied:scoped.filter(x=>x.status==="Applied").length,
    pending:scoped.filter(x=>x.status==="Pending").length,
    responded:scoped.filter(x=>["Responded","Interview","Offer"].includes(x.status)).length,
    rejected:scoped.filter(x=>x.status==="Rejected").length
  };
  const visible=scoped.filter(x=>filter==="All"||(filter==="Responded"?["Responded","Interview","Offer"].includes(x.status):x.status===filter));
  const save = async e => {
    e.preventDefault();
    try {
      const payload={...draft,job_url:draft.job_url||null,follow_up_date:draft.follow_up_date||null,interview_date:draft.interview_date||null};
      const r=await fetch(base+"?workspace_id="+encodeURIComponent(workspaceId),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      if(!r.ok) throw new Error("Could not save application ("+r.status+").");
      const created=await r.json(); setItems(v=>[created,...v]); setDraft(freshDraft()); setShowForm(false); setError("");
    } catch(e) { setError(e.message); }
  };
  const updateStatus = async (item,status) => {
    try {
      const r=await fetch(base+"/"+item.id+"?workspace_id="+encodeURIComponent(workspaceId),{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({...item,status})});
      if(!r.ok) throw new Error("Could not update status.");
      const updated=await r.json(); setItems(v=>v.map(x=>x.id===updated.id?updated:x));
    } catch(e) { setError(e.message); }
  };
  const remove = async item => {
    if(!window.confirm("Delete the application for "+item.company+"?")) return;
    try {
      const r=await fetch(base+"/"+item.id+"?workspace_id="+encodeURIComponent(workspaceId),{method:"DELETE"});
      if(!r.ok) throw new Error("Could not delete application.");
      setItems(v=>v.filter(x=>x.id!==item.id));
    } catch(e) { setError(e.message); }
  };
  return <section className="application-dashboard" id="applications">
    <div className="section-head">
      <div><span className="eyebrow">YOUR ACTIVITY</span><h3>Application dashboard</h3><p>Track your applications and see how your search is progressing.</p><p className="dashboard-privacy">Workspace separation is browser-based at this stage; account login and secure per-user authentication are not yet implemented.</p></div>
      <button className="primary" onClick={()=>setShowForm(v=>!v)}><Plus size={15}/>{showForm?"Close form":"Add application"}</button>
    </div>
    <div className="dashboard-toolbar"><span><CalendarDays size={14}/> Activity period</span><select value={period} onChange={e=>setPeriod(e.target.value)}><option>All time</option><option>7 days</option><option>30 days</option><option>90 days</option></select><button className="secondary" onClick={load} disabled={loading}><RefreshCw size={13}/>{loading?"Refreshing":"Refresh"}</button></div>
    <div className="application-metrics">
      <button className={filter==="All"?"metric-card selected":"metric-card"} onClick={()=>setFilter("All")}><small>TOTAL APPLICATIONS</small><b>{counts.total}</b><span>All tracked records</span></button>
      <button className={filter==="Applied"?"metric-card selected":"metric-card"} onClick={()=>setFilter("Applied")}><small>APPLIED</small><b>{counts.applied}</b><span>Marked submitted by you</span></button>
      <button className={filter==="Pending"?"metric-card selected":"metric-card"} onClick={()=>setFilter("Pending")}><small>PENDING</small><b>{counts.pending}</b><span>Awaiting an update</span></button>
      <button className={filter==="Responded"?"metric-card selected":"metric-card"} onClick={()=>setFilter("Responded")}><small>RESPONDED / INTERVIEW</small><b>{counts.responded}</b><span>Employer response recorded</span></button>
      <button className={filter==="Rejected"?"metric-card selected":"metric-card"} onClick={()=>setFilter("Rejected")}><small>REJECTED</small><b>{counts.rejected}</b><span>Closed applications</span></button>
    </div>
    <div className="dashboard-insights">
      <div className="insight-card"><div className="insight-title">Status distribution</div>{["Applied","Pending","Responded","Interview","Rejected","Offer"].map(status=>{const n=scoped.filter(x=>x.status===status).length;const pct=counts.total?Math.round(n/counts.total*100):0;return <div className="distribution-row" key={status}><span>{status}</span><div><i style={{width:pct+"%"}}/></div><b>{n}</b></div>})}</div>
      <div className="insight-card"><div className="insight-title">Search activity</div><strong className="insight-number">{counts.total}</strong><p>applications recorded in the selected period</p><span className="insight-hint">Counts update when you add or change an application.</span></div>
    </div>
    {showForm&&<form className="application-form" onSubmit={save}><div className="insight-title">Add an application</div><div className="application-form-grid">
      <label>Company<input required value={draft.company} onChange={e=>setDraft(v=>({...v,company:e.target.value}))} placeholder="Company name"/></label>
      <label>Role<input required value={draft.role} onChange={e=>setDraft(v=>({...v,role:e.target.value}))} placeholder="Job title"/></label>
      <label>Status<select value={draft.status} onChange={e=>setDraft(v=>({...v,status:e.target.value}))}>{STATUSES.map(x=><option key={x}>{x}</option>)}</select></label>
      <label>Platform<input value={draft.platform} onChange={e=>setDraft(v=>({...v,platform:e.target.value}))} placeholder="LinkedIn, company site…"/></label>
      <label>Application date<input type="date" value={draft.applied_date} onChange={e=>setDraft(v=>({...v,applied_date:e.target.value||null}))}/></label>
      <label>Follow-up date<input type="date" value={draft.follow_up_date} onChange={e=>setDraft(v=>({...v,follow_up_date:e.target.value}))}/></label>
      <label>Interview date<input type="date" value={draft.interview_date} onChange={e=>setDraft(v=>({...v,interview_date:e.target.value}))}/></label>
      <label>Job URL<input type="url" value={draft.job_url} onChange={e=>setDraft(v=>({...v,job_url:e.target.value}))} placeholder="https://…"/></label>
      <label className="wide">Notes<textarea rows="2" value={draft.notes} onChange={e=>setDraft(v=>({...v,notes:e.target.value}))} placeholder="Recruiter notes, follow-up details, interview feedback…"/></label>
    </div><div className="application-form-actions"><button type="button" className="secondary" onClick={()=>setShowForm(false)}>Cancel</button><button type="submit" className="primary">Save application</button></div></form>}
    {error&&<p className="search-message">{error}</p>}
    <div className="tracker-header"><button className="tracker-toggle" onClick={()=>setExpanded(v=>!v)} aria-expanded={expanded}><ChevronDown className={expanded?"tracker-chevron open":"tracker-chevron"}/><span><b>Application Tracker</b><small>{visible.length} records · {filter==="All"?"All statuses":filter}</small></span></button><button className="secondary" onClick={()=>{setShowForm(true);setExpanded(true);}}><Plus size={14}/> Add</button></div>
    {expanded&&<div className="tracker-content"><div className="tracker-filter"><label>Filter status<select value={filter} onChange={e=>setFilter(e.target.value)}>{["All",...STATUSES].map(x=><option key={x} value={x}>{x==="All"?"All statuses":x}</option>)}</select></label></div>
      {!visible.length?<p className="empty-tracker">{loading?"Loading your applications…":"No applications yet. Add one to start tracking your progress."}</p>:<div className="tracker-table-wrap"><table className="tracker-table"><thead><tr><th>Company</th><th>Role</th><th>Status</th><th>Applied</th><th>Follow-up / interview</th><th>Platform & notes</th><th/></tr></thead><tbody>{visible.map(item=><tr key={item.id}><td data-label="Company"><b>{item.company}</b></td><td data-label="Role">{item.job_url?<a href={item.job_url} target="_blank" rel="noreferrer">{item.role}</a>:item.role}</td><td data-label="Status"><select className="status-select" value={item.status} onChange={e=>updateStatus(item,e.target.value)}>{STATUSES.map(x=><option key={x}>{x}</option>)}</select></td><td data-label="Applied">{item.applied_date||"—"}</td><td data-label="Dates">{item.follow_up_date||item.interview_date||"—"}</td><td data-label="Notes"><span>{item.platform}</span>{item.notes&&<small>{item.notes}</small>}</td><td><button className="icon-action" aria-label="Delete application" onClick={()=>remove(item)}><Trash2 size={15}/></button></td></tr>)}</tbody></table></div>}
    </div>}
  </section>;
}
