"""Universal professional-agent catalog and deterministic routing for Oryven.

The catalog describes *roles*, not unrestricted executors. Agents never gain permissions
by being selected; execution still goes through Oryven skills, governance and one-shot
approvals. Unknown domains fall back to a general professional profile so the runtime
is extensible without pretending every application is deeply supported on day one.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field


class ProfessionalAgentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=80)
    sector: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=8, max_length=500)
    expertise: list[str] = Field(min_length=1)
    preferred_tools: list[str] = Field(default_factory=list)
    high_risk_boundaries: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list, exclude=True)
    stage: str = "mvp"


@dataclass(frozen=True)
class AgentRoute:
    agent_id: str
    name: str
    sector: str
    confidence: float
    matched_terms: tuple[str, ...]
    reason: str

    def as_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "sector": self.sector,
            "confidence": self.confidence,
            "matched_terms": list(self.matched_terms),
            "reason": self.reason,
        }


def _norm(value: str) -> str:
    ascii_text = "".join(
        ch for ch in unicodedata.normalize("NFD", value.casefold())
        if unicodedata.category(ch) != "Mn"
    )
    return re.sub(r"[^a-z0-9+#.]+", " ", ascii_text).strip()


def _agent(
    id: str,
    name: str,
    sector: str,
    description: str,
    expertise: list[str],
    preferred_tools: list[str],
    keywords: list[str],
    high_risk_boundaries: list[str] | None = None,
) -> ProfessionalAgentManifest:
    return ProfessionalAgentManifest(
        id=id,
        name=name,
        sector=sector,
        description=description,
        expertise=expertise,
        preferred_tools=preferred_tools,
        keywords=keywords,
        high_risk_boundaries=high_risk_boundaries or [],
    )


# Broad first-party catalog. Deep product/application integrations are delivered as skills.
# A generic fallback is intentionally included so a new profession can be represented before
# its dedicated skill pack exists.
BUILTIN_AGENTS: tuple[ProfessionalAgentManifest, ...] = (
    _agent("software.engineering", "Software Engineering Agent", "Tecnologia",
           "Desenvolve, analisa, testa e mantém software em múltiplas linguagens e stacks.",
           ["arquitetura", "backend", "frontend", "mobile", "APIs", "debug", "testes", "code review"],
           ["filesystem", "terminal", "git", "browser", "developer_runtime"],
           ["codigo", "programacao", "python", "java", "javascript", "typescript", "react", "spring", "fastapi", "bug", "api", "software"]),
    _agent("devops.platform", "DevOps & Platform Agent", "Tecnologia",
           "Opera pipelines, builds, containers e infraestrutura de entrega de software.",
           ["CI/CD", "Docker", "cloud", "observabilidade", "release", "infraestrutura"],
           ["terminal", "git", "docker", "deploy"],
           ["deploy", "docker", "kubernetes", "ci cd", "pipeline", "infra", "vercel", "aws", "azure", "gcp"],
           ["produção", "credenciais", "custos de cloud"]),
    _agent("data.analytics", "Data & Analytics Agent", "Dados",
           "Analisa dados, prepara datasets, produz métricas, relatórios e automações analíticas.",
           ["SQL", "Python", "estatística", "ETL", "BI", "visualização", "qualidade de dados"],
           ["filesystem", "spreadsheet", "python", "database"],
           ["dados", "dataset", "sql", "dashboard", "analytics", "analise", "etl", "power bi", "estatistica"]),
    _agent("ai.ml", "AI & Machine Learning Agent", "Inteligência Artificial",
           "Projeta pipelines de ML/IA, avaliação, dados, inferência e integração de modelos.",
           ["machine learning", "LLM", "NLP", "visão computacional", "MLOps", "avaliação"],
           ["python", "filesystem", "terminal", "datasets", "model_runtime"],
           ["machine learning", "ml", "ia", "llm", "modelo", "treinar", "fine tuning", "embedding", "nlp", "visao computacional"]),
    _agent("cybersecurity.defensive", "Defensive Security Agent", "Cibersegurança",
           "Ajuda em hardening, revisão defensiva, inventário, compliance e resposta a incidentes autorizada.",
           ["hardening", "logs", "vulnerabilidades", "segurança de aplicação", "IAM"],
           ["filesystem", "terminal", "audit", "browser"],
           ["seguranca", "cyber", "vulnerabilidade", "hardening", "log", "incidente", "iam"],
           ["ações ofensivas", "credenciais", "sistemas de terceiros"]),
    _agent("office.productivity", "Office Productivity Agent", "Escritório",
           "Cria, revisa e organiza documentos, planilhas, apresentações e rotinas administrativas.",
           ["documentos", "planilhas", "apresentações", "PDF", "organização"],
           ["filesystem", "documents", "spreadsheet", "presentation"],
           ["excel", "word", "powerpoint", "planilha", "documento", "pdf", "apresentacao", "office"]),
    _agent("research.knowledge", "Research & Knowledge Agent", "Pesquisa",
           "Pesquisa, sintetiza fontes, organiza conhecimento e produz análises rastreáveis.",
           ["pesquisa", "síntese", "revisão", "fontes", "knowledge management"],
           ["browser", "documents", "knowledge"],
           ["pesquisar", "pesquisa", "artigo", "fontes", "estudo", "literatura", "revisao"]),
    _agent("education.learning", "Education & Learning Agent", "Educação",
           "Apoia estudo, ensino, planejamento de aulas e materiais educacionais.",
           ["tutoria", "currículo", "exercícios", "explicação", "avaliação formativa"],
           ["browser", "documents", "presentation"],
           ["estudar", "aula", "professor", "aluno", "curso", "prova", "educacao", "ensino"]),
    _agent("marketing.growth", "Marketing & Growth Agent", "Marketing",
           "Planeja campanhas, conteúdo, posicionamento, pesquisa de mercado e análise de performance.",
           ["conteúdo", "campanhas", "SEO", "branding", "growth", "analytics"],
           ["browser", "documents", "design", "analytics"],
           ["marketing", "campanha", "seo", "marca", "branding", "conteudo", "growth", "rede social"]),
    _agent("sales.revenue", "Sales & Revenue Agent", "Vendas",
           "Apoia prospecção, qualificação, propostas, CRM e operações comerciais.",
           ["prospecção", "CRM", "pipeline", "propostas", "forecast"],
           ["browser", "documents", "crm", "spreadsheet"],
           ["vendas", "cliente", "prospeccao", "crm", "lead", "proposta", "comercial"]),
    _agent("customer.success", "Customer Success & Support Agent", "Atendimento",
           "Ajuda em suporte, triagem, base de conhecimento e acompanhamento de clientes.",
           ["suporte", "triagem", "SLA", "CS", "base de conhecimento"],
           ["browser", "documents", "support", "knowledge"],
           ["suporte", "atendimento", "chamado", "ticket", "cliente", "customer success", "sla"]),
    _agent("finance.analysis", "Finance Analysis Agent", "Finanças",
           "Apoia orçamento, análise financeira, cenários e relatórios sem movimentar fundos autonomamente.",
           ["orçamento", "fluxo de caixa", "forecast", "KPIs", "modelagem financeira"],
           ["spreadsheet", "documents", "analytics"],
           ["financas", "financeiro", "orcamento", "fluxo de caixa", "receita", "despesa", "forecast"],
           ["transferências", "investimentos", "pagamentos"]),
    _agent("accounting.operations", "Accounting Operations Agent", "Contabilidade",
           "Organiza documentos contábeis, conciliações auxiliares e relatórios para revisão humana.",
           ["conciliação", "documentos fiscais", "classificação", "relatórios"],
           ["documents", "spreadsheet", "filesystem"],
           ["contabilidade", "contabil", "nota fiscal", "conciliacao", "balancete", "fiscal"],
           ["declarações oficiais", "envio fiscal"]),
    _agent("legal.operations", "Legal Operations Agent", "Jurídico",
           "Auxilia organização, pesquisa e preparação documental jurídica para revisão profissional.",
           ["legal ops", "contratos", "pesquisa", "document review", "compliance"],
           ["documents", "browser", "knowledge"],
           ["juridico", "legal", "contrato", "clausula", "compliance", "processo juridico"],
           ["aconselhamento jurídico definitivo", "peticionamento sem revisão"]),
    _agent("people.hr", "People & HR Agent", "Recursos Humanos",
           "Apoia recrutamento, onboarding, políticas internas e operações de pessoas.",
           ["recrutamento", "onboarding", "descrição de vaga", "políticas", "people analytics"],
           ["documents", "spreadsheet", "browser"],
           ["rh", "recursos humanos", "vaga", "recrutamento", "curriculo", "onboarding", "people"]),
    _agent("operations.business", "Business Operations Agent", "Operações",
           "Mapeia processos, organiza rotinas, indicadores e execução operacional.",
           ["processos", "SOP", "KPIs", "automação", "planejamento operacional"],
           ["documents", "spreadsheet", "browser", "automation"],
           ["operacoes", "processo", "rotina", "sop", "kpi", "operacional", "automacao"]),
    _agent("project.management", "Project Management Agent", "Gestão de Projetos",
           "Planeja escopo, cronograma, riscos, dependências e acompanhamento de projetos.",
           ["planejamento", "cronograma", "riscos", "backlog", "status report"],
           ["documents", "spreadsheet", "project_tools"],
           ["projeto", "cronograma", "backlog", "sprint", "risco", "prazo", "project manager"]),
    _agent("product.management", "Product Management Agent", "Produto",
           "Apoia discovery, requisitos, roadmap, métricas e especificação de produto.",
           ["discovery", "PRD", "roadmap", "métricas", "UX", "priorização"],
           ["documents", "browser", "analytics", "project_tools"],
           ["produto", "prd", "roadmap", "feature", "usuario", "discovery", "product manager"]),
    _agent("design.creative", "Design & Creative Agent", "Design",
           "Apoia criação visual, organização de assets, briefs e fluxos de design.",
           ["design gráfico", "UI", "UX", "identidade visual", "assets"],
           ["design", "filesystem", "browser", "image_tools"],
           ["design", "figma", "photoshop", "illustrator", "ui", "ux", "logo", "layout"]),
    _agent("three_d.maya", "3D & Maya Agent", "3D",
           "Apoia modelagem, cenas, materiais, scripts e renderização em pipelines 3D.",
           ["Maya", "Python", "MEL", "cenas", "materiais", "render", "pipeline 3D"],
           ["maya", "filesystem", "python", "ui_automation"],
           ["maya", "3d", "modelagem", "render", "material", "mel", "blender", "cinema 4d"]),
    _agent("media.audiovisual", "Audiovisual Production Agent", "Audiovisual",
           "Apoia organização de mídia, roteiros, edição e fluxos de produção audiovisual.",
           ["roteiro", "edição", "mídia", "produção", "pós-produção"],
           ["filesystem", "documents", "media_tools", "ui_automation"],
           ["video", "audio", "audiovisual", "premiere", "davinci", "after effects", "edicao", "roteiro"]),
    _agent("ecommerce.operations", "E-commerce Operations Agent", "E-commerce",
           "Opera catálogo, pedidos, conteúdo, análise e rotinas de comércio eletrônico supervisionadas.",
           ["catálogo", "pedidos", "pricing", "marketplaces", "conversão"],
           ["browser", "spreadsheet", "commerce", "analytics"],
           ["ecommerce", "loja", "produto", "catalogo", "pedido", "marketplace", "shopify", "mercado livre"]),
    _agent("logistics.supply", "Logistics & Supply Agent", "Logística",
           "Apoia estoque, transporte, roteirização, fornecedores e indicadores logísticos.",
           ["estoque", "transporte", "roteirização", "SLA", "supply chain"],
           ["spreadsheet", "documents", "browser", "erp"],
           ["logistica", "estoque", "frete", "transporte", "supply", "fornecedor", "armazem"]),
    _agent("procurement.sourcing", "Procurement Agent", "Compras",
           "Apoia cotações, comparação de fornecedores, documentação e acompanhamento de compras.",
           ["sourcing", "cotação", "fornecedores", "compras", "TCO"],
           ["browser", "documents", "spreadsheet"],
           ["compras", "cotacao", "fornecedor", "procurement", "sourcing", "preco"]),
    _agent("engineering.general", "Engineering Agent", "Engenharia",
           "Apoia cálculos, documentação, pesquisa técnica e organização de projetos de engenharia.",
           ["requisitos", "cálculos", "documentação técnica", "CAD workflows", "análise"],
           ["documents", "spreadsheet", "browser", "engineering_tools"],
           ["engenharia", "engenheiro", "calculo", "cad", "solidworks", "autocad", "tecnico"]),
    _agent("architecture.bim", "Architecture & BIM Agent", "Arquitetura",
           "Apoia documentação, pesquisa, organização e automações em fluxos de arquitetura/BIM.",
           ["BIM", "documentação", "CAD", "modelagem", "coordenação"],
           ["documents", "filesystem", "ui_automation", "bim_tools"],
           ["arquitetura", "arquiteto", "revit", "bim", "autocad", "planta", "projeto arquitetonico"]),
    _agent("science.research", "Science Research Agent", "Ciência",
           "Apoia análise, experimentação computacional, revisão e documentação científica.",
           ["método científico", "dados", "literatura", "reprodutibilidade", "notebooks"],
           ["browser", "python", "documents", "datasets"],
           ["ciencia", "cientifico", "experimento", "paper", "laboratorio", "pesquisa cientifica"]),
    _agent("healthcare.admin", "Healthcare Operations Agent", "Saúde",
           "Apoia tarefas administrativas, dados e documentação de saúde sem substituir decisão clínica.",
           ["operações hospitalares", "dados", "documentação", "qualidade", "SUS"],
           ["documents", "spreadsheet", "analytics"],
           ["saude", "hospital", "paciente", "sus", "clinica", "hemodialise", "medicina"],
           ["diagnóstico", "prescrição", "decisão clínica autônoma"]),
    _agent("realestate.operations", "Real Estate Agent", "Imobiliário",
           "Apoia pesquisa de imóveis, documentação, comparação e operações imobiliárias.",
           ["pesquisa", "comparação", "documentação", "CRM imobiliário"],
           ["browser", "documents", "spreadsheet", "crm"],
           ["imovel", "imobiliaria", "aluguel", "venda de imovel", "corretor", "real estate"]),
    _agent("hospitality.travel", "Hospitality & Travel Operations Agent", "Hospitalidade e Turismo",
           "Apoia pesquisa, roteiros, reservas e operações de hospitalidade supervisionadas.",
           ["roteiros", "reservas", "atendimento", "pesquisa", "operações"],
           ["browser", "documents", "calendar"],
           ["viagem", "hotel", "turismo", "roteiro", "reserva", "hospitalidade"]),
    _agent("manufacturing.operations", "Manufacturing Operations Agent", "Indústria",
           "Apoia documentação, qualidade, produção, manutenção e análise operacional industrial.",
           ["produção", "qualidade", "manutenção", "OEE", "processos"],
           ["documents", "spreadsheet", "analytics", "erp"],
           ["industria", "fabrica", "producao", "manutencao", "oee", "manufacturing"]),
    _agent("general.professional", "Universal Professional Agent", "Geral",
           "Perfil universal para tarefas profissionais ainda sem agente especializado dedicado.",
           ["planejamento", "pesquisa", "documentação", "organização", "coordenação de skills"],
           ["browser", "filesystem", "documents", "ui_automation"],
           ["trabalho", "profissional", "ajuda", "tarefa"]),
)


class ProfessionalAgentRegistry:
    def __init__(self, agents: Iterable[ProfessionalAgentManifest] = BUILTIN_AGENTS):
        self._agents = {agent.id: agent for agent in agents}
        if "general.professional" not in self._agents:
            raise ValueError("Catálogo precisa de general.professional.")

    def list(self) -> list[dict]:
        return [self._agents[key].model_dump(exclude={"keywords"}) for key in sorted(self._agents)]

    def get(self, agent_id: str) -> dict:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise KeyError("Agente profissional não encontrado.")
        return agent.model_dump(exclude={"keywords"})

    def route(self, objective: str, preferred_agent_id: str | None = None) -> AgentRoute:
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("Objetivo profissional não pode estar vazio.")
        if preferred_agent_id:
            agent = self._agents.get(preferred_agent_id)
            if agent is None:
                raise KeyError("Agente profissional solicitado não existe.")
            return AgentRoute(agent.id, agent.name, agent.sector, 1.0, (), "Agente escolhido explicitamente pelo usuário.")

        normalized = _norm(objective)
        padded = f" {normalized} "
        best: tuple[float, ProfessionalAgentManifest, tuple[str, ...]] | None = None
        for agent in self._agents.values():
            if agent.id == "general.professional":
                continue
            matches = []
            score = 0.0
            for keyword in agent.keywords:
                key = _norm(keyword)
                if key and f" {key} " in padded:
                    matches.append(keyword)
                    score += 2.0 if " " in key else 1.0
            for term in agent.expertise:
                key = _norm(term)
                if key and f" {key} " in padded:
                    score += 0.5
            if score and (best is None or score > best[0]):
                best = (score, agent, tuple(matches))

        if best is None:
            agent = self._agents["general.professional"]
            return AgentRoute(agent.id, agent.name, agent.sector, 0.35, (), "Nenhuma especialidade dedicada atingiu correspondência segura; usando perfil universal.")
        score, agent, matches = best
        confidence = min(0.98, 0.58 + score * 0.08)
        return AgentRoute(agent.id, agent.name, agent.sector, round(confidence, 3), matches,
                          "Especialidade selecionada por correspondência local de domínio; isso não concede permissões.")

    def plan(self, objective: str, preferred_agent_id: str | None = None) -> dict:
        route = self.route(objective, preferred_agent_id)
        agent = self._agents[route.agent_id]
        return {
            "objective": objective.strip(),
            "route": route.as_dict(),
            "agent": agent.model_dump(exclude={"keywords"}),
            "execution_policy": {
                "permissions_granted": False,
                "side_effects": False,
                "rule": "Toda ferramenta executável continua exigindo a governança e a autorização aplicáveis.",
            },
            "recommended_tool_families": list(agent.preferred_tools),
            "boundaries": list(agent.high_risk_boundaries),
        }
