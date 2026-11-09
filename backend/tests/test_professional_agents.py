import pytest

from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.professional_agents import ProfessionalAgentRegistry


class QuietSpeaker:
    enabled = False
    provider = "test"
    speaking = False
    def say(self, message): pass
    def stop(self): pass


class QuietListener:
    running = False
    def start(self): self.running = True
    def stop(self): self.running = False


def test_catalog_is_broad_and_has_universal_fallback():
    registry = ProfessionalAgentRegistry()
    agents = registry.list()
    ids = {a["id"] for a in agents}
    assert len(agents) >= 25
    assert "software.engineering" in ids
    assert "finance.analysis" in ids
    assert "three_d.maya" in ids
    assert "healthcare.admin" in ids
    assert "general.professional" in ids


@pytest.mark.parametrize("objective,expected", [
    ("corrija esse backend Python e rode os testes", "software.engineering"),
    ("prepare uma campanha de marketing para o lançamento", "marketing.growth"),
    ("analise nosso fluxo de caixa e orçamento", "finance.analysis"),
    ("organize a cena no Maya e prepare o render", "three_d.maya"),
    ("monte um dashboard SQL com nossos dados", "data.analytics"),
    ("organize a operação do hospital e indicadores do SUS", "healthcare.admin"),
])
def test_router_selects_professional_domain(objective, expected):
    route = ProfessionalAgentRegistry().route(objective)
    assert route.agent_id == expected
    assert route.confidence >= 0.58


def test_unknown_profession_falls_back_without_permissions():
    plan = ProfessionalAgentRegistry().plan("organize esta tarefa extremamente específica e nova")
    assert plan["route"]["agent_id"] == "general.professional"
    assert plan["execution_policy"]["permissions_granted"] is False
    assert plan["execution_policy"]["side_effects"] is False


def test_explicit_agent_selection_does_not_grant_permissions():
    plan = ProfessionalAgentRegistry().plan("faça a tarefa", preferred_agent_id="legal.operations")
    assert plan["route"]["agent_id"] == "legal.operations"
    assert plan["route"]["confidence"] == 1.0
    assert plan["execution_policy"]["permissions_granted"] is False


def test_core_exposes_professional_planning(tmp_path):
    core = OryvenCore(Settings(data_dir=tmp_path / "data", model_dir=tmp_path / "model"),
                      speaker=QuietSpeaker(), listener=QuietListener())
    plan = core.professional_plan("crie um projeto React e uma API")
    assert plan["route"]["agent_id"] == "software.engineering"
    assert "filesystem" in plan["recommended_tool_families"]
    assert "professional.agents" in core.status()["capabilities"]
