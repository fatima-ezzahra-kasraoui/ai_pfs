import { useState } from "react";
import { User, Monitor, ShieldCheck, Settings as SettingsIcon, ChevronRight, Lock, Sun, Moon, Laptop } from "lucide-react";
import { AsyncView } from "../components/AsyncView";
import { useAsync } from "../hooks";
import { applyTheme, loadTheme, saveTheme, type Theme } from "../preferences";
import { authService, policyService } from "../services/api";
import "./Settings.css";

const SECRET_KEY = /key|secret|token|password|passwd|credential|canary/i;

/** Remplace toute valeur dont la clé évoque un secret : la page n'affiche jamais de secret. */
export function redact(value: unknown, key = ""): unknown {
  if (SECRET_KEY.test(key)) return Array.isArray(value) ? `•••• (${value.length} valeur(s) masquée(s))` : "••••";
  if (Array.isArray(value)) return value.map((v) => redact(v));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, redact(v, k)]));
  return value;
}

function Tree({ data }: { data: unknown }) {
  if (data && typeof data === "object" && !Array.isArray(data)) {
    return <div className="settings-tree">{Object.entries(data).map(([k,v]) => v && typeof v === "object" && !Array.isArray(v) ? <div className="settings-branch" key={k}><h4>{k.replace(/_/g," ")}</h4><Tree data={v}/></div> : <div className="settings-value" key={k}><code>{k}</code><span><Tree data={v}/></span></div>)}</div>;
  }
  return <>{Array.isArray(data) ? data.map(v => typeof v === "object" ? JSON.stringify(v) : String(v)).join(", ") : String(data)}</>;
}
const sections = [{id:"profile",label:"Profil",description:"Compte et identité",Icon:User},{id:"appearance",label:"Apparence",description:"Préférences visuelles",Icon:Monitor},{id:"platform",label:"Plateforme",description:"Informations système",Icon:SettingsIcon},{id:"security",label:"Sécurité",description:"Politiques actives",Icon:ShieldCheck}];
export default function Settings() {
  const me = useAsync(s => authService.me(s));
  const policy = useAsync(s => policyService.get(s));
  const [theme,setTheme] = useState<Theme>(loadTheme);
  const [active,setActive] = useState("profile");
  const onTheme = (t:Theme) => {setTheme(t);saveTheme(t);applyTheme(t);};
  return <section className="settings-page">
    <header className="settings-heading"><div className="settings-eyebrow">ADMINISTRATION <ChevronRight size={12}/> SETTINGS</div><h1>Paramètres</h1><p>Gérez votre compte, votre espace de travail et vos préférences de sécurité.</p></header>
    <div className="settings-layout"><nav className="settings-nav" aria-label="Navigation des paramètres"><div className="settings-nav-label">ESPACE DE TRAVAIL</div>{sections.map(({id,label,description,Icon})=><a key={id} href={`#settings-${id}`} className={active===id?"selected":""} onClick={()=>setActive(id)}><Icon size={19}/><span><strong>{label}</strong><small>{description}</small></span><ChevronRight size={14}/></a>)}</nav>
    <div className="settings-content">
      <section id="settings-profile" className="settings-panel" aria-label="Profil"><div className="settings-panel-head"><User size={20}/><div><h2>Profil</h2><p>Informations associées à votre compte.</p></div></div><AsyncView state={me.state} onRetry={me.reload}>{u=><><div className="settings-identity"><div className="settings-avatar">{u.username.slice(0,2).toUpperCase()}</div><div><strong>Compte AgentShield AI</strong><small>Profil utilisateur</small></div><span className="settings-tag">{u.role}</span></div><div className="settings-fields"><div><span>Identifiant</span><strong>{u.username}</strong></div>{u.email&&<div><span>Adresse e-mail</span><strong>{u.email}</strong></div>}</div></>}</AsyncView></section>
      <section id="settings-appearance" className="settings-panel" aria-label="Préférences d'interface"><div className="settings-panel-head"><Monitor size={20}/><div><h2>Apparence</h2><p>Personnalisez le thème de votre interface.</p></div></div><div className="settings-themes">{([{id:"light",label:"Clair",Icon:Sun},{id:"dark",label:"Sombre",Icon:Moon},{id:"system",label:"Système",Icon:Laptop}] as const).map(({id,label,Icon})=><button key={id} type="button" aria-pressed={theme===id} className={`settings-theme ${theme===id?"selected":""}`} onClick={()=>onTheme(id)}><span className={`settings-preview ${id}`}><i/><b><em/><em/><em/></b></span><span className="settings-theme-label"><Icon size={15}/>{label}<span className="settings-radio"/></span></button>)}</div><div className="settings-select"><label htmlFor="theme">Thème</label><select id="theme" value={theme} onChange={e=>onTheme(e.target.value as Theme)}><option value="system">Système</option><option value="light">Clair</option><option value="dark">Sombre</option></select></div></section>
      <section id="settings-platform" className="settings-panel" aria-label="Plateforme"><div className="settings-panel-head"><SettingsIcon size={20}/><div><h2>Plateforme</h2><p>Informations générales de votre environnement.</p></div></div><div className="settings-fields"><div><span>Application</span><strong>AgentShield AI</strong></div><div><span>Configuration</span><strong>Gérée côté serveur</strong></div></div></section>
      <section id="settings-security" className="settings-panel" aria-label="Politiques en vigueur"><div className="settings-panel-head"><ShieldCheck size={20}/><div><h2>Politiques en vigueur</h2><p>Configuration de sécurité effective du serveur.</p></div><span className="settings-tag"><Lock size={12}/> Lecture seule</span></div><div className="settings-notice"><Lock size={16}/><span>Les politiques sont définies côté serveur. Les valeurs sensibles sont masquées.</span></div><AsyncView state={policy.state} onRetry={policy.reload} isEmpty={p=>Object.keys(p).length===0} emptyMessage="Aucune politique à afficher.">{p=><Tree data={redact(p)}/>}</AsyncView></section>
    </div></div></section>;
}
