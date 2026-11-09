import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  Activity, AppWindow, ArrowRight, Blocks, Bot, BrainCircuit, BriefcaseBusiness, FolderKanban, MemoryStick,
  Check, CircleStop, Command, Eye, Gauge, Home, LockKeyhole, LogOut, Mic, MicOff, Monitor, RefreshCw,
  Search, Settings, ShieldCheck, Sparkles, TerminalSquare, Volume2, X, Zap
} from 'lucide-react';

const API = 'http://127.0.0.1:8765';

type View = 'home' | 'projects' | 'memory' | 'missions' | 'approvals' | 'agents' | 'skills' | 'computer' | 'commercial' | 'settings';
type AuthMode = 'login' | 'register' | 'verify' | 'forgot' | 'reset';
type AccountUser = { id: string; email: string; name: string; email_verified: boolean };
type AuthResult = { access_token: string; token_type: string; user: AccountUser };
type Pending = { id: string; kind: string; description: string; target: string; expires_at: number; fingerprint: string };
type EventItem = { id: number; kind: string; message: string; at: string };
type InstalledApp = { name: string; version: string; launchable?: boolean; source?: string; target_type?: string };
type MissionStep = { index: number; kind: string; description: string; status: string; target: string; result: string; action_id: string | null };
type Mission = { id: string; title: string; status: string; verification: string; steps: MissionStep[] };
type VoiceProfile = { assistant_name: string; language: string; background_listening_enabled: boolean; speak_on_startup: boolean; wake_enabled: boolean };
type Status = { microphone_on: boolean; model_installed: boolean; voice_synthesis_enabled: boolean; voice_provider: string; pending_approvals: number; mode: string; assistant_name?: string; wake_enabled?: boolean; background_listening_enabled?: boolean };
type Agent = { id: string; name: string; sector: string; description: string };
type Skill = { id: string; name: string; description: string; executable?: boolean; risk?: string; family?: string; stage?: string };
type BunoHealth = { reachable: boolean; bridge_mode: string; model_execution_enabled: boolean; message?: string };
type ProfessionalPlan = { objective: string; route: { agent_id: string; name: string; sector: string; confidence: number }; recommended_skills: { id: string; name: string; executable: boolean; risk: string; stage: string }[]; orchestration: { state: string; permissions_granted: boolean; next_step: string } };
type Project = { id: string; name: string; workspace: string; description: string; favorite_agents: string[]; created_at: number; updated_at: number };
type MemoryItem = { id: string; project_id: string | null; kind: string; content: string; source: string; created_at: number; updated_at: number };
type Onboarding = { completed: boolean; assistant_named: boolean; voice_configured: boolean; workspace_configured: boolean; permissions_reviewed: boolean };
type ContextStatus = { active_project: Project | null; permissions_granted: boolean };
type ContextPreview = { public_context: Record<string, unknown>; local_context: Record<string, unknown>; selected_memory_ids: string[]; bindings: string[]; permissions_granted: boolean };
type MissionEvidenceEvent = { id: string; step_index: number | null; phase: string; outcome: string; summary: string; evidence: Record<string, unknown>; created_at: string };
type MissionIntelligence = { mission_id: string; planner: string; agent_id: string; reason_summary: string; context: Record<string, unknown>; selected_memory_ids: string[]; events: MissionEvidenceEvent[]; chain_of_thought_exposed: boolean };
type DemoReadiness = { ready: boolean; checks: Record<string, boolean>; next_action: { key: string; label: string; view: View }; active_project: { id: string; name: string } | null; permissions_granted: boolean };
type FunctionalMVPFlow = { id: string; name: string; description: string; category: string; requires: string[]; success: string; status: string; missing: string[]; permissions_granted: boolean };
type CommercialStatus = { entitlement: { plan: string; status: string; source: string; expires_at: number | null; grants_execution_permissions: boolean }; consents: { terms: { version: string; accepted: boolean }; privacy: { version: string; accepted: boolean } }; telemetry_enabled: boolean; terms_version: string; privacy_version: string; support_email: string; update_manifest_configured: boolean; billing_provider: string; permissions_granted: boolean };

let accountAccessToken = '';

const missionStatus: Record<string, string> = {
  planned: 'Planejada', awaiting_approval: 'Aguardando autorização', awaiting_verification: 'Aguardando verificação',
  paused: 'Pausada', executing: 'Executando', completed: 'Concluída', failed: 'Falhou', cancelled: 'Cancelada',
  needs_review: 'Revisão necessária', unverified: 'Não verificada'
};

async function call<T>(path: string, token: string, method = 'GET', body?: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      'X-Oryven-Session': token,
      ...(accountAccessToken ? { Authorization: `Bearer ${accountAccessToken}` } : {}),
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' })
    },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || `Erro HTTP ${res.status}`);
  return payload as T;
}

function shortId(value: string) { return value.length > 12 ? `${value.slice(0, 7)}…${value.slice(-4)}` : value; }

function friendlyError(raw: string) {
  const text = raw.toLowerCase();
  if (text.includes('buno') && (text.includes('conect') || text.includes('token') || text.includes('indispon'))) return { title: 'Buno AI indisponível', message: 'Não consegui conectar ao planner da Buno agora. Você pode verificar a integração ou continuar com recursos locais.', action: 'Abrir integrações', view: 'settings' as View };
  if (text.includes('workspace') || text.includes('projeto ativo') || text.includes('context')) return { title: 'Falta contexto do projeto', message: 'Selecione um projeto ativo para o Oryven saber em qual workspace trabalhar sem adivinhar caminhos.', action: 'Selecionar projeto', view: 'projects' as View };
  if (text.includes('autoriz') || text.includes('approval')) return { title: 'Ação aguardando sua decisão', message: 'Revise o alvo, impacto e escopo antes de continuar.', action: 'Abrir Authorizations', view: 'approvals' as View };
  if (text.includes('microfone') || text.includes('voice') || text.includes('vosk')) return { title: 'Voz não está pronta', message: 'Verifique microfone, wake word e provider de voz nas configurações.', action: 'Configurar voz', view: 'settings' as View };
  if (text.includes('missão não criada') || text.includes('etapa desconhecida')) return { title: 'Não consegui transformar esse pedido em missão', message: 'Tente descrever o resultado desejado de forma mais direta ou use uma missão profissional com projeto ativo.', action: 'Voltar ao início', view: 'home' as View };
  if (text.includes('offline') || text.includes('backend') || text.includes('http')) return { title: 'Oryven Core desconectado', message: 'O aplicativo perdeu a conexão com o núcleo local. Verifique o backend e tente novamente.', action: 'Abrir Settings', view: 'settings' as View };
  return { title: 'Não consegui concluir esta etapa', message: raw, action: 'Tentar de novo', view: 'home' as View };
}

export default function App() {
  const [token, setToken] = useState('');
  const [account, setAccount] = useState<AccountUser | null>(null);
  const [connected, setConnected] = useState(false);
  const [view, setView] = useState<View>('home');
  const [status, setStatus] = useState<Status | null>(null);
  const [pending, setPending] = useState<Pending[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [missionIntel, setMissionIntel] = useState<Record<string, MissionIntelligence>>({});
  const [voiceProfile, setVoiceProfile] = useState<VoiceProfile | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [apps, setApps] = useState<InstalledApp[]>([]);
  const [bunoHealth, setBunoHealth] = useState<BunoHealth | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [command, setCommand] = useState('');
  const [search, setSearch] = useState('');
  const [objective, setObjective] = useState('');
  const [plan, setPlan] = useState<ProfessionalPlan | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [memoryEnabled, setMemoryEnabled] = useState(true);
  const [onboarding, setOnboarding] = useState<Onboarding | null>(null);
  const [contextStatus, setContextStatus] = useState<ContextStatus | null>(null);
  const [contextPreview, setContextPreview] = useState<ContextPreview | null>(null);
  const [demoReadiness, setDemoReadiness] = useState<DemoReadiness | null>(null);
  const [mvpFlows, setMvpFlows] = useState<FunctionalMVPFlow[]>([]);
  const [commercial, setCommercial] = useState<CommercialStatus | null>(null);
  const [licenseKey, setLicenseKey] = useState('');
  const [feedbackText, setFeedbackText] = useState('');
  const [projectName, setProjectName] = useState('');
  const [projectWorkspace, setProjectWorkspace] = useState('');
  const [projectDescription, setProjectDescription] = useState('');
  const [memoryText, setMemoryText] = useState('');
  const [memoryKind, setMemoryKind] = useState('fact');
  const [memoryProjectId, setMemoryProjectId] = useState('');

  const [authMode, setAuthMode] = useState<AuthMode>('login');
  const [authBusy, setAuthBusy] = useState(false);
  const [authMessage, setAuthMessage] = useState('');
  const [authEmail, setAuthEmail] = useState('');
  const [authName, setAuthName] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authConfirm, setAuthConfirm] = useState('');
  const [authCode, setAuthCode] = useState('');

  const refresh = useCallback(async (session: string) => {
    try {
      const [s, p, e, m, v] = await Promise.all([
        call<Status>('/api/status', session),
        call<Pending[]>('/api/actions/pending', session),
        call<EventItem[]>('/api/events', session),
        call<Mission[]>('/api/missions', session),
        call<VoiceProfile>('/api/voice/profile', session)
      ]);
      setStatus(s); setPending(p); setEvents(e); setMissions(m); setVoiceProfile(v); setConnected(true);
    } catch { setConnected(false); }
  }, []);

  const discover = useCallback(async (session: string) => {
    try {
      const [a, s, p, pr, mem, ob, ctx, demo, mvp, commercialStatus] = await Promise.all([
        call<{ agents: Agent[] }>('/api/agents', session),
        call<{ skills: Skill[] }>('/api/skills', session),
        call<{ apps: InstalledApp[] }>('/api/apps', session),
        call<{ projects: Project[] }>('/api/projects', session),
        call<{ enabled: boolean; memories: MemoryItem[] }>('/api/memory/professional', session),
        call<Onboarding>('/api/onboarding', session),
        call<ContextStatus>('/api/context', session),
        call<DemoReadiness>('/api/demo/readiness', session),
        call<{ flows: FunctionalMVPFlow[] }>('/api/mvp/flows', session),
        call<CommercialStatus>('/api/commercial/status', session)
      ]);
      setAgents(a.agents); setSkills(s.skills); setApps(p.apps); setProjects(pr.projects); setMemories(mem.memories); setMemoryEnabled(mem.enabled); setOnboarding(ob); setContextStatus(ctx); setDemoReadiness(demo); setMvpFlows(mvp.flows); setCommercial(commercialStatus);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      // The packaged Python sidecar can take several seconds to cold-start on
      // Windows. Keep retrying while this screen is mounted instead of giving
      // up after a short fixed window and leaving authentication disabled.
      while (active) {
        try {
          const session = await fetch(`${API}/api/session`).then(r => {
            if (!r.ok) throw new Error('offline');
            return r.json();
          });
          if (!active) return;
          setToken(session.session_token);
          setConnected(true);

          const restored = await fetch(`${API}/api/auth/restore`, {
            method: 'POST',
            headers: { 'X-Oryven-Session': session.session_token }
          });

          if (restored.ok) {
            const auth: AuthResult = await restored.json();
            accountAccessToken = auth.access_token;
            setAccount(auth.user);
            await refresh(session.session_token);
            await discover(session.session_token);
          }
          return;
        } catch {
          if (!active) return;
          setConnected(false);
          await new Promise(r => window.setTimeout(r, 500));
        }
      }
    })();
    return () => { active = false; };
  }, [discover, refresh]);

  useEffect(() => {
    if (!token || !account) return;
    const interval = window.setInterval(() => void refresh(token), 1000);
    return () => window.clearInterval(interval);
  }, [token, account, refresh]);

  async function authRequest(path: string, body?: unknown) {
    if (!token) throw new Error('Backend ainda não conectado.');
    const res = await fetch(`${API}${path}`, {
      method: 'POST', headers: { 'X-Oryven-Session': token, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body)
    });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(payload.detail || `Erro HTTP ${res.status}`);
    return payload;
  }

  async function finishAuth(result: AuthResult) {
    accountAccessToken = result.access_token; setAccount(result.user);
    setAuthPassword(''); setAuthConfirm(''); setAuthCode(''); setAuthMessage('');
    await refresh(token); await discover(token);
  }

  async function submitAuth() {
    setAuthBusy(true); setAuthMessage('');
    try {
      if (authMode === 'login') await finishAuth(await authRequest('/api/auth/login', { email: authEmail.trim(), password: authPassword, remember_device: true }));
      if (authMode === 'register') {
        if (authPassword !== authConfirm) throw new Error('As senhas não coincidem.');
        await authRequest('/api/auth/register', { name: authName.trim(), email: authEmail.trim(), password: authPassword });
        setAuthMode('verify'); setAuthMessage('Enviamos um código de 6 dígitos para seu e-mail.');
      }
      if (authMode === 'verify') await finishAuth(await authRequest('/api/auth/verify-email', { email: authEmail.trim(), code: authCode.trim() }));
      if (authMode === 'forgot') { const r = await authRequest('/api/auth/forgot-password', { email: authEmail.trim() }); setAuthMessage(r.message || 'Se houver uma conta, enviaremos um código.'); setAuthMode('reset'); }
      if (authMode === 'reset') {
        if (authPassword !== authConfirm) throw new Error('As senhas não coincidem.');
        const r = await authRequest('/api/auth/reset-password', { email: authEmail.trim(), code: authCode.trim(), new_password: authPassword });
        setAuthMessage(r.message || 'Senha alterada. Entre novamente.'); setAuthPassword(''); setAuthConfirm(''); setAuthCode(''); setAuthMode('login');
      }
    } catch (e) { setAuthMessage(e instanceof Error ? e.message : String(e)); }
    finally { setAuthBusy(false); }
  }

  async function run<T = unknown>(path: string, method = 'POST', body?: unknown): Promise<T | null> {
    if (!token) return null;
    setWorking(true); setError('');
    try { const result = await call<T>(path, token, method, body); await refresh(token); return result; }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); return null; }
    finally { setWorking(false); }
  }

  async function startMvpFlow(flow: FunctionalMVPFlow) {
    if (!contextStatus?.active_project) { setError('workspace: selecione um projeto ativo antes de iniciar um fluxo do Functional MVP.'); setView('projects'); return; }
    const result = await run<any>(`/api/mvp/flows/${flow.id}/start`, 'POST', { objective: flow.name, context: {} });
    if (!result) return;
    if (result.status === 'needs_context') {
      setError(`Falta contexto para ${flow.name}: ${(result.missing || []).join(', ')}.`);
      return;
    }
    setView('missions');
  }

  async function logout() {
    await run('/api/auth/logout'); accountAccessToken = ''; setAccount(null); setView('home');
    setStatus(null); setPending([]); setEvents([]); setMissions([]); setAgents([]); setSkills([]); setApps([]);
  }

  async function sendCommand(asMission = false) {
    const text = command.trim(); if (!text) return;
    if (asMission && !contextStatus?.active_project) { setError('workspace: selecione um projeto ativo antes de criar uma missão comercial.'); setView('projects'); return; }
    const created = await run(asMission ? '/api/missions' : '/api/commands', 'POST', { text });
    if (created) setCommand('');
    if (asMission && created) setView('missions');
  }

  async function decide(id: string, decision: 'approve' | 'deny') {
    await run(`/api/actions/${id}/decision`, 'POST', { decision });
  }

  async function loadMissionIntelligence(id: string) {
    if (!token) return;
    try {
      const intel = await call<MissionIntelligence>(`/api/missions/${id}/intelligence`, token);
      setMissionIntel(current => ({ ...current, [id]: intel }));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function saveVoice(patch: Partial<VoiceProfile>) {
    if (!token) return; setWorking(true); setError('');
    try { const updated = await call<VoiceProfile>('/api/voice/profile', token, 'PATCH', patch); setVoiceProfile(updated); if (patch.assistant_name) await call<Onboarding>('/api/onboarding', token, 'PATCH', { assistant_named: true }); if ('wake_enabled' in patch || 'background_listening_enabled' in patch || 'speak_on_startup' in patch) await call<Onboarding>('/api/onboarding', token, 'PATCH', { voice_configured: true }); await refresh(token); await discover(token); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setWorking(false); }
  }

  async function planProfessional() {
    if (!objective.trim() || !token) return; setWorking(true); setError('');
    try { setPlan(await call<ProfessionalPlan>('/api/agents/plan', token, 'POST', { objective: objective.trim() })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setWorking(false); }
  }


  async function createProject() {
    if (!projectName.trim() || !projectWorkspace.trim()) return;
    const created = await run<Project>('/api/projects', 'POST', { name: projectName.trim(), workspace: projectWorkspace.trim(), description: projectDescription.trim(), favorite_agents: [] });
    if (created) { setProjectName(''); setProjectWorkspace(''); setProjectDescription(''); await discover(token); }
  }

  async function activateProject(projectId: string | null) {
    const next = await run<ContextStatus>('/api/context/active-project', 'PATCH', { project_id: projectId });
    if (next) { setContextStatus(next); setContextPreview(null); await discover(token); }
  }

  async function previewContext() {
    if (!objective.trim()) return;
    const next = await run<ContextPreview>('/api/context/preview', 'POST', { objective: objective.trim(), context: {} });
    if (next) setContextPreview(next);
  }

  async function addMemory() {
    if (!memoryText.trim()) return;
    const created = await run<MemoryItem>('/api/memory/professional', 'POST', { content: memoryText.trim(), kind: memoryKind, project_id: memoryProjectId || null });
    if (created) { setMemoryText(''); await discover(token); }
  }

  async function updateOnboarding(patch: Partial<Onboarding>) {
    const next = await run<Onboarding>('/api/onboarding', 'PATCH', patch);
    if (next) { setOnboarding(next); await discover(token); }
  }

  const filteredAgents = useMemo(() => agents.filter(a => `${a.name} ${a.sector} ${a.description}`.toLowerCase().includes(search.toLowerCase())), [agents, search]);
  const filteredSkills = useMemo(() => skills.filter(s => `${s.name} ${s.id} ${s.family || ''}`.toLowerCase().includes(search.toLowerCase())), [skills, search]);
  const assistant = voiceProfile?.assistant_name || status?.assistant_name || 'Oryven';
  const activeMission = missions.find(m => ['awaiting_approval', 'executing', 'awaiting_verification', 'needs_review'].includes(m.status));
  const runtimeState = pending.length ? 'approval' : status?.microphone_on ? 'listening' : activeMission?.status === 'executing' ? 'executing' : working ? 'thinking' : 'idle';
  const friendly = error ? friendlyError(error) : null;
  const latestMission = missions[0] || null;
  const completedMission = missions.find(m => m.status === 'completed') || null;
  const journey = [
    { label: 'Conta', done: true, hint: account?.email_verified ? 'Conta verificada' : 'Verifique seu e-mail', view: 'home' as View },
    { label: 'Configuração', done: !!onboarding?.completed, hint: onboarding?.completed ? 'Onboarding completo' : 'Finalize o onboarding', view: 'settings' as View },
    { label: 'Projeto', done: !!contextStatus?.active_project, hint: contextStatus?.active_project?.name || 'Selecione um projeto', view: 'projects' as View },
    { label: 'Tarefa', done: missions.length > 0, hint: missions.length ? 'Missão criada' : 'Digite ou fale um objetivo', view: 'home' as View },
    { label: 'Autorização', done: !!latestMission && !['planned','awaiting_approval'].includes(latestMission.status), hint: pending.length ? 'Sua decisão é necessária' : 'Governança ativa', view: 'approvals' as View },
    { label: 'Resultado', done: !!completedMission, hint: completedMission ? 'Resultado disponível' : 'Acompanhe execução e verificação', view: 'missions' as View },
  ];

  if (!account) {
    return <div className="auth-shell">
      <div className="auth-backdrop"/><section className="auth-card">
        <div className="brand-lockup"><span className="brand-mark">◇</span><div><strong>ORYVEN</strong><small>BY BUNO AI</small></div></div>
        <div className="auth-intro"><span>DESKTOP INTELLIGENCE</span><h1>{authMode === 'login' ? 'Bem-vindo de volta.' : authMode === 'register' ? 'Crie seu Oryven.' : authMode === 'verify' ? 'Confirme seu e-mail.' : authMode === 'forgot' ? 'Recupere o acesso.' : 'Crie uma nova senha.'}</h1><p>Seu assistente, suas missões e suas permissões permanecem isolados por conta neste dispositivo.</p></div>
        <div className="auth-form">
          {authMode === 'register' && <label>Nome completo<input value={authName} onChange={e => setAuthName(e.target.value)} autoComplete="name" /></label>}
          {authMode !== 'verify' && <label>E-mail<input type="email" value={authEmail} onChange={e => setAuthEmail(e.target.value)} autoComplete="email" /></label>}
          {authMode === 'verify' && <div className="inline-note">Código enviado para <strong>{authEmail}</strong></div>}
          {(authMode === 'login' || authMode === 'register' || authMode === 'reset') && <label>{authMode === 'reset' ? 'Nova senha' : 'Senha'}<input type="password" value={authPassword} onChange={e => setAuthPassword(e.target.value)} autoComplete={authMode === 'login' ? 'current-password' : 'new-password'} /></label>}
          {(authMode === 'register' || authMode === 'reset') && <label>Confirmar senha<input type="password" value={authConfirm} onChange={e => setAuthConfirm(e.target.value)} autoComplete="new-password" /></label>}
          {(authMode === 'verify' || authMode === 'reset') && <label>Código de 6 caracteres<input inputMode="text" autoCapitalize="characters" maxLength={6} value={authCode} onChange={e => setAuthCode(e.target.value.replace(/[^a-zA-Z0-9]/g, '').toUpperCase().slice(0, 6))} /></label>}
          {!token && <div className="auth-message">Conectando ao backend local do Oryven…</div>}{authMessage && <div className="auth-message">{authMessage}</div>}
          <button className="primary wide" disabled={authBusy} onClick={() => void submitAuth()}>{authBusy ? 'Processando…' : authMode === 'login' ? 'Entrar no Oryven' : authMode === 'register' ? 'Criar conta' : authMode === 'verify' ? 'Verificar e entrar' : authMode === 'forgot' ? 'Enviar código' : 'Alterar senha'}</button>
          {authMode === 'login' && <><button className="text-button" onClick={() => setAuthMode('forgot')}>Esqueceu sua senha?</button><button className="text-button" onClick={() => setAuthMode('register')}>Criar uma conta</button></>}
          {authMode === 'register' && <button className="text-button" onClick={() => setAuthMode('login')}>Já tenho uma conta</button>}
          {authMode === 'verify' && <button className="text-button" onClick={() => void authRequest('/api/auth/resend-verification', { email: authEmail }).then(r => setAuthMessage(r.message)).catch(e => setAuthMessage(String(e)))}>Reenviar código</button>}
          {(authMode === 'forgot' || authMode === 'reset') && <button className="text-button" onClick={() => setAuthMode('login')}>Voltar ao login</button>}
        </div>
        <div className="auth-security"><ShieldCheck size={16}/> Sessão persistente protegida no Windows. Senhas e tokens não ficam no frontend.</div>
      </section>
    </div>;
  }

  const nav: { id: View; label: string; icon: typeof Home; badge?: number }[] = [
    { id: 'home', label: 'Home', icon: Home },
    { id: 'projects', label: 'Projects', icon: FolderKanban },
    { id: 'memory', label: 'Memory', icon: MemoryStick },
    { id: 'missions', label: 'Missions', icon: Zap, badge: activeMission ? 1 : undefined },
    { id: 'approvals', label: 'Authorizations', icon: ShieldCheck, badge: pending.length || undefined },
    { id: 'agents', label: 'Agents', icon: Bot },
    { id: 'skills', label: 'Skills', icon: Blocks },
    { id: 'computer', label: 'Computer', icon: Monitor },
    { id: 'commercial', label: 'Paid Pilot', icon: BriefcaseBusiness },
    { id: 'settings', label: 'Settings', icon: Settings }
  ];

  return <div className="product-shell">
    <aside className="sidebar">
      <div className="brand-lockup sidebar-brand"><span className="brand-mark">◇</span><div><strong>ORYVEN</strong><small>BY BUNO AI</small></div></div>
      <nav>{nav.map(item => { const Icon = item.icon; return <button key={item.id} className={view === item.id ? 'nav-item active' : 'nav-item'} onClick={() => setView(item.id)}><Icon size={18}/><span>{item.label}</span>{item.badge ? <b>{item.badge}</b> : null}</button>; })}</nav>
      <div className="sidebar-spacer"/>
      <div className="governance-card"><ShieldCheck size={18}/><div><strong>Governança ativa</strong><small>Deny-by-default · one-shot approval</small></div></div>
      <button className="account-button" onClick={() => void logout()}><div className="avatar">{account.name.slice(0, 1).toUpperCase()}</div><div><strong>{account.name}</strong><small>{account.email}</small></div><LogOut size={16}/></button>
    </aside>

    <main className="workspace">
      <header className="workspace-header"><div><span className="kicker">ORYVEN / {view.toUpperCase()}</span><h1>{view === 'home' ? 'Command Center' : nav.find(n => n.id === view)?.label}</h1></div><div className="header-status"><span className={connected ? 'status-dot online' : 'status-dot'}/>{connected ? 'Core online' : 'Core offline'}<span className="version-pill">0.19 PAID PILOT</span></div></header>
      {friendly && <div className="error-banner friendly-error"><X size={16}/><div><strong>{friendly.title}</strong><span>{friendly.message}</span></div><button onClick={() => { setError(''); setView(friendly.view); }}>{friendly.action}</button><button className="icon-close" onClick={() => setError('')} aria-label="Fechar">×</button></div>}
      {onboarding && !onboarding.completed && <section className="onboarding-banner"><div><span className="eyebrow"><Sparkles size={14}/> PRIMEIRA CONFIGURAÇÃO</span><h3>Prepare seu Oryven</h3><p>Complete os quatro passos para deixar identidade, voz, workspace e governança prontos.</p></div><div className="onboarding-steps"><button className={onboarding.assistant_named ? 'done' : ''} onClick={() => setView('settings')}><span>1</span> Nome do assistente {onboarding.assistant_named && <Check size={14}/>}</button><button className={onboarding.voice_configured ? 'done' : ''} onClick={() => setView('settings')}><span>2</span> Voz e microfone {onboarding.voice_configured && <Check size={14}/>}</button><button className={onboarding.workspace_configured ? 'done' : ''} onClick={() => setView('projects')}><span>3</span> Primeiro projeto {onboarding.workspace_configured && <Check size={14}/>}</button><button className={onboarding.permissions_reviewed ? 'done' : ''} onClick={() => void updateOnboarding({ permissions_reviewed: true })}><span>4</span> Revisar governança {onboarding.permissions_reviewed && <Check size={14}/>}</button></div></section>}

      {view === 'home' && <>
        <section className="hero-grid">
          <div className="hero-copy"><span className="eyebrow"><Sparkles size={14}/> PERSONAL AI WORKSPACE</span><h2>Olá, {account.name.split(' ')[0]}.<br/>Eu sou <em>{assistant}.</em></h2><p>Planejo, coordeno agentes e trabalho no seu computador com autorização explícita em cada ação.</p>
            <div className="hero-actions"><button className="primary" disabled={working || !connected} onClick={() => void run(status?.microphone_on ? '/api/voice/stop' : '/api/voice/start')} >{status?.microphone_on ? <MicOff size={17}/> : <Mic size={17}/>} {status?.microphone_on ? 'Desativar microfone' : 'Ativar voz'}</button><button className="danger-ghost" disabled={working || !connected} onClick={() => void run('/api/stop')}><CircleStop size={17}/> Emergency stop</button></div>
          </div>
          <div className={`core-orb ${runtimeState}`}><div className="orb-ring ring-a"/><div className="orb-ring ring-b"/><div className="orb-center">◇</div><div className="orb-label"><strong>{runtimeState === 'approval' ? 'AWAITING APPROVAL' : runtimeState.toUpperCase()}</strong><small>{pending.length ? `${pending.length} autorização(ões) pendente(s)` : status?.microphone_on ? `Diga “${assistant}, acordar”` : 'Ready'}</small></div></div>
        </section>
        <section className="command-deck"><div className="command-icon"><Command size={20}/></div><input value={command} onChange={e => setCommand(e.target.value)} onKeyDown={e => e.key === 'Enter' && void sendCommand(true)} placeholder={`Diga ao ${assistant} o que você quer alcançar…`}/><button className="primary" disabled={!command.trim() || working} onClick={() => void sendCommand(true)}>Criar missão <ArrowRight size={16}/></button></section>
        <section className={`demo-journey ${demoReadiness?.ready ? 'ready' : ''}`}><div className="journey-heading"><div><span className="eyebrow"><Sparkles size={14}/> DEMO READINESS</span><h3>{demoReadiness?.ready ? 'Pronto para demonstrar' : 'Prepare o próximo passo'}</h3><p>{demoReadiness?.ready ? 'Conta, contexto e governança estão prontos para um fluxo completo.' : demoReadiness?.next_action?.label || 'Complete a configuração para iniciar uma missão segura.'}</p></div>{demoReadiness && <button className="secondary" onClick={() => setView(demoReadiness.next_action.view)}>{demoReadiness.ready ? 'Criar missão' : demoReadiness.next_action.label} <ArrowRight size={14}/></button>}</div><div className="journey-steps">{journey.map((step, i) => <button key={step.label} className={step.done ? 'journey-step done' : 'journey-step'} onClick={() => setView(step.view)}><span>{step.done ? <Check size={13}/> : i + 1}</span><div><strong>{step.label}</strong><small>{step.hint}</small></div></button>)}</div></section>
        <section className="metric-grid"><Metric icon={Zap} label="Missões" value={String(missions.length)} note={activeMission ? '1 missão em andamento' : 'Tudo concluído por enquanto'}/><Metric icon={ShieldCheck} label="Autorizações" value={String(pending.length)} note={pending.length ? 'Sua decisão é necessária' : 'Nenhuma ação aguardando você'}/><Metric icon={FolderKanban} label="Projeto ativo" value={contextStatus?.active_project ? contextStatus.active_project.name : 'Nenhum'} note={contextStatus?.active_project ? 'Contexto profissional selecionado' : 'Escolha um projeto para dar contexto'}/><Metric icon={Mic} label="Voice" value={status?.microphone_on ? 'ON' : 'OFF'} note={status?.microphone_on ? `Diga “${assistant}, acordar”` : 'Ative quando quiser falar'}/></section>
        <section className="status-strip">
          <div className="status-primary"><span className={`status-beacon ${runtimeState}`}/><div><strong>{runtimeState === 'approval' ? 'Sua autorização é necessária' : runtimeState === 'listening' ? `${assistant} está ouvindo` : runtimeState === 'executing' ? 'Missão em execução' : runtimeState === 'thinking' ? 'Planejando próximo passo' : `${assistant} está pronto`}</strong><small>{runtimeState === 'approval' ? 'Revise impacto, alvo e escopo antes de autorizar.' : activeMission ? activeMission.title : contextStatus?.active_project ? `Contexto ativo: ${contextStatus.active_project.name}` : 'Crie uma missão ou selecione um projeto.'}</small></div></div>
          <button className="secondary" onClick={() => setView(pending.length ? 'approvals' : activeMission ? 'missions' : 'projects')}>{pending.length ? 'Revisar autorização' : activeMission ? 'Abrir missão' : 'Selecionar projeto'} <ArrowRight size={15}/></button>
        </section>
        <section className="dashboard-grid">
          <Panel title="Missão em foco" subtitle={activeMission ? 'Acompanhe progresso, evidências e próxima decisão' : 'Nada executando agora'} icon={Zap}>{activeMission ? <MissionCard mission={activeMission} intelligence={missionIntel[activeMission.id]} onLoadIntelligence={() => void loadMissionIntelligence(activeMission.id)} onVerify={c => void run(`/api/missions/${activeMission.id}/verify`, 'POST', { confirmed: c })} onCancel={() => void run(`/api/missions/${activeMission.id}/cancel`)}/> : <Empty icon={Check} title="Tudo sob controle" text="Crie uma missão por voz ou texto. O Oryven planeja, pede autorização e só então age."/>}</Panel>
          <Panel title="Authorization Center" subtitle="Ações que aguardam sua decisão" icon={LockKeyhole}>{pending.length ? pending.slice(0, 3).map(p => <ApprovalCard key={p.id} item={p} onApprove={() => void decide(p.id, 'approve')} onDeny={() => void decide(p.id, 'deny')}/>) : <Empty icon={ShieldCheck} title="Tudo sob controle" text="Nenhuma ação aguardando autorização."/>}</Panel>
        </section>
        <Panel title="Atividade recente" subtitle="Transparência sobre decisões e execuções" icon={Activity}><div className="timeline">{events.length ? events.slice(-7).reverse().map(e => <div className="timeline-item" key={e.id}><span className={`event-dot ${e.kind}`}/><time>{new Date(e.at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</time><p>{e.message}</p></div>) : <p className="muted">Nenhum evento nesta sessão.</p>}</div></Panel>
      </>}

      {view === 'projects' && <><section className="section-toolbar"><div><h2>Projects</h2><p>Organize trabalho, memória e missões por contexto. O caminho local continua protegido do planner remoto.</p></div><span className="ready-badge">{contextStatus?.active_project ? `ATIVO · ${contextStatus.active_project.name}` : `${projects.length} PROJETO(S)`}</span></section>{contextStatus?.active_project && <div className="active-project-banner"><div className="project-avatar"><BriefcaseBusiness size={20}/></div><div><span>CONTEXTO ATIVO</span><strong>{contextStatus.active_project.name}</strong><small>{contextStatus.active_project.description || 'Sem descrição'} · workspace protegido por token</small></div><button className="secondary" onClick={() => setView('home')}>Voltar ao Command Center</button></div>}<section className="planner-card"><span className="eyebrow"><FolderKanban size={14}/> NEW PROJECT</span><div className="project-form-grid"><label className="field">Nome<input value={projectName} onChange={e => setProjectName(e.target.value)} placeholder="Flow Commerce"/></label><label className="field">Workspace<input value={projectWorkspace} onChange={e => setProjectWorkspace(e.target.value)} placeholder="E:\\projetos\\flow-commerce"/></label><label className="field project-description">Descrição<input value={projectDescription} onChange={e => setProjectDescription(e.target.value)} placeholder="Objetivo e contexto do projeto"/></label></div><button className="primary" disabled={!projectName.trim() || !projectWorkspace.trim()} onClick={() => void createProject()}>Criar projeto</button></section><section className="planner-card"><span className="eyebrow"><BrainCircuit size={14}/> CONTEXT ENGINE</span><div className="planner-form"><input value={objective} onChange={e => setObjective(e.target.value)} placeholder="Ex.: corrija o backend Java deste projeto"/><button className="secondary" disabled={!objective.trim()} onClick={() => void previewContext()}>Prévia do contexto</button></div>{contextPreview && <div className="plan-result"><strong>Contexto minimizado</strong><span>{contextPreview.selected_memory_ids.length} memória(s) selecionada(s)</span><p>Workspace enviado à Buno: {String(contextPreview.public_context.workspace || 'nenhum')}</p><div className="chip-row">{Array.isArray(contextPreview.public_context.memory_notes) && (contextPreview.public_context.memory_notes as string[]).slice(0,6).map((m,i) => <span className="chip" key={i}>{m}</span>)}</div></div>}</section><div className="catalog-grid">{projects.map(p => <article className="catalog-card" key={p.id}><div className="card-top"><div className="catalog-icon"><BriefcaseBusiness size={19}/></div>{contextStatus?.active_project?.id === p.id && <span className="ready-badge">ACTIVE</span>}</div><span className="catalog-sector">PROJECT</span><h3>{p.name}</h3><p>{p.description || 'Sem descrição.'}</p><small>{p.workspace}</small><div className="approval-actions"><button className="mini-button" onClick={() => void activateProject(contextStatus?.active_project?.id === p.id ? null : p.id)}>{contextStatus?.active_project?.id === p.id ? 'Desativar contexto' : 'Usar como ativo'}</button><button className="mini-button" onClick={() => { setMemoryProjectId(p.id); setView('memory'); }}>Abrir memória</button><button className="text-danger" onClick={async () => { if (window.confirm(`Excluir ${p.name} e a memória desse projeto?`)) { await run(`/api/projects/${p.id}`, 'DELETE'); await discover(token); } }}>Excluir</button></div></article>)}</div>{!projects.length && <Empty icon={FolderKanban} title="Nenhum projeto ainda" text="Crie um projeto para agrupar workspace, memória e contexto profissional."/>}</>}

      {view === 'memory' && <><section className="section-toolbar"><div><h2>Professional Memory</h2><p>Memória explícita, isolada por usuário e opcionalmente por projeto.</p></div><button className="secondary" onClick={async () => { const r = await run<{enabled:boolean}>('/api/memory/professional/settings','PATCH',{enabled:!memoryEnabled}); if (r) { setMemoryEnabled(r.enabled); await discover(token); } }}>{memoryEnabled ? 'Desativar memória' : 'Ativar memória'}</button></section><section className="planner-card"><div className="memory-compose"><select value={memoryKind} onChange={e => setMemoryKind(e.target.value)}><option value="fact">Fato</option><option value="preference">Preferência</option><option value="decision">Decisão</option><option value="project_note">Nota de projeto</option></select><select value={memoryProjectId} onChange={e => setMemoryProjectId(e.target.value)}><option value="">Memória global</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select><input value={memoryText} onChange={e => setMemoryText(e.target.value)} placeholder="Ex.: Preferir relatórios executivos em português."/><button className="primary" disabled={!memoryEnabled || !memoryText.trim()} onClick={() => void addMemory()}>Lembrar</button></div><p>Senhas, tokens, API keys e secrets são rejeitados pelo backend.</p></section><div className="stack">{memories.filter(m => !memoryProjectId || m.project_id === memoryProjectId).map(m => <article className="approval-card" key={m.id}><div className="approval-top"><span className="approval-kind">{m.kind}</span><button className="text-danger" onClick={async () => { await run(`/api/memory/professional/${m.id}`, 'DELETE'); await discover(token); }}>Apagar</button></div><h3>{m.content}</h3><p>{m.project_id ? projects.find(p => p.id === m.project_id)?.name || 'Projeto' : 'Memória global'} · explícita</p></article>)}</div></>}

      {view === 'missions' && <>
        <section className="section-toolbar"><div><h2>Mission Center</h2><p>Planejamento, autorização, execução, verificação e recuperação em um único lugar.</p></div><button className="secondary" onClick={() => void refresh(token)}><RefreshCw size={16}/> Atualizar</button></section>
        <section className="planner-card"><span className="eyebrow"><Gauge size={14}/> FUNCTIONAL MVP · 5 FLUXOS OFICIAIS</span><h3>Jornadas de aceitação</h3><p>Um fluxo só inicia depois de validar contexto e continua sujeito a autorização one-shot em cada ação.</p><div className="catalog-grid">{mvpFlows.map(flow => <article className="catalog-card" key={flow.id}><div className="card-top"><div className="catalog-icon"><Zap size={18}/></div><span className={flow.status === 'ready' ? 'ready-badge' : 'version-pill'}>{flow.status === 'ready' ? 'READY' : 'CONTEXT'}</span></div><span className="catalog-sector">{flow.category.toUpperCase()}</span><h3>{flow.name}</h3><p>{flow.description}</p><small>{flow.status === 'ready' ? flow.success : `Falta: ${flow.missing.join(', ')}`}</small><div className="approval-actions"><button className="mini-button" disabled={working || flow.status !== 'ready'} onClick={() => void startMvpFlow(flow)}>Iniciar fluxo</button></div></article>)}</div></section>
        <section className="command-deck compact"><div className="command-icon"><Zap size={19}/></div><input value={command} onChange={e => setCommand(e.target.value)} placeholder="Ex.: analise este projeto Python, rode os testes e prepare um relatório"/><button className="primary" disabled={!command.trim() || working} onClick={() => void sendCommand(true)}>Nova missão</button></section>
        <div className="stack">{missions.length ? missions.slice().reverse().map(m => <MissionCard key={m.id} mission={m} intelligence={missionIntel[m.id]} onLoadIntelligence={() => void loadMissionIntelligence(m.id)} onVerify={c => void run(`/api/missions/${m.id}/verify`, 'POST', { confirmed: c })} onCancel={() => void run(`/api/missions/${m.id}/cancel`)}/>) : <Empty icon={Zap} title="Ainda não há missões" text="Uma missão reúne objetivo, agentes, skills, aprovações e evidências."/>}</div>
      </>}

      {view === 'approvals' && <><section className="section-toolbar"><div><h2>Authorization Center</h2><p>Veja exatamente o que será feito, onde, por quê e com qual impacto antes de autorizar.</p></div><div className="authorization-summary"><strong>{pending.length}</strong><span>{pending.length === 1 ? 'decisão pendente' : 'decisões pendentes'}</span></div></section>{pending.length > 0 && <div className="authorization-notice"><ShieldCheck size={17}/><div><strong>Você mantém o controle</strong><p>Autorizações são one-shot. Aprovar esta ação não concede acesso permanente ao agente.</p></div></div>}<div className="stack">{pending.length ? pending.map(p => <ApprovalCard key={p.id} item={p} onApprove={() => void decide(p.id, 'approve')} onDeny={() => void decide(p.id, 'deny')}/>) : <Empty icon={ShieldCheck} title="Nenhuma autorização pendente" text="O Oryven não tem nenhuma ação aguardando sua decisão agora."/>}</div></>}

      {view === 'agents' && <><section className="section-toolbar"><div><h2>Professional Agents</h2><p>Perfis especializados que compartilham o mesmo runtime governado.</p></div><SearchBox value={search} onChange={setSearch}/></section><section className="planner-card"><div><span className="eyebrow"><BrainCircuit size={14}/> ROUTER</span><h3>Planejar por especialidade</h3><p>Descreva o objetivo; planejar não concede permissão.</p></div><div className="planner-form"><input value={objective} onChange={e => setObjective(e.target.value)} placeholder="Ex.: prepare uma campanha e um relatório executivo"/><button className="primary" onClick={() => void planProfessional()} disabled={!objective.trim() || working}>Planejar</button></div>{plan && <div className="plan-result"><strong>{plan.route.name}</strong><span>{plan.route.sector} · {Math.round(plan.route.confidence * 100)}%</span><p>{plan.objective}</p><div className="chip-row">{plan.recommended_skills.slice(0, 8).map(s => <span className="chip" key={s.id}>{s.name}</span>)}</div></div>}</section><div className="catalog-grid">{filteredAgents.map(a => <article className="catalog-card" key={a.id}><div className="catalog-icon"><Bot size={19}/></div><span className="catalog-sector">{a.sector}</span><h3>{a.name}</h3><p>{a.description}</p><small>{a.id}</small></article>)}</div></>}

      {view === 'skills' && <><section className="section-toolbar"><div><h2>Skill Library</h2><p>Capacidades reais, requisitos e estado de execução do runtime.</p></div><SearchBox value={search} onChange={setSearch}/></section><div className="catalog-grid skills">{filteredSkills.map(s => <article className="catalog-card" key={s.id}><div className="card-top"><div className="catalog-icon"><Blocks size={19}/></div><span className={s.executable ? 'ready-badge' : 'planned-badge'}>{s.executable ? 'READY' : 'PLANNED'}</span></div><span className="catalog-sector">{s.family || 'general'}</span><h3>{s.name}</h3><p>{s.description}</p><div className="skill-meta"><span>risk: {s.risk || 'unknown'}</span><span>{s.id}</span></div></article>)}</div></>}

      {view === 'computer' && <><section className="section-toolbar"><div><h2>Computer</h2><p>Apps, janelas, UI Automation, visão e workspaces governados.</p></div><button className="secondary" onClick={() => void discover(token)}><RefreshCw size={16}/> Redescobrir</button></section><section className="metric-grid"><Metric icon={AppWindow} label="Apps" value={String(apps.length)} note={`${apps.filter(a => a.launchable).length} inicializáveis`}/><Metric icon={Eye} label="Vision" value="READY" note="Snapshot + UIA fusion"/><Metric icon={TerminalSquare} label="Terminal" value="SAFE" note="argv allowlist · shell=false"/><Metric icon={Gauge} label="Core" value={connected ? 'ONLINE' : 'OFFLINE'} note="127.0.0.1:8765"/></section><div className="dashboard-grid"><Panel title="Aplicativos" subtitle="Inventário local; descobrir não concede acesso" icon={AppWindow}><div className="app-list">{apps.slice(0, 30).map(a => <div className="app-row" key={a.name}><div><strong>{a.name}</strong><small>{a.version || 'versão desconhecida'}{a.launchable ? ' · launchable' : ''}</small></div>{a.launchable && <button className="mini-button" onClick={() => void run('/api/apps/launch/propose', 'POST', { app_name: a.name })}>Solicitar abertura</button>}</div>)}</div></Panel><Panel title="Windows UIA" subtitle="Inspecione primeiro; aja depois" icon={Monitor}><button className="secondary wide" onClick={async () => { const r = await run<{ pending?: { id: string } }>('/api/control/windows/propose'); if (r) setView('approvals'); }}>Solicitar inspeção de janelas</button><p className="muted small">Ações UIA permanecem vinculadas à identidade da janela e exigem aprovação separada.</p></Panel></div></>}


      {view === 'commercial' && <><section className="section-toolbar"><div><h2>Paid Pilot</h2><p>Licença, consentimentos, privacidade, feedback, exportação e suporte comercial.</p></div><span className={commercial?.entitlement.status === 'active' && ['pilot','pro'].includes(commercial.entitlement.plan) ? 'ready-badge' : 'planned-badge'}>{commercial?.entitlement.plan?.toUpperCase() || 'FREE'}</span></section><section className="metric-grid"><Metric icon={BriefcaseBusiness} label="Plano" value={(commercial?.entitlement.plan || 'free').toUpperCase()} note={commercial?.entitlement.status || 'active'}/><Metric icon={ShieldCheck} label="Termos" value={commercial?.consents.terms.accepted ? 'OK' : 'PENDENTE'} note={commercial?.terms_version || 'pilot'}/><Metric icon={LockKeyhole} label="Privacidade" value={commercial?.consents.privacy.accepted ? 'OK' : 'PENDENTE'} note={commercial?.privacy_version || 'pilot'}/><Metric icon={Activity} label="Telemetria" value={commercial?.telemetry_enabled ? 'ON' : 'OFF'} note="Opt-in · mínimo necessário"/></section><div className="settings-grid"><Panel title="Plano e cobrança" subtitle="Stripe Checkout + entitlement confirmado por webhook" icon={BriefcaseBusiness}><label className="field">Chave de licença manual<input type="password" value={licenseKey} onChange={e => setLicenseKey(e.target.value)} placeholder="Opcional para pilotos provisionados manualmente"/></label><div className="button-row"><button className="primary" disabled={!licenseKey.trim() || working} onClick={async()=>{const r=await run<{entitlement:CommercialStatus['entitlement']}>('/api/commercial/license/activate','POST',{license_key:licenseKey.trim()}); if(r){setLicenseKey(''); await discover(token);}}}>Ativar licença</button><button className="secondary" disabled={working || commercial?.billing_provider !== 'stripe'} onClick={async()=>{const r=await run<{checkout_url:string;session_id:string}>('/api/commercial/billing/checkout','POST',{plan:'pilot'}); if(r?.checkout_url){window.open(r.checkout_url,'_blank','noopener,noreferrer'); setError('Checkout aberto no navegador. Depois do pagamento, use “Sincronizar assinatura”.');}}}>Assinar com cartão</button><button className="secondary" disabled={working || commercial?.billing_provider !== 'stripe'} onClick={async()=>{const r=await run<{entitlement:CommercialStatus['entitlement']}>('/api/commercial/billing/sync','POST'); if(r){await discover(token); setError('Assinatura sincronizada com o Stripe.');}}}>Sincronizar assinatura</button></div><p className="muted small">Plano atual: {commercial?.entitlement.plan || 'free'} · cobrança nunca concede permissões de computador.</p></Panel><Panel title="Termos e privacidade" subtitle="Consentimentos versionados para o piloto" icon={ShieldCheck}><button className={commercial?.consents.terms.accepted ? 'approve' : 'secondary'} onClick={async()=>{await run('/api/commercial/consent','POST',{kind:'terms',version:commercial?.terms_version,accepted:true}); await discover(token);}}>{commercial?.consents.terms.accepted ? <Check size={14}/> : null} Termos do Piloto</button><button className={commercial?.consents.privacy.accepted ? 'approve' : 'secondary'} onClick={async()=>{await run('/api/commercial/consent','POST',{kind:'privacy',version:commercial?.privacy_version,accepted:true}); await discover(token);}}>{commercial?.consents.privacy.accepted ? <Check size={14}/> : null} Política de Privacidade</button><Toggle label="Telemetria mínima opt-in" checked={!!commercial?.telemetry_enabled} onChange={async v=>{await run('/api/commercial/telemetry','PATCH',{enabled:v}); await discover(token);}}/></Panel><Panel title="Seus dados" subtitle="Portabilidade e controle local" icon={MemoryStick}><button className="secondary wide" onClick={async()=>{const r=await run<{path:string;files:string[]}>('/api/commercial/export','POST'); if(r) setError(`Exportação criada localmente: ${r.path}`);}}>Exportar meus dados</button><p className="muted small">A exportação exclui credenciais de sessão, tokens e segredos internos.</p></Panel><Panel title="Feedback e suporte" subtitle={`Contato: ${commercial?.support_email || 'Buno support'}`} icon={Activity}><label className="field">Feedback<input value={feedbackText} onChange={e=>setFeedbackText(e.target.value)} placeholder="Conte o que funcionou ou o que precisa melhorar"/></label><button className="primary" disabled={feedbackText.trim().length < 3} onClick={async()=>{const r=await run('/api/commercial/feedback','POST',{category:'experience',message:feedbackText.trim(),include_diagnostics:false}); if(r)setFeedbackText('');}}>Enviar feedback local</button><button className="secondary wide" onClick={async()=>{const r=await run<Record<string,unknown>>('/api/support/diagnostics'); if(r)setError('Diagnóstico seguro gerado. Nenhum segredo foi incluído.');}}>Gerar diagnóstico seguro</button></Panel></div></>}

      {view === 'settings' && <><section className="section-toolbar"><div><h2>Settings</h2><p>Identidade, voz, privacidade e integrações locais.</p></div></section><section className="voice-overview"><div className={`voice-pulse ${status?.microphone_on ? 'active' : ''}`}><Mic size={24}/></div><div><span>VOICE-FIRST</span><h3>{status?.microphone_on ? `${assistant} está ouvindo` : 'Microfone em espera'}</h3><p>{voiceProfile?.wake_enabled ? `Wake word ativo: “${assistant}, acordar”` : 'Wake word desativado'}</p></div><button className={status?.microphone_on ? 'deny' : 'approve'} disabled={working || !connected} onClick={() => void run(status?.microphone_on ? '/api/voice/stop' : '/api/voice/start')}>{status?.microphone_on ? <MicOff size={16}/> : <Mic size={16}/>} {status?.microphone_on ? 'Desativar' : 'Ativar voz'}</button></section><div className="settings-grid"><Panel title="Identidade do assistente" subtitle="Nome usado na interface e wake word" icon={Sparkles}><label className="field">Nome<input value={voiceProfile?.assistant_name || ''} onChange={e => setVoiceProfile(v => v ? { ...v, assistant_name: e.target.value } : v)} /></label><button className="primary" disabled={!voiceProfile?.assistant_name.trim()} onClick={() => void saveVoice({ assistant_name: voiceProfile!.assistant_name.trim() })}>Salvar nome</button></Panel><Panel title="Voice-first" subtitle="Microfone e comportamento de inicialização" icon={Mic}><Toggle label="Wake word" checked={!!voiceProfile?.wake_enabled} onChange={v => void saveVoice({ wake_enabled: v })}/><Toggle label="Escuta em background" checked={!!voiceProfile?.background_listening_enabled} onChange={v => void saveVoice({ background_listening_enabled: v })}/><Toggle label="Falar ao iniciar" checked={!!voiceProfile?.speak_on_startup} onChange={v => void saveVoice({ speak_on_startup: v })}/><div className="settings-note"><Volume2 size={15}/> Provider atual: <strong>{status?.voice_provider === 'elevenlabs' ? 'ElevenLabs' : 'Windows local'}</strong></div></Panel><Panel title="Buno Intelligence" subtitle="Planner e chat locais, separados da conta Oryven" icon={BrainCircuit}><button className="secondary" onClick={async () => { if (!token) return; setWorking(true); try { setBunoHealth(await call<BunoHealth>('/api/integrations/buno/health', token)); } catch (e) { setError(String(e)); } finally { setWorking(false); } }}><RefreshCw size={15}/> Verificar Buno AI</button>{bunoHealth && <div className={`integration-state ${bunoHealth.reachable ? 'ok' : 'bad'}`}><span className="status-dot online"/><strong>{bunoHealth.reachable ? 'Conectada' : 'Indisponível'}</strong><small>{bunoHealth.bridge_mode}</small></div>}</Panel><Panel title="Segurança" subtitle="Controles que permanecem sempre ativos" icon={ShieldCheck}><ul className="security-list"><li>Deny-by-default</li><li>One-shot approval</li><li>Revalidação antes da execução</li><li>Emergency stop global</li><li>Isolamento por usuário</li></ul><button className="danger-ghost wide" onClick={() => void run('/api/stop')}><CircleStop size={16}/> Parar tudo agora</button></Panel></div></>}
    </main>
  </div>;
}

function Metric({ icon: Icon, label, value, note }: { icon: typeof Home; label: string; value: string; note: string }) {
  return <article className="metric"><div className="metric-head"><Icon size={15}/><span>{label}</span></div><strong>{value}</strong><small>{note}</small></article>;
}
function Panel({ title, subtitle, icon: Icon, children }: { title: string; subtitle: string; icon: typeof Home; children: ReactNode }) {
  return <section className="panel"><div className="panel-heading"><div className="panel-icon"><Icon size={18}/></div><div><h3>{title}</h3><p>{subtitle}</p></div></div>{children}</section>;
}
function Empty({ icon: Icon, title, text }: { icon: typeof Home; title: string; text: string }) {
  return <div className="empty-state"><div><Icon size={20}/></div><strong>{title}</strong><p>{text}</p></div>;
}
function SearchBox({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return <label className="search-box"><Search size={16}/><input value={value} onChange={e => onChange(e.target.value)} placeholder="Buscar…"/></label>;
}
function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return <button className="toggle-row" onClick={() => onChange(!checked)}><span>{label}</span><i className={checked ? 'toggle on' : 'toggle'}><b/></i></button>;
}
function approvalRisk(item: Pending) {
  const text = `${item.kind} ${item.description} ${item.target}`.toLowerCase();
  if (/(delete|excluir|remove|apagar|push|deploy|publish|publicar|send|enviar|pay|pagar|password|senha|credential|token)/.test(text)) return { level: 'HIGH', label: 'Alto impacto', cls: 'high' };
  if (/(write|edit|alter|terminal|execute|run|launch|abrir|invoke|set_text|criar|create|move|copy)/.test(text)) return { level: 'MEDIUM', label: 'Altera estado', cls: 'medium' };
  return { level: 'LOW', label: 'Baixo impacto', cls: 'low' };
}
function ApprovalCard({ item, onApprove, onDeny }: { item: Pending; onApprove: () => void; onDeny: () => void }) {
  const risk = approvalRisk(item);
  const expiresIn = Math.max(0, Math.round(item.expires_at - Date.now() / 1000));
  return <article className={`approval-card approval-${risk.cls}`}>
    <div className="approval-top"><div className="approval-title-row"><span className="approval-kind">{item.kind}</span><span className={`risk-badge ${risk.cls}`}>{risk.level}</span></div><small>{expiresIn ? `expira em ~${Math.ceil(expiresIn / 60)} min` : shortId(item.id)}</small></div>
    <h3>{item.description}</h3>
    <div className="approval-facts"><div><span>ALVO</span><strong>{item.target || 'Não informado'}</strong></div><div><span>IMPACTO</span><strong>{risk.label}</strong></div><div><span>ESCOPO</span><strong>Uma execução</strong></div></div>
    <div className="approval-safety"><LockKeyhole size={14}/><div><strong>Autorização vinculada a esta ação</strong><small>Se alvo ou parâmetros mudarem, esta aprovação deixa de ser válida.</small></div></div>
    <div className="approval-fingerprint"><LockKeyhole size={13}/> fingerprint {shortId(item.fingerprint)}</div>
    <div className="approval-actions"><button className="approve" onClick={onApprove}><Check size={16}/> Autorizar uma vez</button><button className="deny" onClick={onDeny}><X size={16}/> Negar</button></div>
  </article>;
}
function MissionCard({ mission, intelligence, onLoadIntelligence, onVerify, onCancel }: { mission: Mission; intelligence?: MissionIntelligence; onLoadIntelligence: () => void; onVerify: (v: boolean) => void; onCancel: () => void }) {
  const done = mission.steps.filter(s => ['completed', 'verified', 'verified_by_user', 'verified_automatically'].includes(s.status)).length;
  const pct = mission.steps.length ? Math.round(done / mission.steps.length * 100) : 0;
  return <article className="mission-card"><div className="mission-head"><div><span className="mission-state">{missionStatus[mission.status] || mission.status}</span><h3>{mission.title}</h3><small>{shortId(mission.id)}</small></div><strong>{pct}%</strong></div><div className="progress"><span style={{ width: `${pct}%` }}/></div><div className="steps">{mission.steps.map(s => <div className={`step ${s.status}`} key={`${mission.id}-${s.index}`}><span>{s.index + 1}</span><div><strong>{s.description}</strong><small>{s.kind} · {missionStatus[s.status] || s.status}</small>{s.result && <small>{s.result}</small>}</div></div>)}</div>{mission.status === 'completed' && <div className="mission-result"><Check size={17}/><div><strong>Resultado pronto</strong><p>{mission.steps.filter(s => s.result).slice(-1)[0]?.result || 'A missão foi concluída e verificada.'}</p></div></div>}<div className="mission-actions"><button className="mini-button" onClick={onLoadIntelligence}><Eye size={14}/> Evidências</button>{mission.status === 'awaiting_verification' && <><button className="approve" onClick={() => onVerify(true)}><Check size={15}/> Confirmar resultado</button><button className="deny" onClick={() => onVerify(false)}><X size={15}/> Resultado incorreto</button></>} {!['completed', 'cancelled', 'failed'].includes(mission.status) && <button className="text-danger" onClick={onCancel}>Cancelar missão</button>}</div>{intelligence && <div className="plan-result"><strong>Mission Intelligence</strong><span>{intelligence.planner}{intelligence.agent_id ? ` · ${intelligence.agent_id}` : ''}</span><p>{intelligence.reason_summary || 'Sem justificativa resumida registrada.'}</p><div className="chip-row"><span className="chip">{intelligence.selected_memory_ids.length} memória(s)</span><span className="chip">{intelligence.events.length} evidência(s)</span><span className="chip">chain-of-thought: oculto</span></div><div className="timeline">{intelligence.events.slice(-8).reverse().map(e => <div className="timeline-item" key={e.id}><span className={`event-dot ${e.outcome}`}/><time>{new Date(e.created_at).toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'})}</time><p><strong>{e.phase}</strong> · {e.summary}</p></div>)}</div></div>}</article>;
}
