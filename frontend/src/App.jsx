import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowUpRight, BriefcaseBusiness, Check, ChevronRight, CircleHelp, FileText, LayoutDashboard, MapPin, Search, Settings2, ShieldCheck, UploadCloud, X } from "lucide-react";

const platforms = [
  { id:"linkedin", name:"LinkedIn", detail:"Professional roles and company listings", search:"Not connected", apply:"Manual" },
  { id:"indeed", name:"Indeed", detail:"Broad employer and aggregator listings", search:"Not connected", apply:"Manual" },
  { id:"glassdoor", name:"Glassdoor", detail:"Jobs with company and workplace context", search:"Not connected", apply:"Manual" },
  { id:"ziprecruiter", name:"ZipRecruiter", detail:"Recruiter and employer listings", search:"Not connected", apply:"Manual" },
  { id:"dice", name:"Dice", detail:"Technology-focused opportunities", search:"Not connected", apply:"Manual" },
  { id:"wellfound", name:"Wellfound", detail:"Startup and growth-company roles", search:"Not connected", apply:"Manual" },
  { id:"career", name:"Company career pages", detail:"Employer-owned career sites and ATS portals", search:"ATS-dependent", apply:"Manual" },
  { id:"other", name:"Other supported portals", detail:"Additional sources when an approved connection exists", search:"Not connected", apply:"Manual" }
];
const defaults = { role:"Software Engineer, Java Developer, Backend Engineer, SDET", country:"United States", location:"", work:["Remote","Nationwide"], experience:"Early career / 1–3 years" };
const API_BASE = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? "" : "http://localhost:8000");
const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };

export default function App() {
  const [selected,setSelected] = useState(() => read("nova-platforms", platforms.map(p=>p.id)));
  const [prefs,setPrefs] = useState(() => { const saved = read("nova-preferences", defaults); return { ...defaults, ...saved, country: "United States" }; });
  const [resume,setResume] = useState(null);
  const [active,setActive] = useState("Overview");
  const [saved,setSaved] = useState(false);
  const [notice,setNotice] = useState("");
  const [apiStatus,setApiStatus] = useState("checking");
  const [apiMessage,setApiMessage] = useState("Checking Nova API");
  const [platformCatalog,setPlatformCatalog] = useState([]);
  const [backendConfig,setBackendConfig] = useState(null);
  const [searchLoading,setSearchLoading] = useState(false);
  const [searchResults,setSearchResults] = useState([]);
  const [searchMessage,setSearchMessage] = useState("");
  const [searchSources,setSearchSources] = useState([]);
  const [verificationById,setVerificationById] = useState({});
  const [verifyingId,setVerifyingId] = useState("");
  const [pilotJob,setPilotJob] = useState(null);
  const [pilotSubmitted,setPilotSubmitted] = useState(false);
  const [recruiterEmail,setRecruiterEmail] = useState("");
  const [recruiterProfile,setRecruiterProfile] = useState("");
  const [recruiterCheck,setRecruiterCheck] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    async function connectApi() {
      try {
        const [healthResponse, platformResponse, configResponse] = await Promise.all([
          fetch(`${API_BASE}/health`, { signal: controller.signal }),
          fetch(`${API_BASE}/api/v1/platforms`, { signal: controller.signal }),
          fetch(`${API_BASE}/api/v1/config`, { signal: controller.signal })
        ]);
        if (!healthResponse.ok || !platformResponse.ok || !configResponse.ok) throw new Error("API returned an unsuccessful response");
        const [health, catalog, config] = await Promise.all([healthResponse.json(), platformResponse.json(), configResponse.json()]);
        setPlatformCatalog(Array.isArray(catalog.platforms) ? catalog.platforms : []);
        setBackendConfig(config);
        setApiStatus("connected");
        setApiMessage(`API connected · ${health.status || "healthy"}`);
      } catch (error) {
        if (error.name === "AbortError") return;
        setApiStatus("offline");
        setApiMessage("API unavailable · Start the FastAPI service to connect");
      }
    }
    connectApi();
    return () => controller.abort();
  }, []);
  useEffect(()=>localStorage.setItem("nova-platforms",JSON.stringify(selected)),[selected]);
  useEffect(()=>localStorage.setItem("nova-preferences",JSON.stringify(prefs)),[prefs]);
  const chosen = useMemo(()=>platforms.filter(p=>selected.includes(p.id)),[selected]);
  const platformView = platforms.map(p => {
    const remote = platformCatalog.find(item => item.id === p.id);
    return remote ? { ...p, search: remote.search, apply: remote.application } : p;
  });
  const toggle = id => { setSelected(s=>s.includes(id)?s.filter(x=>x!==id):[...s,id]); setSaved(false); };
  const toggleWork = v => setPrefs(p=>({...p,work:p.work.includes(v)?p.work.filter(x=>x!==v):[...p.work,v]}));
  const runJobSearch = async () => {
    if (!resume) {
      setSearchResults([]);
      setSearchMessage("Select your resume first to unlock job discovery. Your file remains in this browser and is not uploaded or analyzed by Nova yet.");
      return;
    }
    if (!selected.includes("career")) {
      setSearchResults([]);
      setSearchMessage("Select Company career pages above to search configured public company boards.");
      return;
    }
    setSearchLoading(true);
    setSearchMessage("");
    try {
      const response = await fetch(`${API_BASE}/api/v1/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: prefs.role, location: prefs.country, limit: 60 })
      });
      if (!response.ok) throw new Error(`Search service returned ${response.status}`);
      const data = await response.json();
      setSearchResults(data.jobs || []);
      setVerificationById({});
      setPilotJob(null);
      setPilotSubmitted(false);
      setSearchSources(data.sources_checked || []);
      setSearchMessage(data.message || "Search complete.");
    } catch (error) {
      setSearchMessage(`Could not search company boards. ${error.message}. Check the API connection.`);
    } finally {
      setSearchLoading(false);
    }
  };
  const verifyJob = async job => {
    setVerifyingId(job.id);
    try {
      const response = await fetch(`${API_BASE}/api/v1/verify-job`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: job.id, url: job.url, title: job.title, company: job.company })
      });
      if (!response.ok) throw new Error(`Verification service returned ${response.status}`);
      const report = await response.json();
      setVerificationById(current => ({ ...current, [job.id]: report }));
    } catch (error) {
      setVerificationById(current => ({ ...current, [job.id]: { status: "Needs review", risk_level: "medium", summary: `Nova could not complete the live verification check: ${error.message}`, checks: [], warnings: ["Do not proceed until you manually confirm this exact role on the employer's official careers page."], apply_url: null } }));
    } finally {
      setVerifyingId("");
    }
  };
  const beginPilot = job => {
    const report = verificationById[job.id];
    if (!report?.apply_url || !["low","medium"].includes(report?.risk_level)) return;
    window.open(report.apply_url, "_blank", "noopener,noreferrer");
    setPilotJob(job);
    setPilotSubmitted(false);
    setRecruiterEmail("");
    setRecruiterProfile("");
    setRecruiterCheck(null);
  };
  const checkRecruiter = () => {
    if (!pilotJob) return;
    const domain = verificationById[pilotJob.id]?.official_domain || "";
    const email = recruiterEmail.trim().toLowerCase();
    const emailDomain = email.includes("@") ? email.split("@").pop() : "";
    const freeDomains = ["gmail.com","outlook.com","hotmail.com","yahoo.com","icloud.com","aol.com"];
    let emailStatus = "review";
    let emailDetail = "No recruiter email was supplied. Verify the contact through the employer's official website.";
    if (email) {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        emailStatus = "fail";
        emailDetail = "This does not look like a valid email address.";
      } else if (domain && (emailDomain === domain || emailDomain.endsWith("." + domain))) {
        emailStatus = "pass";
        emailDetail = "The email domain matches the curated company domain " + domain + ". This does not prove who controls the mailbox.";
      } else if (freeDomains.includes(emailDomain)) {
        emailStatus = "fail";
        emailDetail = "This is a personal email provider, not the company's registered domain. Treat the recruiter as unverified.";
      } else {
        emailStatus = "review";
        emailDetail = "The email domain does not match the company's registered domain. It may be an agency, but verify that relationship independently.";
      }
    }
    let profileStatus = "review";
    let profileDetail = "No profile link was supplied. Find the recruiter through the company's official website.";
    if (recruiterProfile.trim()) {
      try {
        const profileUrl = new URL(recruiterProfile.trim());
        const validHost = profileUrl.protocol === "https:" && ["linkedin.com","www.linkedin.com"].includes(profileUrl.hostname.toLowerCase());
        const validPath = /^\/(in|company)\//.test(profileUrl.pathname);
        if (validHost && validPath) {
          profileStatus = "review";
          profileDetail = "The link uses a LinkedIn profile/company URL format. Nova cannot confirm the profile owner, employment, or authenticity.";
        } else {
          profileStatus = "fail";
          profileDetail = "The link is not a standard HTTPS LinkedIn profile/company URL. Do not rely on it without independent confirmation.";
        }
      } catch {
        profileStatus = "fail";
        profileDetail = "The profile link is not a valid URL.";
      }
    }
    setRecruiterCheck({ emailStatus, emailDetail, profileStatus, profileDetail });
  };
  const onFile = e => { const f=e.target.files?.[0]; if(!f)return; const ok=/\.(pdf|doc|docx)$/i.test(f.name); if(!ok){setNotice("Please choose a PDF, DOC, or DOCX file.");return;} if(f.size>10*1024*1024){setNotice("Please choose a file smaller than 10 MB.");return;} setResume({name:f.name,size:(f.size/1024/1024).toFixed(2)+" MB"}); setNotice("Resume selected in this browser only. It has not been uploaded."); };
  const nav = [{name:"Overview",icon:LayoutDashboard},{name:"Resume",icon:FileText},{name:"Job platforms",icon:BriefcaseBusiness},{name:"Preferences",icon:Settings2}];
  return <div className="shell">
    <aside className="sidebar"><a className="brand" href="#"><span className="brand-mark">N</span><span>nova<span className="brand-dot">.</span><small>CAREER INTELLIGENCE</small></span></a><div className="workspace-label">WORKSPACE</div><nav>{nav.map(({name,icon:Icon})=><button key={name} className={active===name?"nav-item active":"nav-item"} onClick={()=>{setActive(name);document.getElementById(name.toLowerCase().replace(" ","-"))?.scrollIntoView({behavior:"smooth"});}}><Icon size={17}/>{name}<ChevronRight size={15}/></button>)}</nav><div className="sidebar-bottom"><div className="secure-icon"><ShieldCheck size={18}/></div><strong>Your search, your control</strong><p>Review every opportunity before you take action.</p><span className="local-tag"><span/> Browser preview</span></div></aside>
    <main className="main"><header className="topbar"><div><span className="eyebrow">CAREER WORKSPACE</span><h1>Find your next opportunity.</h1><p>Bring your experience and goals together in one focused search space.</p></div><div className="topbar-actions"><span className={`api-status ${apiStatus}`} title={apiMessage}><i/>{apiStatus==="checking"?"Checking API":apiStatus==="connected"?"API connected":"API offline"}</span><div className="avatar">N</div></div></header>
      <section className="hero"><div className="hero-copy"><span className="pill"><Activity size={13}/> YOUR CAREER, IN FOCUS</span><h2>Make your next move<br/><em>with confidence.</em></h2><p>Set your direction, choose where Nova should look, and keep your applications organized.</p><button className="primary" onClick={()=>{setActive("Job platforms");document.getElementById("job-platforms").scrollIntoView({behavior:"smooth"});}}>Configure job sources <ArrowUpRight size={16}/></button></div><div className="hero-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit-core"><Search size={35}/></div><div className="float-card fc-one"><span className="mini-icon"><BriefcaseBusiness size={15}/></span><span><b>Role matching</b><small>Preference-led</small></span></div><div className="float-card fc-two"><span className="mini-check"><Check size={15}/></span><span><b>You stay in control</b><small>Review before applying</small></span></div></div></section>
      <section className="stats"><div className="stat"><span>Selected platforms</span><b>{selected.length}<small> / 8</small></b><p>Sources in your workspace</p></div><div className="stat"><span>Resume</span><b className="stat-word">{resume?"Added":"Not added"}</b><p>{resume?resume.name:"Upload to prepare your profile"}</p></div><div className="stat"><span>Selected job market</span><b className="stat-word">{prefs.country || "United States"}</b><p>Country-specific listings</p></div></section>
      <section className="content-grid"><div className="panel resume-panel" id="resume"><div className="section-head"><div><span className="eyebrow">STEP 02</span><h3>Your resume</h3><p>Start with the experience you want employers to see.</p></div><FileText size={20}/></div><label className="upload-zone"><input type="file" accept=".pdf,.doc,.docx" onChange={onFile}/><span className="upload-icon"><UploadCloud size={22}/></span><b>{resume?"Choose a different resume":"Upload your resume"}</b><span>PDF, DOC or DOCX · up to 10 MB</span><small>Click to browse files</small></label>{resume&&<div className="file-row"><FileText size={17}/><span><b>{resume.name}</b><small>{resume.size} · Selected locally</small></span><button aria-label="Remove resume" onClick={()=>setResume(null)}><X size={16}/></button></div>}<p className="privacy-note"><ShieldCheck size={14}/> Preview only: the file stays on your device and is not uploaded or analyzed yet.</p>{notice&&<p className="notice">{notice}</p>}</div>
      <div className="panel preferences-panel" id="preferences"><div className="section-head"><div><span className="eyebrow">STEP 03</span><h3>Search preferences</h3><p>Tell Nova what a good next role looks like.</p></div><MapPin size={20}/></div><label className="field-label">TARGET ROLES</label><textarea value={prefs.role} onChange={e=>setPrefs(p=>({...p,role:e.target.value}))} rows="3"/><label className="field-label">COUNTRY / JOB MARKET</label><select value={prefs.country || "United States"} onChange={e=>setPrefs(p=>({...p,country:e.target.value,location:""}))}><option value="United States">United States</option></select><label className="field-label">CITY / REGION (OPTIONAL)</label><input value={prefs.location} placeholder="e.g. Dallas, TX, Seattle, CA" onChange={e=>setPrefs(p=>({...p,location:e.target.value}))}/><label className="field-label">WORK SETUP</label><div className="chips">{["Remote","Nationwide","Hybrid","On-site"].map(v=><button key={v} className={prefs.work.includes(v)?"chip selected":"chip"} onClick={()=>toggleWork(v)}>{prefs.work.includes(v)&&<Check size={13}/>} {v}</button>)}</div><label className="field-label">EXPERIENCE LEVEL</label><select value={prefs.experience} onChange={e=>setPrefs(p=>({...p,experience:e.target.value}))}><option>Entry level</option><option>Early career / 1–3 years</option><option>Mid-level / 3–5 years</option><option>Senior</option><option>Open to matching roles</option></select></div></section>
      <section className="panel platforms-panel" id="job-platforms"><div className="section-head platform-heading"><div><span className="eyebrow">STEP 04</span><h3>Choose your job platforms</h3><p>Select each source individually. Your choices are saved in this browser.</p></div><span className="selected-count">{selected.length} SELECTED</span></div><div className="platform-list">{platformView.map(p=><label key={p.id} className={selected.includes(p.id)?"platform-row chosen":"platform-row"}><input className="platform-checkbox" type="checkbox" checked={selected.includes(p.id)} onChange={()=>toggle(p.id)}/><span className="platform-copy"><span className="platform-name">{p.name}</span><span className="platform-detail">{p.detail}</span></span><span className="platform-capability"><small>SEARCH</small><b className={p.search==="ATS-dependent"?"muted":""}>{p.search}</b></span><span className="platform-capability"><small>APPLICATION</small><b>{p.apply}</b></span></label>)}</div><div className="platform-footnote"><CircleHelp size={15}/><span>Capability labels reflect the current MVP. Greenhouse and Lever discovery works only for employer boards configured on the backend; other job boards are not connected. Applications remain manual. Nova will not bypass site restrictions or submit applications without your explicit authorization.</span></div><div className="save-row"><span>{saved?"Preferences saved in this browser.":"Changes are saved locally as you make them."}</span><button className="secondary" onClick={()=>{localStorage.setItem("nova-platforms",JSON.stringify(selected));localStorage.setItem("nova-preferences",JSON.stringify(prefs));setSaved(true);}}>Save preferences <Check size={15}/></button></div></section>
      <section className="panel search-panel" id="job-search"><div className="section-head"><div><span className="eyebrow">STEP 05</span><h3>Discover matching jobs</h3><p>Search published United States roles from company boards configured by Nova.</p></div><Search size={20}/></div><div className="search-action-row"><div><b>Company career pages</b><span>Greenhouse and Lever public listings · {backendConfig?.configured_public_boards ?? 0} configured boards</span></div><button className="primary" onClick={runJobSearch} disabled={!resume || searchLoading || apiStatus!=="connected" || !(backendConfig?.configured_public_boards>0)}>{searchLoading?"Searching…":"Search configured boards"} <ArrowUpRight size={15}/></button></div>{!resume&&<p className="search-message">Upload/select your resume above to unlock job discovery. Your file stays in this browser. Resume parsing and resume-based matching are not enabled yet.</p>}{apiStatus==="connected" && !(backendConfig?.configured_public_boards>0) && <p className="search-message">The API is connected, but no employer boards are configured yet. Add approved Greenhouse board tokens or Lever site names to the backend environment, then restart the API.</p>}{searchMessage&&<p className="search-message">{searchMessage}</p>}{searchSources.length>0&&<div className="source-status">{searchSources.map((s,i)=><span key={i} className={s.status==="ok"?"source-ok":"source-error"}>{s.provider}: {s.status==="ok"?`${s.count} matches`:"unavailable"}</span>)}</div>}{searchResults.length>0&&<div className="job-results">{searchResults.map(job=><article className="job-result" key={job.id}><div className="job-result-main"><h4>{job.title}</h4><p>{job.company} · {job.location || "Location not listed"} · {job.source}</p><span>{job.description}</span>{verificationById[job.id]&&<div className={`verification-result ${verificationById[job.id].risk_level}`}><b>{verificationById[job.id].status}</b><p>{verificationById[job.id].summary}</p><ul>{(verificationById[job.id].checks||[]).map((check,i)=><li key={i}><strong>{check.name}:</strong> {check.detail}</li>)}</ul>{(verificationById[job.id].warnings||[]).map((warning,i)=><small key={i}>• {warning}</small>)}</div>}</div><div className="job-result-actions">{!verificationById[job.id]&&<button className="secondary" onClick={()=>verifyJob(job)} disabled={verifyingId===job.id}>{verifyingId===job.id?"Checking…":"Verify authenticity"}</button>}{["low","medium"].includes(verificationById[job.id]?.risk_level)&&verificationById[job.id]?.apply_url&&<button className="primary" onClick={()=>beginPilot(job)}>Start pilot application <ArrowUpRight size={13}/></button>}{verificationById[job.id]?.risk_level==="medium"&&<span className="review-lock">Manual review required</span>}{verificationById[job.id]?.risk_level==="high"&&<span className="risk-lock">Do not apply</span>}</div></article>)}</div>}<p className="privacy-note"><ShieldCheck size={14}/> Nova rechecks the exact job ID against the live public employer feed before enabling the pilot. A source check cannot guarantee a recruiter is genuine. Resume files stay in your browser; upload them directly to the employer only after your review.</p>{pilotJob&&<div className="pilot-panel"><div className="section-head"><div><span className="eyebrow">CONTROLLED PILOT</span><h3>One-application review</h3><p>{pilotJob.title} · {pilotJob.company}</p></div><span className="pilot-tag">Verified source</span></div><ol><li>Confirm the role and location on the employer's official application page.</li><li>Check recruiter communication and contact details before sharing personal information.</li><li>Upload your resume directly to the employer's portal, not to Nova.</li><li>Review every answer, especially work authorization and sponsorship, before submitting.</li></ol><div className="recruiter-check"><h4>Recruiter identity screening</h4><p>Optional: check whether the recruiter email matches the employer domain and whether the profile link uses LinkedIn. These checks are signals, not proof of identity.</p><label>Recruiter email<input type="email" value={recruiterEmail} onChange={e=>{setRecruiterEmail(e.target.value);setRecruiterCheck(null);}} placeholder="name@company.com"/></label><label>Recruiter profile URL<input type="url" value={recruiterProfile} onChange={e=>{setRecruiterProfile(e.target.value);setRecruiterCheck(null);}} placeholder="https://www.linkedin.com/in/..."/></label><button className="secondary" onClick={checkRecruiter}>Check recruiter details</button>{recruiterCheck&&<div className="recruiter-results"><p className={recruiterCheck.emailStatus}><b>Email:</b> {recruiterCheck.emailDetail}</p><p className={recruiterCheck.profileStatus}><b>Profile:</b> {recruiterCheck.profileDetail}</p></div>}</div><div className="pilot-actions"><a className="primary" href={verificationById[pilotJob.id]?.apply_url} target="_blank" rel="noreferrer">Open verified application <ArrowUpRight size={14}/></a><button className="secondary" onClick={()=>{setPilotJob(null);setPilotSubmitted(false);}}>Close pilot</button></div>{pilotSubmitted?<p className="pilot-confirm">Marked as submitted by you. Nova did not submit the application or verify the employer's receipt.</p>:<button className="pilot-complete" onClick={()=>setPilotSubmitted(true)}>I submitted this application on the employer's website</button>}</div>}</section>
      <footer><span>nova<span className="brand-dot">.</span> <small>CAREER INTELLIGENCE</small></span><span>Built around your goals. Always in your control.</span></footer>
    </main>
  </div>;
}
