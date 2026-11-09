"""Deterministic professional skill-pack runtime for Oryven 0.11.

This runtime intentionally starts with local, auditable operations that can be
verified without trusting an LLM: documents, CSV analytics, dataset preparation,
asset inventory, read-only SQLite queries, knowledge indexing and Maya script
preparation. Every action is still proposed through ApprovalStore before execution.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import os
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ProfessionalActionIntent
from .work_runtime import WorkRuntime, WorkRuntimeError


class ProfessionalRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class ProfessionalResult:
    action: str
    workspace: str
    target: str
    data: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "workspace": self.workspace,
            "target": self.target,
            "data": self.data,
        }


class ProfessionalRuntime:
    MAX_CSV_BYTES = 5_000_000
    MAX_ROWS = 50_000
    MAX_TEXT_BYTES = 1_000_000
    ASSET_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp4", ".mov",
        ".wav", ".mp3", ".fbx", ".obj", ".ma", ".mb", ".blend", ".psd", ".ai",
        ".dwg", ".dxf", ".rvt", ".rfa", ".ifc", ".step", ".stp", ".iges", ".igs",
    }

    def __init__(self, work: WorkRuntime):
        self.work = work

    def _workspace(self, raw: str) -> Path:
        return self.work._workspace(raw)

    def _target(self, workspace: Path, raw: str, must_exist: bool | None = None) -> Path:
        return self.work._target(workspace, raw, must_exist=must_exist)

    @staticmethod
    def _safe_text(value: Any, limit: int = 8000) -> str:
        text = "" if value is None else str(value)
        return text if len(text) <= limit else text[:limit]

    def validate(self, intent: ProfessionalActionIntent) -> None:
        workspace = self._workspace(intent.workspace)
        action = intent.action
        args = intent.arguments
        if action == "documents.compose":
            path = str(args.get("path", "")).strip()
            content = args.get("content")
            if not path or not isinstance(content, str):
                raise ProfessionalRuntimeError("documents.compose exige path e content.")
            target = self._target(workspace, path)
            if target.suffix.lower() not in {".md", ".txt"}:
                raise ProfessionalRuntimeError("documents.compose aceita apenas .md ou .txt nesta versão.")
            return
        if action in {"spreadsheet.analyze", "analytics.analyze", "datasets.prepare"}:
            path = str(args.get("path", "")).strip()
            if not path:
                raise ProfessionalRuntimeError(f"{action} exige path.")
            target = self._target(workspace, path, must_exist=True)
            if target.suffix.lower() != ".csv":
                raise ProfessionalRuntimeError(f"{action} aceita CSV nesta versão.")
            if target.stat().st_size > self.MAX_CSV_BYTES:
                raise ProfessionalRuntimeError("CSV excede 5 MB nesta versão.")
            if action == "datasets.prepare":
                output = str(args.get("output", "")).strip()
                if not output:
                    raise ProfessionalRuntimeError("datasets.prepare exige output.")
                out = self._target(workspace, output)
                if out.suffix.lower() != ".csv":
                    raise ProfessionalRuntimeError("datasets.prepare exige output .csv.")
            return
        if action == "design.assist":
            path = str(args.get("path", ".")).strip() or "."
            target = self._target(workspace, path, must_exist=True)
            if not target.is_dir():
                raise ProfessionalRuntimeError("design.assist exige uma pasta de assets.")
            return
        if action == "database.query":
            path = str(args.get("path", "")).strip()
            query = str(args.get("query", "")).strip()
            if not path or not query:
                raise ProfessionalRuntimeError("database.query exige path e query.")
            target = self._target(workspace, path, must_exist=True)
            if target.suffix.lower() not in {".sqlite", ".sqlite3", ".db"}:
                raise ProfessionalRuntimeError("database.query aceita apenas SQLite local nesta versão.")
            normalized = query.lstrip().casefold()
            if not normalized.startswith("select") and not normalized.startswith("with") and not normalized.startswith("pragma"):
                raise ProfessionalRuntimeError("database.query é somente leitura nesta versão.")
            blocked = ("insert ", "update ", "delete ", "drop ", "alter ", "create ", "attach ", "detach ", "vacuum ", "replace ")
            folded = f" {query.casefold()} "
            if any(token in folded for token in blocked):
                raise ProfessionalRuntimeError("Comando SQLite de escrita não é permitido.")
            return
        if action == "knowledge.organize":
            path = str(args.get("path", ".")).strip() or "."
            target = self._target(workspace, path, must_exist=True)
            if not target.is_dir():
                raise ProfessionalRuntimeError("knowledge.organize exige uma pasta.")
            return
        if action == "maya.assist":
            output = str(args.get("output", "")).strip()
            language = str(args.get("language", "python")).strip().casefold()
            script = args.get("script")
            if not output or not isinstance(script, str) or language not in {"python", "mel"}:
                raise ProfessionalRuntimeError("maya.assist exige output, script e language=python|mel.")
            target = self._target(workspace, output)
            expected = ".py" if language == "python" else ".mel"
            if target.suffix.lower() != expected:
                raise ProfessionalRuntimeError(f"maya.assist exige arquivo {expected} para {language}.")
            return
        if action == "presentation.compose":
            path = str(args.get("path", "")).strip()
            title = str(args.get("title", "")).strip()
            sections = args.get("sections")
            if not path or not title or not isinstance(sections, list) or not sections:
                raise ProfessionalRuntimeError("presentation.compose exige path, title e sections.")
            target = self._target(workspace, path)
            if target.suffix.lower() != ".md":
                raise ProfessionalRuntimeError("presentation.compose gera outline .md nesta versão.")
            return
        if action == "documents.docx.compose":
            path=str(args.get("path","")).strip(); title=str(args.get("title","")).strip(); sections=args.get("sections")
            if not path or not title or not isinstance(sections,list): raise ProfessionalRuntimeError("documents.docx.compose exige path, title e sections.")
            if self._target(workspace,path).suffix.lower() != ".docx": raise ProfessionalRuntimeError("Saída deve ser .docx.")
            return
        if action == "spreadsheet.xlsx.create":
            path=str(args.get("path","")).strip(); sheets=args.get("sheets")
            if not path or not isinstance(sheets,list) or not sheets: raise ProfessionalRuntimeError("spreadsheet.xlsx.create exige path e sheets.")
            if self._target(workspace,path).suffix.lower() != ".xlsx": raise ProfessionalRuntimeError("Saída deve ser .xlsx.")
            return
        if action in {"spreadsheet.xlsx.analyze","finance.workbook.analyze"}:
            path=str(args.get("path","")).strip(); target=self._target(workspace,path,must_exist=True)
            if target.suffix.lower() != ".xlsx": raise ProfessionalRuntimeError(f"{action} aceita XLSX.")
            if target.stat().st_size > 10_000_000: raise ProfessionalRuntimeError("XLSX excede 10 MB nesta versão.")
            return
        if action == "office.report.from.xlsx":
            path=str(args.get("path","")).strip(); output=str(args.get("output","")).strip()
            source=self._target(workspace,path,must_exist=True); target=self._target(workspace,output)
            if source.suffix.lower() != ".xlsx": raise ProfessionalRuntimeError("office.report.from.xlsx exige source .xlsx.")
            if target.suffix.lower() != ".docx": raise ProfessionalRuntimeError("office.report.from.xlsx exige output .docx.")
            if source.stat().st_size > 10_000_000: raise ProfessionalRuntimeError("XLSX excede 10 MB nesta versão.")
            return
        if action == "office.open.document":
            path=str(args.get("path","")).strip()
            if not path: raise ProfessionalRuntimeError("office.open.document exige path.")
            target=self._target(workspace,path)
            if target.suffix.lower() not in {".xlsx",".docx",".pptx",".pdf"}:
                raise ProfessionalRuntimeError("office.open.document aceita XLSX, DOCX, PPTX ou PDF.")
            return
        if action == "presentation.pptx.compose":
            path=str(args.get("path","")).strip(); title=str(args.get("title","")).strip(); sections=args.get("sections")
            if not path or not title or not isinstance(sections,list): raise ProfessionalRuntimeError("presentation.pptx.compose exige path, title e sections.")
            if self._target(workspace,path).suffix.lower() != ".pptx": raise ProfessionalRuntimeError("Saída deve ser .pptx.")
            return
        if action == "pdf.compose":
            path=str(args.get("path","")).strip(); title=str(args.get("title","")).strip(); sections=args.get("sections")
            if not path or not title or not isinstance(sections,list): raise ProfessionalRuntimeError("pdf.compose exige path, title e sections.")
            if self._target(workspace,path).suffix.lower() != ".pdf": raise ProfessionalRuntimeError("Saída deve ser .pdf.")
            return
        if action in {"maya.execute","blender.execute"}:
            path=str(args.get("path","")).strip(); target=self._target(workspace,path,must_exist=True)
            if action=="maya.execute" and target.suffix.lower() not in {".py",".mel"}: raise ProfessionalRuntimeError("maya.execute aceita .py ou .mel.")
            if action=="blender.execute" and target.suffix.lower() != ".py": raise ProfessionalRuntimeError("blender.execute aceita .py.")
            return
        if action == "blender.assist":
            output=str(args.get("output","")).strip(); script=args.get("script")
            if not output or not isinstance(script,str) or self._target(workspace,output).suffix.lower() != ".py": raise ProfessionalRuntimeError("blender.assist exige output .py e script.")
            return
        if action in {"cad.assets.inspect","bim.assets.inspect","media.assets.inspect"}:
            target=self._target(workspace,str(args.get("path",".") or "."),must_exist=True)
            if not target.is_dir(): raise ProfessionalRuntimeError(f"{action} exige pasta.")
            return
        if action in {"marketing.plan","operations.sop.compose"}:
            path=str(args.get("path","")).strip(); target=self._target(workspace,path)
            if target.suffix.lower() not in {".md",".txt"}: raise ProfessionalRuntimeError(f"{action} exige .md ou .txt.")
            return
        if action in {"ecommerce.catalog.audit","crm.pipeline.analyze","logistics.analyze","hr.organize","support.triage","accounting.reconcile.preview"}:
            path=str(args.get("path","")).strip(); target=self._target(workspace,path,must_exist=True)
            if target.suffix.lower() != ".csv": raise ProfessionalRuntimeError(f"{action} exige CSV.")
            if action=="accounting.reconcile.preview":
                output=str(args.get("output","")).strip()
                if not output or self._target(workspace,output).suffix.lower() != ".csv": raise ProfessionalRuntimeError("accounting.reconcile.preview exige output .csv.")
            return
        raise ProfessionalRuntimeError("Ação profissional não suportada.")

    def _write_text(self, workspace: Path, path: str, content: str, action: str) -> dict:
        from .models import WorkActionIntent
        data = self.work.execute(WorkActionIntent(
            action="filesystem.write_text", workspace=str(workspace), path=path, content=content
        ))
        return ProfessionalResult(action, str(workspace), path, data).as_dict()

    def _read_csv(self, target: Path) -> tuple[list[str], list[dict[str, str]]]:
        try:
            with target.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                headers = list(reader.fieldnames or [])
                rows: list[dict[str, str]] = []
                for index, row in enumerate(reader):
                    if index >= self.MAX_ROWS:
                        raise ProfessionalRuntimeError("CSV excede 50.000 linhas nesta versão.")
                    rows.append({k: "" if v is None else v for k, v in row.items() if k is not None})
        except UnicodeDecodeError as exc:
            raise ProfessionalRuntimeError("CSV deve estar em UTF-8/UTF-8 BOM.") from exc
        except OSError as exc:
            raise ProfessionalRuntimeError("Não foi possível ler o CSV.") from exc
        if not headers:
            raise ProfessionalRuntimeError("CSV sem cabeçalho.")
        return headers, rows

    @staticmethod
    def _number(value: str) -> float | None:
        raw = value.strip().replace(" ", "")
        if not raw:
            return None
        if raw.count(",") == 1 and raw.count(".") == 0:
            raw = raw.replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            return None

    def _csv_profile(self, target: Path, detailed: bool) -> dict[str, Any]:
        headers, rows = self._read_csv(target)
        columns = []
        for header in headers:
            values = [row.get(header, "") for row in rows]
            non_empty = [v for v in values if v.strip()]
            nums = [n for n in (self._number(v) for v in non_empty) if n is not None]
            item: dict[str, Any] = {
                "name": header,
                "non_empty": len(non_empty),
                "missing": len(rows) - len(non_empty),
                "unique": len(set(non_empty)),
                "numeric_ratio": round((len(nums) / len(non_empty)), 4) if non_empty else 0.0,
            }
            if nums:
                item.update({"min": min(nums), "max": max(nums), "mean": sum(nums) / len(nums)})
            if detailed and non_empty and len(set(non_empty)) <= 20:
                item["top_values"] = Counter(non_empty).most_common(5)
            columns.append(item)
        return {"rows": len(rows), "columns": columns, "headers": headers}

    @staticmethod
    def _load_office():
        try:
            import openpyxl
            from docx import Document
            from pptx import Presentation
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            return openpyxl, Document, Presentation, A4, SimpleDocTemplate, Paragraph, Spacer, getSampleStyleSheet
        except ImportError as exc:
            raise ProfessionalRuntimeError("Dependências Office ausentes. Instale requirements-professional.txt.") from exc

    def _xlsx_analysis(self, target: Path) -> dict[str, Any]:
        openpyxl, *_ = self._load_office()
        try:
            wb=openpyxl.load_workbook(target, read_only=True, data_only=False)
        except Exception as exc:
            raise ProfessionalRuntimeError("Não foi possível abrir o XLSX.") from exc
        sheets=[]
        for ws in wb.worksheets[:20]:
            rows=[]
            numeric=[]
            for ridx,row in enumerate(ws.iter_rows(values_only=True),1):
                if ridx>5000: break
                vals=list(row[:100]); rows.append(vals)
                for v in vals:
                    if isinstance(v,(int,float)) and not isinstance(v,bool): numeric.append(float(v))
            sheets.append({"name":ws.title,"rows":len(rows),"columns":max((len(r) for r in rows),default=0),
                           "numeric_count":len(numeric),"numeric_sum":sum(numeric) if numeric else 0.0})
        wb.close()
        return {"sheets":sheets,"sheet_count":len(sheets)}

    def _asset_inventory(self, workspace: Path, folder: Path, extensions: set[str], action: str) -> dict:
        items=[]
        for item in sorted(folder.rglob("*")):
            if item.is_file() and item.suffix.lower() in extensions:
                try: stat=item.stat()
                except OSError: continue
                items.append({"path":str(item.relative_to(workspace)),"extension":item.suffix.lower(),"bytes":stat.st_size})
                if len(items)>=1000: break
        return ProfessionalResult(action,str(workspace),str(folder.relative_to(workspace)),{"items":items,"count":len(items),"extensions":dict(Counter(x["extension"] for x in items))}).as_dict()

    @staticmethod
    def _resolve_executable(explicit: str, env_name: str, candidates: list[str]) -> str:
        values=[explicit, os.environ.get(env_name, ""), *candidates]
        for value in values:
            if not value: continue
            resolved=shutil.which(value) if not Path(value).is_file() else str(Path(value).resolve())
            if resolved: return resolved
        raise ProfessionalRuntimeError(f"Executável não encontrado. Configure {env_name}.")

    def _run_external(self, executable: str, argv: list[str], cwd: Path, timeout: int=120) -> dict:
        try:
            cp=subprocess.run([executable,*argv], cwd=cwd, capture_output=True, text=True, timeout=timeout, shell=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProfessionalRuntimeError("Ferramenta externa falhou ou excedeu o tempo limite.") from exc
        return {"returncode":cp.returncode,"stdout":cp.stdout[-8000:],"stderr":cp.stderr[-8000:]}

    def execute(self, intent: ProfessionalActionIntent) -> dict:
        self.validate(intent)
        workspace = self._workspace(intent.workspace)
        args = intent.arguments
        action = intent.action
        if action == "documents.compose":
            return self._write_text(workspace, str(args["path"]), str(args["content"]), action)
        if action in {"spreadsheet.analyze", "analytics.analyze"}:
            target = self._target(workspace, str(args["path"]), must_exist=True)
            profile = self._csv_profile(target, detailed=action == "analytics.analyze")
            return ProfessionalResult(action, str(workspace), str(args["path"]), profile).as_dict()
        if action == "datasets.prepare":
            source = self._target(workspace, str(args["path"]), must_exist=True)
            headers, rows = self._read_csv(source)
            cleaned: list[dict[str, str]] = []
            seen: set[tuple[str, ...]] = set()
            for row in rows:
                normalized = {h: (row.get(h, "") or "").strip() for h in headers}
                key = tuple(normalized[h] for h in headers)
                if key in seen:
                    continue
                seen.add(key)
                cleaned.append(normalized)
            out = self._target(workspace, str(args["output"]))
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                with out.open("w", encoding="utf-8", newline="") as fh:
                    writer = csv.DictWriter(fh, fieldnames=headers)
                    writer.writeheader(); writer.writerows(cleaned)
            except OSError as exc:
                raise ProfessionalRuntimeError("Não foi possível gravar o dataset preparado.") from exc
            return ProfessionalResult(action, str(workspace), str(args["output"]), {
                "source_rows": len(rows), "output_rows": len(cleaned), "duplicates_removed": len(rows)-len(cleaned),
                "headers": headers,
            }).as_dict()
        if action == "design.assist":
            target = self._target(workspace, str(args.get("path", ".")), must_exist=True)
            assets = []
            for item in sorted(target.rglob("*")):
                if not item.is_file() or item.suffix.lower() not in self.ASSET_EXTENSIONS:
                    continue
                try:
                    stat = item.stat()
                except OSError:
                    continue
                assets.append({"path": str(item.relative_to(workspace)), "extension": item.suffix.lower(), "bytes": stat.st_size})
                if len(assets) >= 500:
                    break
            return ProfessionalResult(action, str(workspace), str(target.relative_to(workspace)), {
                "assets": assets,
                "count": len(assets),
                "extensions": dict(Counter(a["extension"] for a in assets)),
            }).as_dict()
        if action == "database.query":
            target = self._target(workspace, str(args["path"]), must_exist=True)
            query = str(args["query"])
            try:
                uri = f"file:{target.as_posix()}?mode=ro"
                with sqlite3.connect(uri, uri=True, timeout=5) as db:
                    db.execute("PRAGMA query_only = ON")
                    cur = db.execute(query)
                    columns = [d[0] for d in (cur.description or [])]
                    rows = cur.fetchmany(201)
            except sqlite3.Error as exc:
                raise ProfessionalRuntimeError("Consulta SQLite falhou em modo somente leitura.") from exc
            truncated = len(rows) > 200
            rows = rows[:200]
            return ProfessionalResult(action, str(workspace), str(args["path"]), {
                "columns": columns, "rows": [list(row) for row in rows], "truncated": truncated,
            }).as_dict()
        if action == "knowledge.organize":
            target = self._target(workspace, str(args.get("path", ".")), must_exist=True)
            records = []
            allowed = {".md", ".txt", ".py", ".js", ".ts", ".tsx", ".json", ".csv"}
            for item in sorted(target.rglob("*")):
                if not item.is_file() or item.suffix.lower() not in allowed:
                    continue
                try:
                    size = item.stat().st_size
                except OSError:
                    continue
                if size > self.MAX_TEXT_BYTES:
                    continue
                records.append({"path": str(item.relative_to(workspace)), "extension": item.suffix.lower(), "bytes": size})
                if len(records) >= 1000:
                    break
            return ProfessionalResult(action, str(workspace), str(target.relative_to(workspace)), {
                "files": records, "count": len(records), "extensions": dict(Counter(r["extension"] for r in records)),
            }).as_dict()
        if action == "maya.assist":
            header = "# Generated by Oryven for manual review before Maya execution.\n" if str(args.get("language", "python")).casefold() == "python" else "// Generated by Oryven for manual review before Maya execution.\n"
            return self._write_text(workspace, str(args["output"]), header + str(args["script"]), action)
        if action == "presentation.compose":
            lines = [f"# {str(args['title']).strip()}", ""]
            for idx, section in enumerate(args["sections"], 1):
                if isinstance(section, dict):
                    title = self._safe_text(section.get("title") or f"Slide {idx}", 200)
                    body = self._safe_text(section.get("body") or "", 4000)
                else:
                    title = f"Slide {idx}"; body = self._safe_text(section, 4000)
                lines.extend([f"## {idx}. {title}", body, ""])
            return self._write_text(workspace, str(args["path"]), "\n".join(lines), action)
        if action == "documents.docx.compose":
            _, Document, *_ = self._load_office(); target=self._target(workspace,str(args["path"])); target.parent.mkdir(parents=True,exist_ok=True)
            doc=Document(); doc.add_heading(str(args["title"]),0)
            for section in args["sections"]:
                if isinstance(section,dict):
                    doc.add_heading(self._safe_text(section.get("title","Section"),200), level=1); doc.add_paragraph(self._safe_text(section.get("body",""),12000))
                else: doc.add_paragraph(self._safe_text(section,12000))
            doc.save(target)
            return ProfessionalResult(action,str(workspace),str(args["path"]),{"bytes":target.stat().st_size,"sections":len(args["sections"])}).as_dict()
        if action == "spreadsheet.xlsx.create":
            openpyxl,*_=self._load_office(); target=self._target(workspace,str(args["path"])); target.parent.mkdir(parents=True,exist_ok=True)
            wb=openpyxl.Workbook(); wb.remove(wb.active)
            for idx,spec in enumerate(args["sheets"][:20],1):
                if not isinstance(spec,dict): continue
                ws=wb.create_sheet(str(spec.get("name") or f"Sheet{idx}")[:31]); headers=spec.get("headers") or []; rows=spec.get("rows") or []
                if headers: ws.append(list(headers))
                for row in rows[:10000]: ws.append(list(row) if isinstance(row,(list,tuple)) else [row])
                if headers:
                    for cell in ws[1]: cell.font=openpyxl.styles.Font(bold=True)
                    ws.freeze_panes="A2"
                for col in ws.columns:
                    letter=col[0].column_letter; width=min(40,max(10,max((len(str(c.value or "")) for c in col[:200]),default=10)+2)); ws.column_dimensions[letter].width=width
            if not wb.sheetnames: wb.create_sheet("Sheet1")
            wb.save(target)
            return ProfessionalResult(action,str(workspace),str(args["path"]),{"bytes":target.stat().st_size,"sheets":wb.sheetnames}).as_dict()
        if action in {"spreadsheet.xlsx.analyze","finance.workbook.analyze"}:
            target=self._target(workspace,str(args["path"]),must_exist=True); data=self._xlsx_analysis(target)
            if action=="finance.workbook.analyze": data["note"]="Análise descritiva; não movimenta fundos nem executa ordens."
            return ProfessionalResult(action,str(workspace),str(args["path"]),data).as_dict()
        if action == "office.report.from.xlsx":
            source=self._target(workspace,str(args["path"]),must_exist=True)
            analysis=self._xlsx_analysis(source)
            _, Document, *_ = self._load_office()
            target=self._target(workspace,str(args["output"])); target.parent.mkdir(parents=True,exist_ok=True)
            doc=Document(); doc.add_heading(str(args.get("title") or "Relatório Oryven"),0)
            doc.add_paragraph(f"Fonte analisada: {args['path']}")
            doc.add_heading("Resumo da pasta de trabalho", level=1)
            doc.add_paragraph(f"Planilhas analisadas: {analysis['sheet_count']}")
            for sheet in analysis["sheets"]:
                doc.add_heading(str(sheet["name"]), level=2)
                doc.add_paragraph(
                    f"Linhas: {sheet['rows']} | Colunas: {sheet['columns']} | "
                    f"Valores numéricos: {sheet['numeric_count']} | Soma numérica: {sheet['numeric_sum']:.2f}"
                )
            doc.add_paragraph("Relatório descritivo gerado localmente pelo Oryven; revise antes de decisões profissionais.")
            doc.save(target)
            return ProfessionalResult(action,str(workspace),str(args["output"]),{
                "source":str(args["path"]),"analysis":analysis,"bytes":target.stat().st_size,
                "report_generated_from_analysis":True,
            }).as_dict()
        if action == "office.open.document":
            target=self._target(workspace,str(args["path"]),must_exist=True)
            if os.name != "nt" or not hasattr(os, "startfile"):
                raise ProfessionalRuntimeError("Abrir documentos no aplicativo padrão exige Windows.")
            try:
                os.startfile(str(target))
            except OSError as exc:
                raise ProfessionalRuntimeError("O Windows não conseguiu abrir o documento no aplicativo associado.") from exc
            return ProfessionalResult(action,str(workspace),str(args["path"]),{
                "opened":True,"application":"windows-default-association","verified":False,
                "note":"Abertura solicitada; valide visualmente o aplicativo resultante.",
            }).as_dict()
        if action == "presentation.pptx.compose":
            *_, Presentation, _, _, _, _, _ = self._load_office(); target=self._target(workspace,str(args["path"])); target.parent.mkdir(parents=True,exist_ok=True)
            prs=Presentation(); slide=prs.slides.add_slide(prs.slide_layouts[0]); slide.shapes.title.text=str(args["title"]); slide.placeholders[1].text="Created by Oryven"
            for section in args["sections"][:50]:
                sld=prs.slides.add_slide(prs.slide_layouts[1]);
                if isinstance(section,dict): title=self._safe_text(section.get("title","Slide"),200); body=self._safe_text(section.get("body",""),6000)
                else: title="Slide"; body=self._safe_text(section,6000)
                sld.shapes.title.text=title; sld.placeholders[1].text=body
            prs.save(target)
            return ProfessionalResult(action,str(workspace),str(args["path"]),{"bytes":target.stat().st_size,"slides":len(prs.slides)}).as_dict()
        if action == "pdf.compose":
            *_, A4, SimpleDocTemplate, Paragraph, Spacer, getSampleStyleSheet = self._load_office(); target=self._target(workspace,str(args["path"])); target.parent.mkdir(parents=True,exist_ok=True)
            styles=getSampleStyleSheet(); story=[Paragraph(self._safe_text(args["title"],300),styles["Title"]),Spacer(1,12)]
            for section in args["sections"]:
                if isinstance(section,dict): title=self._safe_text(section.get("title","Section"),200); body=self._safe_text(section.get("body",""),12000)
                else: title=""; body=self._safe_text(section,12000)
                if title: story.extend([Paragraph(title,styles["Heading2"]),Spacer(1,6)])
                story.extend([Paragraph(body.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"),styles["BodyText"]),Spacer(1,10)])
            SimpleDocTemplate(str(target),pagesize=A4).build(story)
            return ProfessionalResult(action,str(workspace),str(args["path"]),{"bytes":target.stat().st_size}).as_dict()
        if action == "blender.assist":
            return self._write_text(workspace,str(args["output"]),"# Generated by Oryven for review before Blender execution.\n"+str(args["script"]),action)
        if action in {"maya.execute","blender.execute"}:
            target=self._target(workspace,str(args["path"]),must_exist=True); explicit=str(args.get("executable","") or "")
            if action=="maya.execute":
                exe=self._resolve_executable(explicit,"ORYVEN_MAYA_EXECUTABLE",["mayapy","maya"]); language=str(args.get("language") or ("mel" if target.suffix.lower()==".mel" else "python")).casefold()
                if language=="python": argv=[str(target)] if Path(exe).name.casefold().startswith("mayapy") else ["-batch","-command",f'python(\"exec(open(r\\\"{target}\\\").read())\")']
                else:
                    if Path(exe).name.casefold().startswith("mayapy"): raise ProfessionalRuntimeError("MEL requer executável Maya, não mayapy.")
                    argv=["-batch","-script",str(target)]
            else:
                exe=self._resolve_executable(explicit,"ORYVEN_BLENDER_EXECUTABLE",["blender"]); argv=["--background","--python",str(target)]
            data=self._run_external(exe,argv,workspace,timeout=180)
            return ProfessionalResult(action,str(workspace),str(args["path"]),data).as_dict()
        if action in {"cad.assets.inspect","bim.assets.inspect","media.assets.inspect"}:
            target=self._target(workspace,str(args.get("path",".")),must_exist=True)
            ext={"cad.assets.inspect":{ ".dwg",".dxf",".step",".stp",".iges",".igs"},"bim.assets.inspect":{ ".rvt",".rfa",".ifc"},"media.assets.inspect":{ ".png",".jpg",".jpeg",".webp",".gif",".mp4",".mov",".wav",".mp3"}}[action]
            return self._asset_inventory(workspace,target,ext,action)
        if action == "marketing.plan":
            channels=args.get("channels") or []; lines=[f"# Plano de Marketing - {self._safe_text(args.get('objective','Objetivo'),300)}","",f"Público: {self._safe_text(args.get('audience',''),500)}","","## Canais",* [f"- {self._safe_text(x,200)}" for x in channels],"","## Métricas","- Alcance","- Conversão","- CAC/CPA quando aplicável","- Receita atribuída","","## Revisão humana","Nenhuma publicação é executada automaticamente."]
            return self._write_text(workspace,str(args["path"]),"\n".join(lines),action)
        if action == "operations.sop.compose":
            lines=[f"# SOP - {self._safe_text(args.get('title','Processo'),300)}",""]
            for idx,section in enumerate(args.get("sections") or [],1): lines.extend([f"## {idx}. {self._safe_text(section.get('title','Etapa') if isinstance(section,dict) else f'Etapa {idx}',200)}",self._safe_text(section.get('body','') if isinstance(section,dict) else section,5000),""])
            return self._write_text(workspace,str(args["path"]),"\n".join(lines),action)
        if action in {"ecommerce.catalog.audit","logistics.analyze","hr.organize","support.triage"}:
            target=self._target(workspace,str(args["path"]),must_exist=True); headers,rows=self._read_csv(target); profile=self._csv_profile(target,detailed=True)
            if action=="ecommerce.catalog.audit":
                expected={"sku","name","title","price","stock"}; present={h.casefold() for h in headers}; profile["missing_recommended_columns"]=sorted(expected-present); profile["duplicate_rows"]=len(rows)-len({tuple((r.get(h,"") or "").strip() for h in headers) for r in rows})
            elif action=="hr.organize": profile["note"]="Organização descritiva apenas; sem ranking, contratação ou decisão sobre pessoas."
            elif action=="support.triage": profile["note"]="Agrupamento descritivo; nenhuma resposta ou fechamento automático de ticket."
            return ProfessionalResult(action,str(workspace),str(args["path"]),profile).as_dict()
        if action == "crm.pipeline.analyze":
            target=self._target(workspace,str(args["path"]),must_exist=True); headers,rows=self._read_csv(target); status_col=str(args.get("status_column") or "status"); amount_col=str(args.get("amount_column") or "amount")
            if status_col not in headers: raise ProfessionalRuntimeError("Coluna de status não encontrada.")
            stages=Counter((r.get(status_col,"") or "(vazio)").strip() for r in rows); amounts={};
            if amount_col in headers:
                for r in rows:
                    st=(r.get(status_col,"") or "(vazio)").strip(); n=self._number(r.get(amount_col,"") or ""); amounts[st]=amounts.get(st,0.0)+(n or 0.0)
            return ProfessionalResult(action,str(workspace),str(args["path"]),{"rows":len(rows),"stages":dict(stages),"amount_by_stage":amounts}).as_dict()
        if action == "accounting.reconcile.preview":
            source=self._target(workspace,str(args["path"]),must_exist=True); headers,rows=self._read_csv(source); out=self._target(workspace,str(args["output"])); out.parent.mkdir(parents=True,exist_ok=True)
            seen=Counter(tuple((r.get(h,"") or "").strip() for h in headers) for r in rows); preview=[]
            for key,count in seen.items(): preview.append({**dict(zip(headers,key)),"occurrences":count,"review_required":count>1})
            with out.open("w",encoding="utf-8",newline="") as fh:
                writer=csv.DictWriter(fh,fieldnames=[*headers,"occurrences","review_required"]); writer.writeheader(); writer.writerows(preview)
            return ProfessionalResult(action,str(workspace),str(args["output"]),{"rows":len(preview),"duplicates_flagged":sum(1 for r in preview if r["review_required"])}).as_dict()
        raise ProfessionalRuntimeError("Ação profissional não suportada.")
