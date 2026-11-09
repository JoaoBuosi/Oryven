import csv
from pathlib import Path
import pytest

from oryven.models import ProfessionalActionIntent
from oryven.professional_runtime import ProfessionalRuntime, ProfessionalRuntimeError
from oryven.work_runtime import WorkRuntime


def runtime(tmp_path):
    root=tmp_path/'work'; root.mkdir(); return ProfessionalRuntime(WorkRuntime((root,))), root


def test_office_real_files(tmp_path):
    rt,root=runtime(tmp_path)
    rt.execute(ProfessionalActionIntent(action='documents.docx.compose',workspace=str(root),arguments={'path':'r.docx','title':'Report','sections':[{'title':'A','body':'B'}]}))
    rt.execute(ProfessionalActionIntent(action='spreadsheet.xlsx.create',workspace=str(root),arguments={'path':'book.xlsx','sheets':[{'name':'Data','headers':['a','b'],'rows':[[1,2],[3,4]]}]}))
    rt.execute(ProfessionalActionIntent(action='presentation.pptx.compose',workspace=str(root),arguments={'path':'deck.pptx','title':'Deck','sections':[{'title':'S1','body':'Body'}]}))
    rt.execute(ProfessionalActionIntent(action='pdf.compose',workspace=str(root),arguments={'path':'report.pdf','title':'PDF','sections':[{'title':'One','body':'Hello'}]}))
    for name in ['r.docx','book.xlsx','deck.pptx','report.pdf']:
        assert (root/name).exists() and (root/name).stat().st_size > 100
    analysis=rt.execute(ProfessionalActionIntent(action='spreadsheet.xlsx.analyze',workspace=str(root),arguments={'path':'book.xlsx'}))
    assert analysis['data']['sheet_count']==1


def test_creative_engineering_inventory_and_script_prepare(tmp_path):
    rt,root=runtime(tmp_path); (root/'assets').mkdir()
    for name in ['model.dwg','building.ifc','clip.mp4']:
        (root/'assets'/name).write_bytes(b'x')
    assert rt.execute(ProfessionalActionIntent(action='cad.assets.inspect',workspace=str(root),arguments={'path':'assets'}))['data']['count']==1
    assert rt.execute(ProfessionalActionIntent(action='bim.assets.inspect',workspace=str(root),arguments={'path':'assets'}))['data']['count']==1
    assert rt.execute(ProfessionalActionIntent(action='media.assets.inspect',workspace=str(root),arguments={'path':'assets'}))['data']['count']==1
    rt.execute(ProfessionalActionIntent(action='blender.assist',workspace=str(root),arguments={'output':'tools/a.py','script':'print(1)'}))
    assert 'review' in (root/'tools/a.py').read_text(encoding='utf-8')


def test_external_execute_requires_tool(tmp_path, monkeypatch):
    rt,root=runtime(tmp_path); (root/'x.py').write_text('print(1)',encoding='utf-8')
    monkeypatch.delenv('ORYVEN_BLENDER_EXECUTABLE',raising=False)
    monkeypatch.setattr('oryven.professional_runtime.shutil.which', lambda x: None)
    with pytest.raises(ProfessionalRuntimeError):
        rt.execute(ProfessionalActionIntent(action='blender.execute',workspace=str(root),arguments={'path':'x.py'}))


def write_csv(path, headers, rows):
    with path.open('w',encoding='utf-8',newline='') as fh:
        w=csv.writer(fh); w.writerow(headers); w.writerows(rows)


def test_business_packs(tmp_path):
    rt,root=runtime(tmp_path)
    write_csv(root/'catalog.csv',['sku','title','price'],[['1','A','10'],['1','A','10']])
    audit=rt.execute(ProfessionalActionIntent(action='ecommerce.catalog.audit',workspace=str(root),arguments={'path':'catalog.csv'}))
    assert audit['data']['duplicate_rows']==1 and 'stock' in audit['data']['missing_recommended_columns']
    write_csv(root/'crm.csv',['status','amount'],[['lead','10'],['won','20'],['won','5']])
    crm=rt.execute(ProfessionalActionIntent(action='crm.pipeline.analyze',workspace=str(root),arguments={'path':'crm.csv','status_column':'status','amount_column':'amount'}))
    assert crm['data']['stages']['won']==2 and crm['data']['amount_by_stage']['won']==25
    rt.execute(ProfessionalActionIntent(action='marketing.plan',workspace=str(root),arguments={'path':'marketing.md','objective':'Launch','audience':'SMB','channels':['LinkedIn','Email']}))
    rt.execute(ProfessionalActionIntent(action='operations.sop.compose',workspace=str(root),arguments={'path':'sop.md','title':'Orders','sections':[{'title':'Check','body':'Validate'}]}))
    assert (root/'marketing.md').exists() and (root/'sop.md').exists()


def test_hr_support_and_accounting_are_non_decision_support(tmp_path):
    rt,root=runtime(tmp_path)
    write_csv(root/'people.csv',['name','department'],[['A','X'],['B','Y']])
    hr=rt.execute(ProfessionalActionIntent(action='hr.organize',workspace=str(root),arguments={'path':'people.csv'}))
    assert 'sem ranking' in hr['data']['note']
    write_csv(root/'tickets.csv',['id','priority'],[['1','high'],['2','low']])
    support=rt.execute(ProfessionalActionIntent(action='support.triage',workspace=str(root),arguments={'path':'tickets.csv'}))
    assert 'nenhuma resposta' in support['data']['note'].lower()
    write_csv(root/'ledger.csv',['id','amount'],[['1','10'],['1','10'],['2','20']])
    preview=rt.execute(ProfessionalActionIntent(action='accounting.reconcile.preview',workspace=str(root),arguments={'path':'ledger.csv','output':'preview.csv'}))
    assert preview['data']['duplicates_flagged']==1 and (root/'preview.csv').exists()
